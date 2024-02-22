from typing import Any

from torch import device as Device, dtype as DType, arange, einsum, cat
import refiners.fluxion.layers as fl

from refiners.foundationals.fuyu.common import SquaredReLU
from refiners.foundationals.dinov2.vit import FeedForward


class RotaryPositionalEmbedding(fl.Module):
    def __init__(
        self,
        n_features: int = 4096,
        base: int = 10_000,
    ) -> None:
        super().__init__()
        self.n_features = n_features
        self.base = base
        # Create positional encodings
        theta = 1 / (self.base ** ((arange(0, self.n_features, 2).float()) / self.n_features))
        self.register_buffer("theta", theta)

    def forward(self, q, k, v, mask):
        q_text = q[:, mask]
        k_text = k[:, mask]

        # Q rotation
        q_seq_len = q_text.shape[1]
        q_position_idxs = arange(q_seq_len, device=q_text.device).float()
        q_freqs = einsum("i,j->ij", q_position_idxs, self.theta)
        q_emb = cat([q_freqs, q_freqs], dim=1).to(q_text.device)
        q_rot = self.apply_rotary_embedding(q_text, q_emb)

        # K rotation
        k_seq_len = k_text.shape[1]
        k_position_idxs = arange(k_seq_len, device=k_text.device).float()
        k_freqs = einsum("i,j->ij", k_position_idxs, self.theta)
        k_emb = cat([k_freqs, k_freqs], dim=1).to(k_text.device)
        k_rot = self.apply_rotary_embedding(k_text, k_emb)

        q[:, mask] = q_rot
        k[:, mask] = k_rot

        return q, k, v

    def apply_rotary_embedding(self, x, emb, seq_len):
        # Split x into two halves for real and imaginary components for rotation
        x1, x2 = x.split(self.n_features // 2, dim=-1)
        x_halfr = cat((-x2, x1), dim=-1)
        # Apply rotation
        x_rot = x * emb.cos()[:seq_len] + x_halfr * emb.sin()[:seq_len]
        return x_rot


class FuyuAttention(fl.Chain):
    """Multi-Head Attention layer with fuyu-8b spcificities : Rotary Embedding and Layer Norm added to QK.

    ??? note "See [[arXiv:1706.03762] Attention Is All You Need (Figure 2)](https://arxiv.org/abs/1706.03762) and
    https://www.adept.ai/blog/persimmon-8b for more details"

        ![](https://ar5iv.labs.arxiv.org/html/1706.03762/assets/Figures/ModalNet-20.png)

    Note: This layer simply chains
        - a [`Distribute`][refiners.fluxion.layers.chain.Distribute] layer,
            containing 3 [`Linear`][refiners.fluxion.layers.linear.Linear] layers,
            which transforms the 3 inputs into Query, Key and Value
        - a [`ScaledDotProductAttention`][refiners.fluxion.layers.attentions.ScaledDotProductAttention] layer
        - a [`Linear`][refiners.fluxion.layers.linear.Linear] layer,
            which projects the output of the
            [`ScaledDotProductAttention`][refiners.fluxion.layers.attentions.ScaledDotProductAttention] layer

    Receives:
        Query (Float[Tensor, "batch sequence_length embedding_dim"]):
        Key (Float[Tensor, "batch sequence_length embedding_dim"]):
        Value (Float[Tensor, "batch sequence_length embedding_dim"]):
        Mask (Bool[Tensor, ""sequence length])

    Returns:
        (Float[Tensor, "batch sequence_length embedding_dim"]):

    Example:
        ```py
        attention = fl.Attention(num_heads=8, embedding_dim=128)

        tensor = torch.randn(2, 10, 128)
        output = attention(tensor, tensor, tensor)

        assert output.shape == (2, 10, 128)
        ```
    """

    def __init__(
        self,
        embedding_dim: int,
        num_heads: int = 1,
        key_embedding_dim: int | None = None,
        value_embedding_dim: int | None = None,
        inner_dim: int | None = None,
        base: int = 10_000,
        norm_eps: float = 1e-6,
        use_bias: bool = True,
        is_causal: bool = False,
        is_optimized: bool = True,
        device: Device | str | None = None,
        dtype: DType | None = None,
    ) -> None:
        """Initialize the Attention layer.

        Args:
            embedding_dim: The embedding dimension of the input and output tensors.
            num_heads: The number of heads to use.
            key_embedding_dim: The embedding dimension of the key tensor.
            value_embedding_dim: The embedding dimension of the value tensor.
            inner_dim: The inner dimension of the linear layers.
            base: constant used to compute theta in the Rotary Positional Embedding
            norm_eps: epsilon for Layer Norm
            use_bias: Whether to use bias in the linear layers.
            is_causal: Whether to use causal attention.
            is_optimized: Whether to use optimized attention.
            device: The device to use.
            dtype: The dtype to use.
        """
        assert (
            embedding_dim % num_heads == 0
        ), f"embedding_dim {embedding_dim} must be divisible by num_heads {num_heads}"
        self.embedding_dim = embedding_dim
        self.num_heads = num_heads
        self.heads_dim = embedding_dim // num_heads
        self.key_embedding_dim = key_embedding_dim or embedding_dim
        self.value_embedding_dim = value_embedding_dim or embedding_dim
        self.inner_dim = inner_dim or embedding_dim
        self.use_bias = use_bias
        self.is_causal = is_causal
        self.is_optimized = is_optimized
        self.base = base
        self.norm_eps = norm_eps

        super().__init__(
            fl.Distribute(
                fl.Linear(  # Query projection
                    in_features=self.embedding_dim,
                    out_features=self.inner_dim,
                    bias=self.use_bias,
                    device=device,
                    dtype=dtype,
                ),
                fl.Linear(  # Key projection
                    in_features=self.key_embedding_dim,
                    out_features=self.inner_dim,
                    bias=self.use_bias,
                    device=device,
                    dtype=dtype,
                ),
                fl.Linear(  # Value projection
                    in_features=self.value_embedding_dim,
                    out_features=self.inner_dim,
                    bias=self.use_bias,
                    device=device,
                    dtype=dtype,
                ),
                fl.Identity(),  # Mask to perform Rotary Projection Embedding only on the text component
            ),
            RotaryPositionalEmbedding(
                n_features=inner_dim,
                base=base,
            ),
            fl.Distribute(
                fl.LayerNorm(  # Layer Norm on Q
                    normalized_shape=self.inner_dim,
                    eps=self.norm_eps,
                    device=device,
                    dtype=dtype,
                ),
                fl.LayerNorm(  # Layer Norm on K
                    normalized_shape=self.inner_dim, eps=self.norm_eps, device=device, dtype=dtype
                ),
                fl.Identity(),  # No Layer Norm on V
            ),
            fl.ScaledDotProductAttention(
                num_heads=num_heads,
                is_causal=is_causal,
                is_optimized=is_optimized,
            ),
            fl.Linear(  # Output projection
                in_features=self.inner_dim,
                out_features=self.embedding_dim,
                bias=True,
                device=device,
                dtype=dtype,
            ),
        )


class FuyuSelfAttention(FuyuAttention):
    """Fuyu Self-Attention layer.

    Note: This layer simply chains
        - a [`Parallel`][refiners.fluxion.layers.chain.Parallel] layer,
        which duplicates the input Tensor
        (for each Linear layer in the `Attention` layer)
        - an [`Attention`][refiners.fluxion.layers.attentions.Attention] layer

    Receives:
        (Float[Tensor, "batch sequence_length embedding_dim"]):
        (Bool[Tensor, "sequence_length']):

    Returns:
        (Float[Tensor, "batch sequence_length embedding_dim"]):

    Example:
        ```py
        self_attention = fl.SelfAttention(num_heads=8, embedding_dim=128)

        tensor = torch.randn(2, 10, 128)
        output = self_attention(tensor)

        assert output.shape == (2, 10, 128)
        ```
    """

    def __init__(
        self,
        embedding_dim: int = 4096,
        inner_dim: int | None = None,
        num_heads: int = 64,
        norm_eps: float = 1e-6,
        base: int = 10_000,
        use_bias: bool = True,
        is_causal: bool = True,
        is_optimized: bool = True,
        device: Device | str | None = None,
        dtype: DType | None = None,
    ) -> None:
        """Initialize the Self-Attention layer.

        Args:
            embedding_dim: The embedding dimension of the input and output tensors.
            inner_dim: The inner dimension of the linear layers.
            num_heads: The number of heads to use.
            use_bias: Whether to use bias in the linear layers.
            is_causal: Whether to use causal attention.
            is_optimized: Whether to use optimized attention.
            device: The device to use.
            dtype: The dtype to use.
        """
        super().__init__(
            embedding_dim=embedding_dim,
            inner_dim=inner_dim,
            num_heads=num_heads,
            base=base,
            norm_eps=norm_eps,
            use_bias=use_bias,
            is_causal=is_causal,
            is_optimized=is_optimized,
            device=device,
            dtype=dtype,
        )
        self.insert(
            index=0,
            module=fl.Parallel(
                fl.GetArg(0),  # Query projection's input
                fl.GetArg(0),  # Key projection's input
                fl.GetArg(0),  # Value projection's input
                fl.GetArg(1),  # Mask to perform Rotary Projection Embedding only on the text component
            ),
        )


class FuyuTransformerLayer(fl.Chain):
    """Apply a multi-head self-attention mechanism to the input tensor."""

    def __init__(
        self,
        embedding_dim: int = 4_096,
        inner_dim: int | None = None,
        feedforward_dim: int = 16_384,
        num_heads: int = 64,
        norm_eps: float = 1e-6,
        base: int = 10_000,
        use_bias: bool = True,
        is_causal: bool = True,
        is_optimized: bool = True,
        device: Device | str | None = None,
        dtype: DType | None = None,
    ) -> None:
        self.embedding_dim = embedding_dim
        self.num_heads = num_heads
        self.norm_eps = norm_eps
        self.feedforward_dim = feedforward_dim
        self.base = base
        super().__init__(
            fl.Residual(
                fl.LayerNorm(
                    normalized_shape=embedding_dim,
                    eps=norm_eps,
                    device=device,
                    dtype=dtype,
                ),
                FuyuSelfAttention(
                    embedding_dim=embedding_dim,
                    inner_dim=inner_dim,
                    num_heads=num_heads,
                    base=base,
                    norm_eps=norm_eps,
                    use_bias=use_bias,
                    is_causal=is_causal,
                    is_optimized=is_optimized,
                    device=device,
                    dtype=dtype,
                ),
            ),
            fl.Residual(
                fl.LayerNorm(
                    normalized_shape=embedding_dim,
                    eps=norm_eps,
                    device=device,
                    dtype=dtype,
                ),
                FeedForward(
                    embedding_dim=embedding_dim,
                    feedforward_dim=feedforward_dim,
                    activation=SquaredReLU(),
                    device=device,
                    dtype=dtype,
                ),
            ),
        )

    def forward(self, *args: Any) -> Any:
        result: tuple[Any] | Any = None
        intermediate_args: tuple[Any, ...] = args
        for name, layer in self._modules.items():
            if isinstance(layer, FuyuSelfAttention):  # We passe the mask information to the SelfAttention module only
                result = self._call_layer(layer, name, *intermediate_args)
            else:
                result = self._call_layer(layer, name, intermediate_args[0])

            intermediate_args[0] = result

        self._reset_context()
        return result


class FuyuTransformer(fl.Chain):
    """Alias for a Chain of FuyuTransformerLayer."""