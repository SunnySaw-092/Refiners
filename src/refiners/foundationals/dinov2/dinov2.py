import torch
from PIL import Image

from refiners.fluxion.layers.activations import GLU, SiLU
from refiners.fluxion.utils import image_to_tensor, normalize
from refiners.foundationals.dinov2.vit import ViT


def preprocess(img: Image.Image, dim: int = 224) -> torch.Tensor:
    """
    Preprocess an image for use with DINOv2. Uses ImageNet mean and standard deviation.
    Note that this only resizes and normalizes the image, there is no center crop.

    Args:
        img: The image.
        dim: The square dimension to resize the image. Typically 224 or 518.

    Returns:
        A float32 tensor with shape (3, dim, dim).
    """
    img = img.convert("RGB").resize((dim, dim))  # type: ignore
    t = image_to_tensor(img).squeeze()
    return normalize(t, mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])


class DINOv2_small(ViT):
    """DINOv2 small model.

    See [[arXiv:2304.07193] DINOv2: Learning Robust Visual Features without Supervision](https://arxiv.org/abs/2304.07193)
    for more details.

    Attributes:
        embedding_dim (int): 384
        patch_size (int): 14
        image_size (int): 518
        num_layers (int): 12
        num_heads (int): 6
    """

    def __init__(
        self,
        device: torch.device | str | None = None,
        dtype: torch.dtype | None = None,
    ) -> None:
        """Initialize DINOv2 small model.

        Args:
            device: The PyTorch device to use.
            dtype: The PyTorch data type to use.
        """
        super().__init__(
            embedding_dim=384,
            patch_size=14,
            image_size=518,
            num_layers=12,
            num_heads=6,
            device=device,
            dtype=dtype,
        )


class DINOv2_base(ViT):
    """DINOv2 base model.

    See [[arXiv:2304.07193] DINOv2: Learning Robust Visual Features without Supervision](https://arxiv.org/abs/2304.07193)
    for more details.

    Attributes:
        embedding_dim (int): 768
        patch_size (int): 14
        image_size (int): 518
        num_layers (int): 12
        num_heads (int): 12
    """

    def __init__(
        self,
        device: torch.device | str | None = None,
        dtype: torch.dtype | None = None,
    ) -> None:
        """Initialize DINOv2 base model.

        Args:
            device: The PyTorch device to use.
            dtype: The PyTorch data type to use.
        """
        super().__init__(
            embedding_dim=768,
            patch_size=14,
            image_size=518,
            num_layers=12,
            num_heads=12,
            device=device,
            dtype=dtype,
        )


class DINOv2_large(ViT):
    """DINOv2 large model.

    See [[arXiv:2304.07193] DINOv2: Learning Robust Visual Features without Supervision](https://arxiv.org/abs/2304.07193)
    for more details.

    Attributes:
        embedding_dim (int): 1024
        patch_size (int): 14
        image_size (int): 518
        num_layers (int): 24
        num_heads (int): 16
    """

    def __init__(
        self,
        device: torch.device | str | None = None,
        dtype: torch.dtype | None = None,
    ) -> None:
        """Initialize DINOv2 large model.

        Args:
            device: The PyTorch device to use.
            dtype: The PyTorch data type to use.
        """
        super().__init__(
            embedding_dim=1024,
            patch_size=14,
            image_size=518,
            num_layers=24,
            num_heads=16,
            device=device,
            dtype=dtype,
        )


class DINOv2_giant(ViT):
    """DINOv2 giant model.

    See [[arXiv:2304.07193] DINOv2: Learning Robust Visual Features without Supervision](https://arxiv.org/abs/2304.07193)
    for more details.

    Attributes:
        embedding_dim (int): 1536
        feedforward_dim (int): 4096
        patch_size (int): 14
        image_size (int): 518
        num_layers (int): 40
        num_heads (int): 24
    """

    def __init__(
        self,
        device: torch.device | str | None = None,
        dtype: torch.dtype | None = None,
    ) -> None:
        """Initialize DINOv2 giant model.

        Args:
            device: The PyTorch device to use.
            dtype: The PyTorch data type to use.
        """
        super().__init__(
            embedding_dim=1536,
            feedforward_dim=4096,
            patch_size=14,
            image_size=518,
            num_layers=40,
            num_heads=24,
            activation=GLU(SiLU()),
            device=device,
            dtype=dtype,
        )


