from dataclasses import dataclass
from typing import Sequence

import torch
from jaxtyping import Float
from PIL import Image
from torch import Tensor, device as Device, dtype as DType

import refiners.fluxion.layers as fl
from refiners.fluxion.utils import no_grad
from refiners.foundationals.segment_anything.image_encoder import SAMViT, SAMViTH
from refiners.foundationals.segment_anything.mask_decoder import MaskDecoder
from refiners.foundationals.segment_anything.prompt_encoder import MaskEncoder, PointEncoder
from refiners.foundationals.segment_anything.utils import (
    normalize_coordinates,
    postprocess_masks,
    preprocess_image,
)


@dataclass
class ImageEmbedding:
    features: Tensor
    original_image_size: tuple[int, int]  # (height, width)


class SegmentAnything(fl.Chain):
    """SegmentAnything model.

    See [[arXiv:2304.02643] Segment Anything](https://arxiv.org/abs/2304.02643)

    E.g. see [`SegmentAnythingH`][refiners.foundationals.segment_anything.model.SegmentAnythingH] for usage.

    Attributes:
        mask_threshold (float): 0.0
    """

    mask_threshold: float = 0.0

    def __init__(
        self,
        image_encoder: SAMViT,
        point_encoder: PointEncoder,
        mask_encoder: MaskEncoder,
        mask_decoder: MaskDecoder,
        device: Device | str = "cpu",
        dtype: DType = torch.float32,
    ) -> None:
        """Initialize SegmentAnything model.

        Args:
            image_encoder: The image encoder to use.
            point_encoder: The point encoder to use.
            mask_encoder: The mask encoder to use.
            mask_decoder: The mask decoder to use.
        """
        super().__init__(image_encoder, point_encoder, mask_encoder, mask_decoder)

        self.to(device=device, dtype=dtype)

    @property
    def image_encoder(self) -> SAMViT:
        """The image encoder."""
        return self.ensure_find(SAMViT)

    @property
    def point_encoder(self) -> PointEncoder:
        """The point encoder."""
        return self.ensure_find(PointEncoder)

    @property
    def mask_encoder(self) -> MaskEncoder:
        """The mask encoder."""
        return self.ensure_find(MaskEncoder)

    @property
    def mask_decoder(self) -> MaskDecoder:
        """The mask decoder."""
        return self.ensure_find(MaskDecoder)

    @no_grad()
    def compute_image_embedding(self, image: Image.Image) -> ImageEmbedding:
        """Compute the emmbedding of an image.

        Args:
            image: The image to compute the embedding of.

        Returns:
            The computed image embedding.
        """
        original_size = (image.height, image.width)
        return ImageEmbedding(
            features=self.image_encoder(self.preprocess_image(image)),
            original_image_size=original_size,
        )

    @no_grad()
    def predict(
        self,
        input: Image.Image | ImageEmbedding,
        foreground_points: Sequence[tuple[float, float]] | None = None,
        background_points: Sequence[tuple[float, float]] | None = None,
        box_points: Sequence[Sequence[tuple[float, float]]] | None = None,
        low_res_mask: Float[Tensor, "1 1 256 256"] | None = None,
        binarize: bool = True,
    ) -> tuple[Tensor, Tensor, Tensor]:
        """Predict the masks of the input image.

        Args:
            input: The input image or its embedding.
            foreground_points: The points of the foreground.
            background_points: The points of the background.
            box_points: The points of the box.
            low_res_mask: The low resolution mask.
            binarize: Whether to binarize the masks.

        Returns:
            The predicted masks.
            The IOU prediction.
            The low resolution masks.
        """
        if isinstance(input, ImageEmbedding):
            original_size = input.original_image_size
            image_embedding = input.features
        else:
            original_size = (input.height, input.width)
            image_embedding = self.image_encoder(self.preprocess_image(input))

        coordinates, type_mask = self.point_encoder.points_to_tensor(
            foreground_points=foreground_points,
            background_points=background_points,
            box_points=box_points,
        )
        self.point_encoder.set_type_mask(type_mask=type_mask)

        if low_res_mask is not None:
            mask_embedding = self.mask_encoder(low_res_mask)
        else:
            mask_embedding = self.mask_encoder.get_no_mask_dense_embedding(
                image_embedding_size=self.image_encoder.image_embedding_size
            )

        point_embedding = self.point_encoder(self.normalize(coordinates, original_size=original_size))
        dense_positional_embedding = self.point_encoder.get_dense_positional_embedding(
            image_embedding_size=self.image_encoder.image_embedding_size
        )

        self.mask_decoder.set_image_embedding(image_embedding=image_embedding)
        self.mask_decoder.set_mask_embedding(mask_embedding=mask_embedding)
        self.mask_decoder.set_point_embedding(point_embedding=point_embedding)
        self.mask_decoder.set_dense_positional_embedding(dense_positional_embedding=dense_positional_embedding)

        low_res_masks, iou_predictions = self.mask_decoder()

        high_res_masks = self.postprocess_masks(low_res_masks, original_size)

        if binarize:
            high_res_masks = high_res_masks > self.mask_threshold

        return high_res_masks, iou_predictions, low_res_masks

    @property
    def image_encoder_resolution(self) -> int:
        """The resolution of the image encoder."""
        w, h = self.image_encoder.image_size
        assert w == h
        return w

    def preprocess_image(self, image: Image.Image) -> Tensor:
        """
        See [`preprocess_image`][refiners.foundationals.segment_anything.utils.preprocess_image]
        Args:
            image: The image to preprocess.
        Returns:
            The preprocessed tensor.
        """
        return preprocess_image(image, self.image_encoder_resolution, self.device, self.dtype)

    def normalize(self, coordinates: Tensor, original_size: tuple[int, int]) -> Tensor:
        """
        See [`normalize_coordinates`][refiners.foundationals.segment_anything.utils.normalize_coordinates]
        Args:
            coordinates: a tensor of coordinates.
            original_size: (h, w) the original size of the image.
        Returns:
            The [0,1] normalized coordinates tensor.
        """
        return normalize_coordinates(coordinates, original_size, self.image_encoder_resolution)

    def postprocess_masks(self, low_res_masks: Tensor, original_size: tuple[int, int]) -> Tensor:
        """
        See [`postprocess_masks`][refiners.foundationals.segment_anything.utils.postprocess_masks]
        Args:
            low_res_masks: a mask tensor of size (N, 1, 256, 256)
            original_size: (h, w) the original size of the image.
        Returns:
            The mask of shape (N, 1, H, W)
        """
        return postprocess_masks(low_res_masks, original_size, self.image_encoder_resolution)


