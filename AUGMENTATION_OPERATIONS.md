# Augmentation Operations Reference

## Overview

The augmentation system includes **14 operations** optimized for SEM microstructure images in materials science applications. All operations are enabled by default but can be selectively disabled via configuration.

## Complete Operation List

### 1. clahe - CLAHE Contrast Enhancement
- **Transform**: Contrast Limited Adaptive Histogram Equalization
- **Parameters**: `clip_limit=4.0`, `tile_grid_size=(8,8)`
- **Purpose**: Enhances local contrast critical for SEM images
- **Can disable**: Not recommended (essential for SEM)

### 2. brightness_contrast - Brightness & Contrast Variations
- **Transform**: RandomBrightnessContrast
- **Parameters**: `brightness_limit=0.2`, `contrast_limit=0.2`
- **Purpose**: Simulates different SEM imaging conditions
- **Can disable**: Not recommended (essential for SEM)

### 3. gamma - Gamma Correction
- **Transform**: RandomGamma
- **Parameters**: `gamma_limit=(80, 120)`
- **Purpose**: Non-linear brightness adjustments for detector response
- **Can disable**: Not recommended (essential for SEM)

### 4. iso_noise - Realistic SEM Noise
- **Transform**: OneOf(ISONoise, GaussNoise)
- **Parameters**: ISO: `intensity=(0.1, 0.3)`, Gauss: `var_limit=(10.0, 30.0)`
- **Purpose**: Simulates realistic SEM detector noise
- **Can disable**: Not recommended (essential for SEM)

### 5. rotate90 - 90° Rotations
- **Transform**: RandomRotate90
- **Parameters**: `p=1.0`
- **Purpose**: 0°, 90°, 180°, 270° rotations (microstructures are orientation-invariant)
- **Can disable**: Not recommended (essential for orientation invariance)

### 6. hflip - Horizontal Flip
- **Transform**: HorizontalFlip
- **Parameters**: `p=1.0`
- **Purpose**: Mirror horizontally (no inherent left/right)
- **Can disable**: Not recommended (essential for orientation invariance)

### 7. vflip - Vertical Flip
- **Transform**: VerticalFlip
- **Parameters**: `p=1.0`
- **Purpose**: Mirror vertically (no inherent top/bottom)
- **Can disable**: Not recommended (essential for orientation invariance)

### 8. geom_combined - Combined Geometric
- **Transform**: HorizontalFlip + VerticalFlip + RandomRotate90
- **Parameters**: All with `p=0.5`
- **Purpose**: Randomized combination of flips and rotations
- **Can disable**: Optional (adds diversity)

### 9. intensity_blur - Intensity + Blur
- **Transform**: OneOf(CLAHE, RandomBrightnessContrast) + OneOf(GaussianBlur, MedianBlur)
- **Parameters**: Milder than standalone operations
- **Purpose**: Combined intensity and slight blur variations
- **Can disable**: Optional (adds diversity)

### 10. shift_scale - Conservative Shift/Scale
- **Transform**: ShiftScaleRotate
- **Parameters**: `shift_limit=0.03`, `scale_limit=0.1`, `rotate_limit=0`
- **Purpose**: Very small spatial translations and scaling (no rotation)
- **Can disable**: Optional

### 11. elastic - Elastic Deformation
- **Transform**: ElasticTransform
- **Parameters**: `alpha=50`, `sigma=5`, `alpha_affine=0`
- **Purpose**: Mild material deformation simulation
- **Can disable**: Yes (use for specific use cases)

### 12. compression - JPEG Compression
- **Transform**: ImageCompression
- **Parameters**: `quality=75-95`, `type=JPEG`
- **Purpose**: Compression artifact simulation
- **Can disable**: Yes (use if images may be compressed)

### 13. downscale - Resolution Reduction
- **Transform**: Downscale
- **Parameters**: `scale=0.5-0.75`
- **Purpose**: Simulates different magnifications
- **Can disable**: Yes (use for multi-scale training)

### 14. dropout - Coarse Dropout
- **Transform**: CoarseDropout
- **Parameters**: `max_holes=3`, `max_size=32×32`
- **Purpose**: Random occlusions/missing regions
- **Can disable**: Yes (use for robustness testing)

## Disabling Operations

### Via Configuration File

Edit your `config.json` to disable specific operations:

```json
{
  "disabled_operations": ["elastic", "compression", "downscale", "dropout"]
}
```

### Common Configurations

**Minimal (Core only - 7 operations):**
```json
{
  "disabled_operations": [
    "geom_combined",
    "intensity_blur",
    "shift_scale",
    "elastic",
    "compression",
    "downscale",
    "dropout"
  ]
}
```

**Recommended (No extreme augmentations - 10 operations):**
```json
{
  "disabled_operations": [
    "elastic",
    "compression",
    "downscale",
    "dropout"
  ]
}
```

**Full (All operations - 14 operations):**
```json
{
  "disabled_operations": []
}
```

## Output Quantity

### With All 14 Operations:

