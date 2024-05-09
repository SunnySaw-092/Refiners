from typing import Callable, TypeVar

from pydantic import BaseModel, ConfigDict, NonNegativeInt, PositiveInt, model_validator
from torch.utils.data import DataLoader, Dataset
from typing_extensions import Self

BatchT = TypeVar("BatchT")


class DataLoaderConfig(BaseModel):
    batch_size: PositiveInt = 1
    num_workers: NonNegativeInt = 0
    pin_memory: bool = False
    prefetch_factor: PositiveInt | None = None
    persistent_workers: bool = False
    drop_last: bool = False
    shuffle: bool = True

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def check_prefetch_factor(self) -> Self:
        if self.prefetch_factor is not None and self.num_workers == 0:
            raise ValueError(f"prefetch_factor={self.prefetch_factor} requires num_workers > 0")
        return self

    @model_validator(mode="after")
    def check_num_workers(self) -> Self:
        if self.num_workers == 0 and self.persistent_workers is True:
            raise ValueError(f"persistent_workers={self.persistent_workers} option needs num_workers > 0")
        return self


class DatasetFromCallable(Dataset[BatchT]):
    """
    A wrapper around the `get_item` method to create a [`torch.utils.data.Dataset`][torch.utils.data.Dataset].
    """

    def __init__(self, get_item: Callable[[int], BatchT], length: int) -> None:
        assert length > 0, "Dataset length must be greater than 0."
        self.length = length
        self.get_item = get_item

    def __getitem__(self, index: int) -> BatchT:
        return self.get_item(index)

    def __len__(self) -> int:
        return self.length


def create_data_loader(
    get_item: Callable[[int], BatchT],
    length: int,
    config: DataLoaderConfig,
    collate_fn: Callable[[list[BatchT]], BatchT] | None = None,
) -> DataLoader[BatchT]:
    return DataLoader(
        DatasetFromCallable(get_item, length),
        batch_size=config.batch_size,
        num_workers=config.num_workers,
        pin_memory=config.pin_memory,
        prefetch_factor=config.prefetch_factor,
        persistent_workers=config.persistent_workers,
        drop_last=config.drop_last,
        shuffle=config.shuffle,
        collate_fn=collate_fn,
    )
