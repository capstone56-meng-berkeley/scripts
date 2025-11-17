"""Image augmentation operations using the FileOperation interface."""

import os
import uuid
import logging
from datetime import datetime
from typing import List, Optional, Sequence

import cv2
import numpy as np
import albumentations as A

from .file_processor import FileOperation


def is_image(path: str) -> bool:
    """Check if file is an image."""
    EXTS = [".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"]
    return os.path.splitext(path)[1].lower() in EXTS


class AugmentationOperation:
    """Wrapper for albumentations transform."""

    def __init__(self, name: str, transform: A.Compose):
        self.name = name
        self.transform = transform

    def apply(self, image: np.ndarray, idx: int) -> np.ndarray:
        return self.transform(image=image)["image"]


class ImageAugmentationOp(FileOperation):
    """
    File operation for image augmentation.

    Applies multiple augmentation operations to each image and saves
    the augmented versions to the output directory.
    """

    def __init__(self, operations: Sequence[AugmentationOperation],
                 n_samples_per_op: int = 2, seed: int = 42):
        """
        Initialize image augmentation operation.

        Args:
            operations: List of AugmentationOperation instances
            n_samples_per_op: Number of augmented samples per operation
            seed: Random seed for reproducibility
        """
        super().__init__("image_augmentation")
        self.operations = list(operations)
        self.n_samples_per_op = n_samples_per_op
        self.seed = seed

        # Column names for state tracking
        self.op_names = [op.name for op in self.operations]

        # Get logger
        self.logger = logging.getLogger('FileProcessor')

    def get_operation_columns(self) -> List[str]:
        """Get operation-specific columns for state tracking."""
        return ["result", "status", "samples_generated"] + self.op_names

    def process(self, input_path: str, output_dir: str, file_id: str) -> Optional[dict]:
        """
        Process a single image with augmentations.

        Args:
            input_path: Path to input image
            output_dir: Directory to save augmented images
            file_id: Unique identifier for the image

        Returns:
            Dictionary with processing results including samples_generated count, or None if failed
        """
        if not is_image(input_path):
            print(f"    Skipping non-image file: {input_path}")
            return None

        # Load image
        img = cv2.imread(input_path, cv2.IMREAD_UNCHANGED)
        if img is None:
            msg = f"Failed to read: {input_path}"
            print(f"    [WARN] {msg}")
            self.logger.warning(msg)
            return None

        # Normalize image to 3 channels (RGB)
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        elif img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        elif img.shape[2] != 3:
            msg = f"Unsupported image format with {img.shape[2]} channels: {input_path}"
            print(f"    [WARN] {msg}")
            self.logger.warning(msg)
            return None

        # Apply each augmentation operation
        result_data = {"result": output_dir}
        total_generated = 0

        for op in self.operations:
            samples_for_this_op = 0
            for i in range(self.n_samples_per_op):
                aug_img = op.apply(img, idx=i)
                uid = uuid.uuid4().hex[:12]
                ts = datetime.now().strftime("%Y%m%dT%H%M%S")
                out_name = f"{op.name}__{uid}__{ts}.jpg"
                out_path = os.path.join(output_dir, out_name)

                to_save = aug_img
                if to_save.ndim == 2:
                    to_save = cv2.cvtColor(to_save, cv2.COLOR_GRAY2BGR)

                cv2.imwrite(out_path, to_save, [cv2.IMWRITE_JPEG_QUALITY, 95])
                samples_for_this_op += 1
                total_generated += 1

            # Mark this operation as complete in the result data
            result_data[op.name] = "complete"

        result_data["samples_generated"] = self.n_samples_per_op
        print(f"    Generated {total_generated} augmented images ({self.n_samples_per_op} per operation)")
        return result_data


def build_default_augmentation_ops(seed: int = 42) -> List[AugmentationOperation]:
    """
    Build default set of augmentation operations.

    Args:
        seed: Random seed for reproducibility

    Returns:
        List of AugmentationOperation instances
    """
    # Mild geometric + flip
    geom_mild = A.Compose([
        A.HorizontalFlip(p=0.5),
        A.VerticalFlip(p=0.2),
        A.RandomRotate90(p=0.5),
    ])

    # Stronger geometric + small shift/scale
    geom_strong = A.Compose([
        A.ShiftScaleRotate(
            shift_limit=0.05,
            scale_limit=0.15,
            rotate_limit=25,
            border_mode=cv2.BORDER_REFLECT_101,
            p=1.0,
        )
    ])

    # Intensity / contrast
    intensity = A.Compose([
        A.OneOf([
            A.CLAHE(clip_limit=2.0, tile_grid_size=(8, 8), p=1.0),
            A.RandomBrightnessContrast(0.2, 0.2, p=1.0),
            A.RandomGamma(gamma_limit=(80, 120), p=1.0),
        ], p=0.9),
        A.OneOf([
            A.GaussianBlur(blur_limit=(3, 7), p=1.0),
            A.MedianBlur(blur_limit=7, p=1.0),
        ], p=0.3),
    ])

    ops = [
        AugmentationOperation("geom_mild", geom_mild),
        AugmentationOperation("geom_strong", geom_strong),
        AugmentationOperation("intensity", intensity),
    ]

    return ops
