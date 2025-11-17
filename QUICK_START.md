# Quick Start Guide

## Basic Usage

### 1. Image Augmentation (Built-in)

```bash
# Simple augmentation
python process_files.py --operation augment --n-samples 3

# With Google Sheets tracking
export SHEET_ID="your-sheet-id"
python process_files.py --operation augment --n-samples 3
```

### 2. Custom Operations

```bash
# Image resize
python process_files.py --operation custom \
    --module examples.custom_operation_example.ImageResizeOperation

# Text processing
python process_files.py --operation custom \
    --module examples.custom_operation_example.TextFileProcessingOperation
```

## Configuration Modes

### Google Drive Mode

```bash
export INPUT_FOLDER_ID="1VScZDE8q..."
export OUTPUT_FOLDER_ID="1NK1qtl..."
python process_files.py --operation augment
```

### Local Mode

```bash
export LOCAL_INPUT_PATH="/path/to/images"
export LOCAL_OUTPUT_PATH="/path/to/output"
python process_files.py --operation augment
```

## Creating Custom Operations

1. Create a new Python file (e.g., `my_ops.py`):

```python
from lib.file_processor import FileOperation
from typing import List, Optional

class MyOperation(FileOperation):
    def __init__(self):
        super().__init__("my_op")

    def get_operation_columns(self) -> List[str]:
        return ["result", "status"]

    def process(self, input_path: str, output_dir: str,
                file_id: str) -> Optional[str]:
        # Your logic here
        print(f"Processing {file_id}")

        # Save results to output_dir
        # ...

        return output_dir  # or None if failed
```

2. Run it:

```bash
python process_files.py --operation custom --module my_ops.MyOperation
```

## Common Patterns

### Process Limited Files

```bash
export MAX_FILES_TO_PROCESS=10
python process_files.py --operation augment
```

### Custom Config File

```bash
python process_files.py --operation augment --config prod_config.json
```

### Google Sheets Tracking

```bash
export SHEET_ID="1Mo0E67dV8eORdZpqwsbJVxVCoFc5kYwKGiXCvSCD-p0"
export SHEET_WORKSHEET="database worksheet"
export SHEET_ID_COLUMN="A"
export SHEET_RESULT_COLUMN="E"
python process_files.py --operation augment
```

## See Also

- [README_MODULAR.md](README_MODULAR.md) - Full documentation
- [examples/custom_operation_example.py](examples/custom_operation_example.py) - Example operations
- [README.md](README.md) - Original augmentation script docs
