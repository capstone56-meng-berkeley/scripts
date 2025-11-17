##Flexible File Processing Framework

A modular Python framework for processing files from Google Drive or local storage with custom operations and optional Google Sheets tracking.

## Features

- **Modular Architecture**: Easily create custom file operations
- **Dual Mode Operation**:
  - Google Drive: Download, process, upload results
  - Local: Process files from local directories or zip files
- **Smart State Tracking**: Resume capability, prevents duplicate processing
- **Google Sheets Integration**: Automatically update spreadsheet with result links
- **Pluggable Operations**: Run arbitrary operations, not just augmentation
- **Flexible Configuration**: Environment variables, JSON file, or command-line args

## Quick Start

### 1. Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Configure (choose one method)
cp config.json.example config.json
# Edit config.json with your settings
```

### 2. Run Built-in Operations

```bash
# Image augmentation
python process_files.py --operation augment --n-samples 3

# With environment variables
export INPUT_FOLDER_ID="your-folder-id"
export OUTPUT_FOLDER_ID="your-output-folder-id"
python process_files.py --operation augment
```

### 3. Run Custom Operations

```bash
# Image resize operation
python process_files.py --operation custom --module examples.custom_operation_example.ImageResizeOperation

# Text processing operation
python process_files.py --operation custom --module examples.custom_operation_example.TextFileProcessingOperation
```

## Architecture

### Core Modules

```
lib/
├── __init__.py              # Package initialization
├── config.py                # Configuration management
├── drive_client.py          # Google Drive operations
├── sheets_client.py         # Google Sheets tracking
├── file_processor.py        # Base processor & FileOperation interface
└── augmentation_ops.py      # Built-in augmentation operations
```

### Creating Custom Operations

Extend the `FileOperation` base class:

```python
from lib.file_processor import FileOperation
from typing import List, Optional

class MyCustomOperation(FileOperation):
    def __init__(self):
        super().__init__("my_operation")

    def get_operation_columns(self) -> List[str]:
        """Define columns for state tracking."""
        return ["result", "status", "my_metric"]

    def process(self, input_path: str, output_dir: str, file_id: str) -> Optional[str]:
        """
        Process a single file.

        Args:
            input_path: Path to input file
            output_dir: Directory to save results
            file_id: Unique identifier for the file

        Returns:
            Output directory path if successful, None otherwise
        """
        # Your processing logic here
        # ...

        return output_dir  # or None if failed
```

Save this as `my_custom_ops.py` and run:

```bash
python process_files.py --operation custom --module my_custom_ops.MyCustomOperation
```

## Configuration

### Option 1: JSON Configuration File

```json
{
  "google_drive_mode": {
    "input_folder_id": "your-input-folder-id",
    "output_folder_id": "your-output-folder-id",
    "credentials_path": "credentials.json",
    "token_path": "token.json"
  },

  "google_sheets_integration": {
    "sheet_id": "your-sheet-id",
    "sheet_worksheet": "database worksheet",
    "sheet_id_column": "A",
    "sheet_result_column": "E"
  },

  "processing_settings": {
    "max_files_to_process": null,
    "temp_dir": "./temp_processing"
  }
}
```

### Option 2: Environment Variables

```bash
export INPUT_FOLDER_ID="your-folder-id"
export OUTPUT_FOLDER_ID="your-output-folder-id"
export SHEET_ID="your-sheet-id"
export SHEET_WORKSHEET="database worksheet"
export SHEET_ID_COLUMN="A"
export SHEET_RESULT_COLUMN="E"
export MAX_FILES_TO_PROCESS=10
```

### Option 3: Local Mode

```json
{
  "local_mode": {
    "local_input_path": "/path/to/your/files",
    "local_output_path": "/path/to/output/folder"
  },
  "processing_settings": {
    "max_files_to_process": null
  }
}
```

## Built-in Operations

### Image Augmentation

Applies geometric and intensity transformations to images.

```bash
python process_files.py --operation augment \
    --n-samples 3 \
    --seed 42
```

**Operations**:
- `geom_mild`: Horizontal/vertical flip, rotation
- `geom_strong`: Shift, scale, rotate
- `intensity`: CLAHE, brightness/contrast, gamma, blur

## Example Custom Operations

See `examples/custom_operation_example.py` for:

1. **ImageResizeOperation**: Resize images to multiple sizes
   ```bash
   python process_files.py --operation custom --module examples.custom_operation_example.ImageResizeOperation
   ```

2. **TextFileProcessingOperation**: Count words and lines in text files
   ```bash
   python process_files.py --operation custom --module examples.custom_operation_example.TextFileProcessingOperation
   ```

## Google Drive Setup

### 1. Create OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable **Google Drive API** and **Google Sheets API**
4. Create **OAuth 2.0 credentials** (Desktop app)
5. Download as `credentials.json`
6. Place in the scripts directory

### 2. Get Folder IDs

- Open folder in Google Drive
- Copy ID from URL: `https://drive.google.com/drive/folders/{FOLDER_ID}`

### 3. Get Google Sheets ID (Optional)

- Open your Google Sheet
- Copy ID from URL: `https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit`

## State Tracking

The framework automatically tracks:
- Which files have been processed
- Operation-specific metrics
- Results location (folder ID or path)

State is saved to `processing_state.csv`:
```csv
file_id,result,status,custom_metric
image1,/path/to/results,completed,42
image2,folder_id_xyz,completed,38
```

For Google Drive mode, the state file is synced to Drive.

## Google Sheets Integration

When configured, the framework:
1. Finds the row matching the file ID in the specified column
2. Updates the result column with a Google Drive folder link
3. Allows tracking all processed files in a central spreadsheet

## Advanced Usage

### Batch Processing with Limits

```bash
# Process only 10 files at a time
export MAX_FILES_TO_PROCESS=10
python process_files.py --operation augment
```

### Custom Configuration File

```bash
python process_files.py --operation augment --config my_config.json
```

### Combining Operations

Create a custom operation that combines multiple processing steps:

```python
class CombinedOperation(FileOperation):
    def __init__(self):
        super().__init__("combined")
        self.resize_op = ImageResizeOperation()
        self.augment_op = ImageAugmentationOp(...)

    def process(self, input_path, output_dir, file_id):
        # First resize
        resize_result = self.resize_op.process(input_path, output_dir, file_id)

        # Then augment
        if resize_result:
            return self.augment_op.process(input_path, output_dir, file_id)

        return None
```

## Migration from Original Script

The original `augumenter.py` remains available. To migrate to the modular system:

1. **Update config**: Rename `augmentation_settings` → `processing_settings`
2. **Update column names**: `sheet_augmented_column` → `sheet_result_column`
3. **Run command**: `python process_files.py --operation augment` instead of `python augumenter.py`

Both scripts are compatible with the same `config.json` structure.

## Troubleshooting

### "No configuration found"
- Create `config.json` or set environment variables
- See `config.json.example`

### "Module not found" (custom operations)
- Ensure your custom operation file is in the Python path
- Use dot notation: `my_folder.my_module.MyClass`

### Google Sheets API not enabled
- Visit [Google Cloud Console](https://console.cloud.google.com/)
- Enable Google Sheets API
- Delete `token.json` and re-authenticate

## Dependencies

```
google-auth>=2.23.0
google-auth-oauthlib>=1.1.0
google-auth-httplib2>=0.1.1
google-api-python-client>=2.100.0
opencv-python>=4.8.0
albumentations>=1.3.1
numpy>=1.24.0
```

## License

See project root for license information.