class DINOv2_small_reg(ViT):
    """DINOv2 small model with register.

    See [[arXiv:2304.07193] DINOv2: Learning Robust Visual Features without Supervision](https://arxiv.org/abs/2304.07193)
    and [[arXiv:2309.16588] Vision Transformers Need Registers](https://arxiv.org/abs/2309.16588)
    for more details.

    Attributes:
        embedding_dim (int): 384
        patch_size (int): 14
        image_size (int): 518
        num_layers (int): 12
        num_heads (int): 6
        num_registers (int): 4
        interpolate_antialias (bool): True
    """

    def __init__(
        self,
        device: torch.device | str | None = None,
        dtype: torch.dtype | None = None,
    ) -> None:
        """Initialize DINOv2 small model with register.

        Args:
            device (torch.device | str | None): The PyTorch device to use.
            dtype (torch.dtype | None): The PyTorch data type to use.
        """
        super().__init__(
            embedding_dim=384,
            patch_size=14,
            image_size=518,
            num_layers=12,
            num_heads=6,
            num_registers=4,
            interpolate_antialias=True,
            device=device,
            dtype=dtype,
        )


class DINOv2_base_reg(ViT):
    """DINOv2 base model with register.

    See [[arXiv:2304.07193] DINOv2: Learning Robust Visual Features without Supervision](https://arxiv.org/abs/2304.07193)
    and [[arXiv:2309.16588] Vision Transformers Need Registers](https://arxiv.org/abs/2309.16588)
    for more details.

    Attributes:
        embedding_dim (int): 768
        patch_size (int): 14
        image_size (int): 518
        num_layers (int): 12
        num_heads (int): 12
        num_registers (int): 4
        interpolate_antialias (bool): True
    """

    def __init__(
        self,
        device: torch.device | str | None = None,
        dtype: torch.dtype | None = None,
    ) -> None:
        """Initialize DINOv2 base model with register.

        Args:
            device (torch.device | str | None): The PyTorch device to use.
            dtype (torch.dtype | None): The PyTorch data type to use.
        """
        super().__init__(
            embedding_dim=768,
            patch_size=14,
            image_size=518,
            num_layers=12,
            num_heads=12,
            num_registers=4,
            interpolate_antialias=True,
            device=device,
            dtype=dtype,
        )


class DINOv2_large_reg(ViT):
    """DINOv2 large model with register.

    See [[arXiv:2304.07193] DINOv2: Learning Robust Visual Features without Supervision](https://arxiv.org/abs/2304.07193)
    and [[arXiv:2309.16588] Vision Transformers Need Registers](https://arxiv.org/abs/2309.16588)
    for more details.

    Attributes:
        embedding_dim (int): 1024
        patch_size (int): 14
        image_size (int): 518
        num_layers (int): 24
        num_heads (int): 16
        num_registers (int): 4
        interpolate_antialias (bool): True
    """

    def __init__(
        self,
        device: torch.device | str | None = None,
        dtype: torch.dtype | None = None,
    ) -> None:
        """Initialize DINOv2 large model with register.

        Args:
            device (torch.device | str | None): The PyTorch device to use.
            dtype (torch.dtype | None): The PyTorch data type to use.
        """
        super().__init__(
            embedding_dim=1024,
            patch_size=14,
            image_size=518,
            num_layers=24,
            num_heads=16,
            num_registers=4,
            interpolate_antialias=True,
            device=device,
            dtype=dtype,
        )


class DINOv2_giant_reg(ViT):
    """DINOv2 giant model with register.

    See [[arXiv:2304.07193] DINOv2: Learning Robust Visual Features without Supervision](https://arxiv.org/abs/2304.07193)
    and [[arXiv:2309.16588] Vision Transformers Need Registers](https://arxiv.org/abs/2309.16588)

    Attributes:
        embedding_dim (int): 1536
        feedforward_dim (int): 4096
        patch_size (int): 14
        image_size (int): 518
        num_layers (int): 40
        num_heads (int): 24
        num_registers (int): 4
        interpolate_antialias (bool): True
    """

    def __init__(
        self,
        device: torch.device | str | None = None,
        dtype: torch.dtype | None = None,
    ) -> None:
        """Initialize DINOv2 giant model with register.

        Args:
            device (torch.device | str | None): The PyTorch device to use.
            dtype (torch.dtype | None): The PyTorch data type to use.
        """
        super().__init__(
            embedding_dim=1536,
            feedforward_dim=4096,
            patch_size=14,
            image_size=518,
            num_layers=40,
            num_heads=24,
            num_registers=4,
            interpolate_antialias=True,
            activation=GLU(SiLU()),
            device=device,
            dtype=dtype,
        )
