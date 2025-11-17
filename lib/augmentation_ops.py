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
    Build comprehensive augmentation operations optimized for SEM microstructure images.

    These augmentations are designed for materials science applications where:
    - Images are grayscale (SEM)
    - Microstructures have no inherent orientation (rotation invariant)
    - Preserving material features (grain boundaries, phases) is critical
    - Realistic imaging variations (brightness, contrast, noise) are important

    This combines essential SEM-specific operations with general-purpose augmentations
    for maximum dataset diversity while preserving material features.

    Args:
        seed: Random seed for reproducibility

    Returns:
        List of AugmentationOperation instances (14 total operations)
    """
    # 1. Contrast enhancement (critical for SEM)
    contrast_enhancement = A.Compose([
        A.CLAHE(clip_limit=4.0, tile_grid_size=(8, 8), p=1.0),
    ])

    # 2. Brightness and contrast variations
    brightness_contrast = A.Compose([
        A.RandomBrightnessContrast(
            brightness_limit=0.2,
            contrast_limit=0.2,
            p=1.0
        ),
    ])

    # 3. Gamma correction (non-linear brightness)
    gamma_adjust = A.Compose([
        A.RandomGamma(gamma_limit=(80, 120), p=1.0),
    ])

    # 4. Realistic SEM noise
    sem_noise = A.Compose([
        A.OneOf([
            A.ISONoise(
                color_shift=(0.01, 0.05),
                intensity=(0.1, 0.3),
                p=1.0
            ),
            A.GaussNoise(
                var_limit=(10.0, 30.0),
                mean=0,
                per_channel=False,
                p=1.0
            ),
        ], p=1.0),
    ])

    # 5. Rotation invariance (microstructures have no preferred orientation)
    rotation_90 = A.Compose([
        A.RandomRotate90(p=1.0),
    ])

    # 6. Flips (orientation invariant)
    horizontal_flip = A.Compose([
        A.HorizontalFlip(p=1.0),
    ])

    vertical_flip = A.Compose([
        A.VerticalFlip(p=1.0),
    ])

    # 7. Elastic deformation (mild - simulates slight material deformation)
    elastic_deform = A.Compose([
        A.ElasticTransform(
            alpha=50,
            sigma=5,
            alpha_affine=0,
            p=1.0
        ),
    ])

    # 8. Image quality variations
    compression = A.Compose([
        A.ImageCompression(
            quality_lower=75,
            quality_upper=95,
            compression_type=A.ImageCompression.ImageCompressionType.JPEG,
            p=1.0
        ),
    ])

    # 9. Downscale (simulates different magnifications)
    downscale = A.Compose([
        A.Downscale(
            scale_min=0.5,
            scale_max=0.75,
            interpolation=cv2.INTER_LINEAR,
            p=1.0
        ),
    ])

    # 10. Coarse dropout (occlusions/artifacts)
    coarse_dropout = A.Compose([
        A.CoarseDropout(
            max_holes=3,
            max_height=32,
            max_width=32,
            min_holes=1,
            min_height=8,
            min_width=8,
            fill_value=0,
            p=1.0
        ),
    ])

    # 11. Combined geometric (mild - for additional diversity)
    geom_combined = A.Compose([
        A.HorizontalFlip(p=0.5),
        A.VerticalFlip(p=0.5),
        A.RandomRotate90(p=0.5),
    ])

    # 12. Intensity variations (mild blur + contrast)
    intensity_blur = A.Compose([
        A.OneOf([
            A.CLAHE(clip_limit=2.0, tile_grid_size=(8, 8), p=1.0),
            A.RandomBrightnessContrast(0.15, 0.15, p=1.0),
        ], p=0.9),
        A.OneOf([
            A.GaussianBlur(blur_limit=(3, 5), p=1.0),
            A.MedianBlur(blur_limit=5, p=1.0),
        ], p=0.3),
    ])

    # 13. Small shift/scale (very conservative for microstructures)
    shift_scale = A.Compose([
        A.ShiftScaleRotate(
            shift_limit=0.03,
            scale_limit=0.1,
            rotate_limit=0,  # No arbitrary rotations for microstructures
            border_mode=cv2.BORDER_REFLECT_101,
            p=1.0,
        )
    ])

    ops = [
        AugmentationOperation("clahe", contrast_enhancement),
        AugmentationOperation("brightness_contrast", brightness_contrast),
        AugmentationOperation("gamma", gamma_adjust),
        AugmentationOperation("iso_noise", sem_noise),
        AugmentationOperation("rotate90", rotation_90),
        AugmentationOperation("hflip", horizontal_flip),
        AugmentationOperation("vflip", vertical_flip),
        AugmentationOperation("geom_combined", geom_combined),
        AugmentationOperation("intensity_blur", intensity_blur),
        AugmentationOperation("shift_scale", shift_scale),
        AugmentationOperation("elastic", elastic_deform),
        AugmentationOperation("compression", compression),
        AugmentationOperation("downscale", downscale),
        AugmentationOperation("dropout", coarse_dropout),
    ]

    return ops