class SegmentAnythingH(SegmentAnything):
    """SegmentAnything huge model."""

    def __init__(
        self,
        image_encoder: SAMViTH | None = None,
        point_encoder: PointEncoder | None = None,
        mask_encoder: MaskEncoder | None = None,
        mask_decoder: MaskDecoder | None = None,
        multimask_output: bool | None = None,
        device: Device | str = "cpu",
        dtype: DType = torch.float32,
    ) -> None:
        """Initialize SegmentAnything huge model.

        Args:
            image_encoder: The image encoder to use.
            point_encoder: The point encoder to use.
            mask_encoder: The mask encoder to use.
            mask_decoder: The mask decoder to use.
            multimask_output: Whether to use multimask output.
            device: The PyTorch device to use.
            dtype: The PyTorch data type to use.

        Example:
            ```py
            device="cuda" if torch.cuda.is_available() else "cpu"

            # multimask_output=True is recommended for ambiguous prompts such as a single point.
            # Below, a box prompt is passed, so just use multimask_output=False which will return a single mask
            sam_h = SegmentAnythingH(multimask_output=False, device=device)

            # Tips: run scripts/prepare_test_weights.py to download the weights
            tensors_path = "./tests/weights/segment-anything-h.safetensors"
            sam_h.load_from_safetensors(tensors_path=tensors_path)

            from PIL import Image
            image = Image.open("image.png")

            masks, *_ = sam_h.predict(image, box_points=[[(x1, y1), (x2, y2)]])

            assert masks.shape == (1, 1, image.height, image.width)
            assert masks.dtype == torch.bool

            # convert it to [0,255] uint8 ndarray of shape (H, W)
            mask = masks[0, 0].cpu().numpy().astype("uint8") * 255

            Image.fromarray(mask).save("mask_image.png")
            ```
        """
        image_encoder = image_encoder or SAMViTH()
        point_encoder = point_encoder or PointEncoder()
        mask_encoder = mask_encoder or MaskEncoder()

        if mask_decoder:
            assert (
                multimask_output is None or mask_decoder.multimask_output == multimask_output
            ), f"mask_decoder.multimask_output {mask_decoder.multimask_output} should match multimask_output ({multimask_output})"
        else:
            mask_decoder = MaskDecoder(multimask_output) if multimask_output is not None else MaskDecoder()

        super().__init__(image_encoder, point_encoder, mask_encoder, mask_decoder)

        self.to(device=device, dtype=dtype)

    @property
    def image_encoder(self) -> SAMViTH:
        """The image encoder."""
        return self.ensure_find(SAMViTH)