| n_samples | Output per Input | Total for 10 Inputs | Total for 100 Inputs |
|-----------|------------------|---------------------|----------------------|
| 1         | 14 images        | 140 images          | 1,400 images         |
| 2         | 28 images        | 280 images          | 2,800 images         |
| 3         | 42 images        | 420 images          | 4,200 images         |
| 5         | 70 images        | 700 images          | 7,000 images         |

### With Core Only (7 operations):

| n_samples | Output per Input | Total for 10 Inputs | Total for 100 Inputs |
|-----------|------------------|---------------------|----------------------|
| 1         | 7 images         | 70 images           | 700 images           |
| 2         | 14 images        | 140 images          | 1,400 images         |
| 3         | 21 images        | 210 images          | 2,100 images         |
| 5         | 35 images        | 350 images          | 3,500 images         |

## Design Principles

### What's Included and Why

1. **CLAHE over basic contrast**: SEM images need adaptive local contrast
2. **90° rotations only**: Microstructures have no preferred orientation
3. **ISO noise**: Realistic SEM detector characteristics
4. **No arbitrary rotations**: Prevents grain boundary distortion
5. **Conservative shift/scale**: Minimal spatial distortion
6. **Elastic (mild)**: Very conservative parameters preserve features

### What's Excluded and Why

1. **Arbitrary angle rotations**: Can distort grain boundaries
2. **Heavy blur**: Destroys fine microstructure features
3. **Color operations**: SEM images are grayscale
4. **Weather effects**: Not relevant for microscopy
5. **Perspective transforms**: Inappropriate for flat samples
6. **Strong distortions**: Risk losing material features

## Usage Examples

### Basic Usage
```bash
# All 14 operations, 2 samples each = 28 outputs per input
./run_augmenter.sh --n-samples 2

# All 14 operations, 3 samples each = 42 outputs per input
./run_augmenter.sh --n-samples 3
```

### With Disabled Operations
```bash
# First, edit config.json to add disabled_operations
# Then run normally
./run_augmenter.sh --n-samples 3
```

### Recommended Settings

**For Testing:**
```bash
# Minimal operations, 1 sample each
# Edit config.json: "disabled_operations": ["geom_combined", "intensity_blur", "shift_scale", "elastic", "compression", "downscale", "dropout"]
./run_augmenter.sh --n-samples 1
# 7 outputs per input
```

**For Training (Balanced):**
```bash
# Recommended operations (no extreme augmentations)
# Edit config.json: "disabled_operations": ["elastic", "compression", "downscale", "dropout"]
./run_augmenter.sh --n-samples 2
# 20 outputs per input (10 operations × 2)
```

**For Training (Maximum Diversity):**
```bash
# All operations
# Edit config.json: "disabled_operations": []
./run_augmenter.sh --n-samples 3
# 42 outputs per input (14 operations × 3)
```

## File Naming Convention

Each augmented image follows this pattern:
```
<operation>__<uid>__<timestamp>.jpg
```

Examples:
- `clahe__a1b2c3d4e5f6__20250116T143022.jpg`
- `rotate90__f6e5d4c3b2a1__20250116T143023.jpg`
- `geom_combined__1a2b3c4d5e6f__20250116T143024.jpg`

## State Tracking

The `augmentation_state.csv` tracks:
- `file_id`: Original filename
- `status`: "completed"
- `result`: Output directory
- `samples_generated`: Samples per operation
- Individual operation columns: `clahe`, `brightness_contrast`, etc. (marked "complete")

## Performance Considerations

### Processing Time
- **Per operation**: ~1-3 seconds
- **Per image (14 ops, 3 samples)**: ~40-120 seconds
- **100 images (3 samples)**: ~1-2 hours

### Storage Requirements
- **Original dataset**: 100 images × 5 MB = 500 MB
- **With n_samples=2 (all ops)**: 2,800 images × 5 MB = 14 GB
- **With n_samples=3 (all ops)**: 4,200 images × 5 MB = 21 GB
- **With n_samples=3 (core only)**: 2,100 images × 5 MB = 10.5 GB

## Advanced Customization

### Adjusting Parameters

To modify operation parameters, edit the transforms in `lib/augmentation_ops.py`:

```python
# Example: Increase CLAHE clip limit
contrast_enhancement = A.Compose([
    A.CLAHE(clip_limit=6.0, tile_grid_size=(8, 8), p=1.0),  # Increased from 4.0
])

# Example: More conservative elastic deformation
elastic_deform = A.Compose([
    A.ElasticTransform(
        alpha=30,  # Reduced from 50
        sigma=3,   # Reduced from 5
        alpha_affine=0,
        p=1.0
    ),
])
```

## References

- Full transform catalog: [albumentations_transforms_catalog.md](albumentations_transforms_catalog.md)
- SEM-specific guide: [SEM_AUGMENTATION_GUIDE.md](SEM_AUGMENTATION_GUIDE.md)
- Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)
- General README: [README_MODULAR.md](README_MODULAR.md)
