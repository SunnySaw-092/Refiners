import torch
from torch.nn.functional import relu
from torch import device as Device, dtype as DType, Tensor

import refiners.fluxion.layers as fl


class SquaredReLU(fl.Activation):
    def __init__(self) -> None:
        super().__init__()

    def forward(self, x: Tensor) -> Tensor:
        return torch.pow(relu(x), 2)


class Padding(fl.Module):
    def __init__(
        self,
        patch_size: int = 30,
        padding_value: int = 0,
    ):
        super().__init__()
        self.patch_size = patch_size
        self.padding_value = padding_value

    def forward(self, x: Tensor) -> Tensor:
        h, w = x.shape[2:]

        pad_h = h % self.patch_size
        pad_w = w % self.patch_size
        padded_x = torch.pad(
            x,
            (pad_h // 2, pad_h // 2 + pad_h % 2, pad_w // 2, pad_w // 2 + pad_w % 2),
            mode="constant",
            value=self.padding_value,
        )
        return padded_x