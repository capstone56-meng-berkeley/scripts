# Image Augmentation Script

Automated image augmentation tool with Google Drive integration and local file support.

## Features

- **Dual Mode Operation**:
  - Google Drive: Download from Drive, process, upload results
  - Local: Process files from local directories or zip files
- **Smart State Tracking**: Resume capability, prevents duplicate processing
- **Google Sheets Integration**: Automatically update spreadsheet with folder links
- **Multiple Augmentation Operations**: Geometric transforms, intensity adjustments, contrast changes
- **Flexible Configuration**: Environment variables, JSON file, or hardcoded
- **Automated Setup**: Bash wrapper handles venv and dependencies

## Quick Start

### 1. Setup

```bash
# Make the wrapper script executable
chmod +x run_augmenter.sh

# Run the script (it will create venv and install dependencies automatically)
./run_augmenter.sh
```

### 2. Configure

**Option A: Environment Variables (Highest Priority)**

```bash
export INPUT_FOLDER_ID="1VScZDE8q1xdHIq1kY588uT-detAMDfei"
export OUTPUT_FOLDER_ID="1NK1qtldoJAmYqhSoWQi8e1ZPgMDr5dzD"
export N_SAMPLES_PER_OP=3
export MAX_FILES_TO_PROCESS=10

./run_augmenter.sh
```

**Option B: JSON Configuration File**

```bash
# Copy the example config
cp config.json.example config.json

# Edit config.json with your settings
nano config.json

# Run
./run_augmenter.sh
```

**Option C: Direct Python Script**

```bash
# Edit augumenter.py and modify the hardcoded config section
python3 augumenter.py
```

## Configuration Options

### Google Drive Mode

| Variable/Key | Description | Example |
|--------------|-------------|---------|
| `INPUT_FOLDER_ID` | Google Drive folder ID with input images | `1VScZDE8q...` |
| `OUTPUT_FOLDER_ID` | Google Drive folder ID for results | `1NK1qtl...` |
| `CREDENTIALS_PATH` | Path to OAuth credentials | `credentials.json` |
| `TOKEN_PATH` | Path to token file (auto-created) | `token.json` |

### Local Mode

| Variable/Key | Description | Example |
|--------------|-------------|---------|
| `LOCAL_INPUT_PATH` | Path to local folder or zip file | `/path/to/images` |
| `LOCAL_OUTPUT_PATH` | Path to output folder | `/path/to/output` |

### Augmentation Settings

| Variable/Key | Description | Default |
|--------------|-------------|---------|
| `N_SAMPLES_PER_OP` | Samples per augmentation operation | `2` |
| `MAX_FILES_TO_PROCESS` | Limit files to process (None = all) | `None` |
| `SEED` | Random seed for reproducibility | `42` |
| `TEMP_DIR` | Temporary working directory | `./temp_augmentation` |

### Google Sheets Integration (Optional)

| Variable/Key | Description | Example |
|--------------|-------------|---------|
| `SHEET_ID` | Google Sheets spreadsheet ID | `1Mo0E67d...` |
| `SHEET_WORKSHEET` | Worksheet name | `database worksheet` |
| `SHEET_ID_COLUMN` | Column letter for image IDs | `A` |
| `SHEET_AUGMENTED_COLUMN` | Column letter for augmented folder links | `E` |

When configured, the script will automatically update your Google Sheet with links to the augmented image folders in Google Drive. The script matches image IDs using the specified column letter (e.g., column A) and writes folder links to another column (e.g., column E).

## Google Drive Setup

### 1. Create OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable **Google Drive API** and **Google Sheets API** (if using Google Sheets integration)
4. Create **OAuth 2.0 credentials** (Desktop app)
5. Download as `credentials.json`
6. Place in the same directory as the script

### 2. Get Folder IDs

- Open folder in Google Drive
- Copy ID from URL: `https://drive.google.com/drive/folders/{FOLDER_ID}`

