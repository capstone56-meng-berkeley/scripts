# Architecture Overview

## Modular File Processing Framework

This framework provides a flexible, modular system for processing files from Google Drive or local storage with custom operations.

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    process_files.py                          │
│                   (Entry Point / CLI)                        │
└──────────────┬────────────────────────────────┬─────────────┘
               │                                │
               ├─ Built-in Operations           ├─ Custom Operations
               │  (ImageAugmentationOp)         │  (User-defined)
               │                                │
               ▼                                ▼
       ┌────────────────────────────────────────────────┐
       │          FileProcessor                         │
       │  (Orchestrates the processing workflow)        │
       └────────────────┬──────────────┬────────────────┘
                        │              │
           ┌────────────┴──┐     ┌─────┴────────┐
           │               │     │              │
           ▼               ▼     ▼              ▼
   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
   │ DriveClient  │  │SheetsClient │  │   Config     │
   │              │  │             │  │              │
   │ - Download   │  │ - Update    │  │ - Load from  │
   │ - Upload     │  │   cells     │  │   ENV/JSON   │
   │ - List files │  │ - Batch ops │  │ - Validate   │
   └──────────────┘  └──────────────┘  └──────────────┘
           │
           ▼
   ┌──────────────────────────────────────────┐
   │     Google Drive / Local Storage         │
   └──────────────────────────────────────────┘
```

## Core Components

### 1. FileOperation (Abstract Base Class)

**Purpose**: Interface for all file operations

**Key Methods**:
- `process(input_path, output_dir, file_id)` - Process single file
- `get_operation_columns()` - Define state tracking columns

**Implementations**:
- `ImageAugmentationOp` - Built-in image augmentation
- Custom operations - User-defined (e.g., resize, compress, analyze)

### 2. FileProcessor

**Purpose**: Orchestrates the processing workflow

**Responsibilities**:
- State management (CSV tracking)
- File download/upload (Google Drive mode)
- Local file discovery (Local mode)
- Result organization
- Google Sheets integration

**Workflow**:
```
1. prepare_input()
   ├─ Load state from CSV
   ├─ Verify existing results
   ├─ Download/locate unprocessed files
   └─ Apply max_files_to_process limit

2. process_files()
   ├─ For each file:
   │  ├─ Check if already processed
   │  ├─ Call operation.process()
   │  └─ Update state
   └─ Save state after each file

3. save_results()
   ├─ Upload results to Google Drive (if applicable)
   ├─ Update Google Sheets with links
   └─ Upload final state file
```

### 3. GoogleDriveClient

**Purpose**: Handle all Google Drive operations

**Features**:
- OAuth 2.0 authentication
- File download/upload
- Folder creation and search
- List files with filters

### 4. GoogleSheetsClient

**Purpose**: Update Google Sheets for tracking

**Features**:
- Find row by value in column
- Update specific cells
- Batch updates

### 5. ProcessingConfig

**Purpose**: Configuration management

**Sources** (in priority order):
1. Environment variables
2. JSON configuration file
3. Default values

## Data Flow

### Google Drive Mode

```
Input Drive Folder
       ↓
  [Download] ────────┐
       ↓             │
 Local Temp Files    │ State
       ↓             │ Tracking
  [Process]          │ (CSV)
       ↓             │
  Result Files       │
       ↓             │
  [Upload] ──────────┘
       ↓
Output Drive Folder
       ↓
  [Update Sheets]
       ↓
 Google Sheets (optional)
```

### Local Mode

```
Local Input Folder/Zip
       ↓
  [Extract/Locate] ──┐
       ↓             │
    Files            │ State
       ↓             │ Tracking
  [Process]          │ (CSV)
       ↓             │
  Result Files ──────┘
       ↓
Local Output Folder
```

## State Tracking

### processing_state.csv Format

```csv
file_id,result,status,operation_specific_columns...
image1,folder_xyz,completed,geom_mild,geom_strong,intensity
image2,/path/out,completed,3,3,3
```

**Columns**:
- `file_id`: Unique identifier (filename without extension)
- `result`: Output location (folder ID for Drive, path for local)
- `status`: Processing status (completed, failed, etc.)
- Additional columns defined by the operation

### State Synchronization (Google Drive Mode)

```
1. Start: Download processing_state.csv from Drive (if exists)
2. Before processing: Load state into memory
3. Verify: Check if result folders exist, remove stale entries
4. During processing: Update state after each file
5. End: Upload final processing_state.csv to Drive
```

## Extending the Framework

### Creating Custom Operations

```python
from lib.file_processor import FileOperation

class MyOperation(FileOperation):
    def __init__(self):
        super().__init__("operation_name")
        # Your initialization

    def get_operation_columns(self) -> List[str]:
        # Define additional columns for state tracking
        return ["result", "status", "my_metric"]

    def process(self, input_path, output_dir, file_id):
        # Your processing logic
        # Save results to output_dir
        # Return output_dir if successful, None if failed
        return output_dir
```

### Using Custom Operations

```bash
python process_files.py \
    --operation custom \
    --module path.to.module.MyOperation
```

## Configuration Structure

### JSON Configuration

```json
{
  "google_drive_mode": {
    "input_folder_id": "...",
    "output_folder_id": "...",
    "credentials_path": "credentials.json",
    "token_path": "token.json"
  },

  "local_mode": {
    "local_input_path": "/path/to/input",
    "local_output_path": "/path/to/output"
  },

  "google_sheets_integration": {
    "sheet_id": "...",
    "sheet_worksheet": "worksheet_name",
    "sheet_id_column": "A",
    "sheet_result_column": "E"
  },

  "processing_settings": {
    "max_files_to_process": null,
    "temp_dir": "./temp_processing"
  }
}
```

## Key Design Decisions

### 1. Separation of Concerns
- **Operations**: Define WHAT to do with files
- **Processor**: Define HOW to orchestrate processing
- **Clients**: Handle external service integration

### 2. Pluggable Architecture
- Operations implement a simple interface
- Easy to add new operations without modifying core code
- Supports both built-in and user-defined operations

### 3. State Management
- CSV-based for simplicity and portability
- Synced to Google Drive for persistence
- Allows resume capability

### 4. Flexible Configuration
- Multiple configuration sources
- Environment variables for CI/CD
- JSON files for complex setups
- Defaults for quick prototyping

## Benefits

1. **Modularity**: Easy to extend with new operations
2. **Reusability**: Core logic shared across all operations
3. **Flexibility**: Works with Google Drive or local files
4. **Tracking**: Built-in state management and Google Sheets integration
5. **Reliability**: Resume capability, duplicate prevention
6. **Simplicity**: Clean interfaces, easy to understand

## Migration Path

The original `augumenter.py` script remains available:

### Old Way
```bash
python augumenter.py
```

### New Way
```bash
python process_files.py --operation augment --n-samples 3
```

Both use the same `config.json` structure with minor naming changes.