### 3. Get Google Sheets ID (Optional)

If you want to automatically update a Google Sheet with augmented folder links:
- Open your Google Sheet
- Copy ID from URL: `https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit`
- Configure the columns:
  - Set `SHEET_ID_COLUMN` to the column letter containing image IDs (default: "A")
  - Set `SHEET_AUGMENTED_COLUMN` to the column letter for folder links (default: "E")
  - Set `SHEET_WORKSHEET` to your worksheet name (default: "database worksheet")

## Example Workflows

### Process 10 images from Google Drive

```bash
export INPUT_FOLDER_ID="1VScZDE8q1xdHIq1kY588uT-detAMDfei"
export OUTPUT_FOLDER_ID="1NK1qtldoJAmYqhSoWQi8e1ZPgMDr5dzD"
export MAX_FILES_TO_PROCESS=10
export N_SAMPLES_PER_OP=3

./run_augmenter.sh
```

### Process images and update Google Sheet

```bash
export INPUT_FOLDER_ID="1VScZDE8q1xdHIq1kY588uT-detAMDfei"
export OUTPUT_FOLDER_ID="1NK1qtldoJAmYqhSoWQi8e1ZPgMDr5dzD"
export SHEET_ID="1Mo0E67dV8eORdZpqwsbJVxVCoFc5kYwKGiXCvSCD-p0"
export SHEET_WORKSHEET="database worksheet"
export SHEET_ID_COLUMN="A"           # Column with image IDs
export SHEET_AUGMENTED_COLUMN="E"    # Column for folder links
export N_SAMPLES_PER_OP=3

./run_augmenter.sh
```

### Process all images from local zip file

```bash
export LOCAL_INPUT_PATH="/path/to/images.zip"
export LOCAL_OUTPUT_PATH="/path/to/output"
export N_SAMPLES_PER_OP=5

./run_augmenter.sh
```

### Resume interrupted processing

```bash
# State file tracks progress automatically
# Just run again with same config - it will skip completed images
./run_augmenter.sh
```

## File Structure

```
scripts/
├── augumenter.py           # Main Python script
├── run_augmenter.sh        # Bash wrapper (auto-setup)
├── requirements.txt        # Python dependencies
├── config.json.example     # Example configuration
├── config.json            # Your configuration (git-ignored)
├── credentials.json       # Google OAuth credentials (git-ignored)
├── token.json            # Auto-generated OAuth token (git-ignored)
└── README.md             # This file
```

## Output Structure

### Google Drive Mode
```
Output Folder/
├── augmentation_state.csv  # Progress tracking
├── image1/
│   ├── geom_mild__abc123__20250116.jpg
│   ├── geom_strong__def456__20250116.jpg
│   └── intensity__ghi789__20250116.jpg
└── image2/
    └── ...
```

### Local Mode
```
/path/to/output/
├── augmentation_state.csv
├── image1/
│   ├── geom_mild__abc123__20250116.jpg
│   └── ...
└── image2/
    └── ...
```

## State Tracking

The `augmentation_state.csv` file tracks which operations have been applied:

```csv
image_id,geom_mild,geom_strong,intensity
image1,3,3,3
image2,3,0,0
```

- Each row = one image
- Each column = one operation
- Numbers = samples generated
- Automatically synced to Google Drive

## Troubleshooting

### "No configuration found"
- Create `config.json` or set environment variables
- See examples above

### "credentials.json not found"
- Download OAuth credentials from Google Cloud Console
- Place in script directory

### "Image has N channels" warning
- Script auto-converts RGBA → RGB
- Check if images are corrupted

### Virtual environment issues
```bash
# Remove and recreate
rm -rf venv/
./run_augmenter.sh
```

## Dependencies

- Python 3.7+
- google-auth
- google-auth-oauthlib
- google-api-python-client
- opencv-python
- albumentations
- numpy

All installed automatically by `run_augmenter.sh`

## License

See project root for license information.
