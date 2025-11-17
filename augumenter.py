# -*- coding: utf-8 -*-
"""
Image Augmentation Script with Google Drive and Local File Support

This script supports two modes:

MODE 1 - Google Drive:
  1. Downloads images from a Google Drive folder
  2. Processes them with various augmentation operations
  3. Uploads the augmented images individually back to Google Drive folder
     (preserves folder structure for organized results)
  4. Optionally updates a Google Sheet with links to augmented folders

MODE 2 - Local Files:
  1. Reads images from a local folder or zip file
  2. Processes them with various augmentation operations
  3. Saves augmented images to a local output folder

Features:
  - Multiple augmentation operations (geometric, intensity, contrast)
  - Smart state tracking with CSV file (augmentation_state.csv)
    * Tracks which operations have been applied to each image
    * Prevents duplicate processing when re-running
    * Synced to Google Drive for persistent state across runs
  - Google Sheets integration (optional)
    * Automatically updates spreadsheet with augmented folder links
    * Matches by image ID and updates "Augumented_Data" column
  - Configurable limit on number of files to process
  - Support for various image formats (JPEG, PNG, TIFF, BMP)
  - Handles RGBA/PNG images with transparency
  - Preserves folder structure when uploading to Google Drive
  - Resume capability - can safely re-run without duplicating work

Setup:
1. Install required packages:
   pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client gspread opencv-python albumentations numpy

2. For Google Drive mode (optional):
   - Go to https://console.cloud.google.com/
   - Create a new project or select existing
   - Enable Google Drive API and Google Sheets API
   - Create OAuth 2.0 credentials (Desktop app)
   - Download credentials.json and place it in the same directory as this script

3. Configure at the bottom of this script:
   - For Google Drive: Set input_folder_id and output_folder_id
   - For Local: Set local_input_path and local_output_path
   - For Google Sheets (optional): Set sheet_id and sheet_worksheet

Usage:
   python augumenter.py
"""

# --- imports ---
import os
import io
import uuid
import zipfile
import shutil
import json
import sys
from glob import glob
from dataclasses import dataclass
from typing import List, Sequence, Optional
from datetime import datetime
import csv

import cv2
import numpy as np
import albumentations as A

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

# --- constants ---
EXTS = [".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"]
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets'
]


def is_image(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in EXTS


def list_images(root: str) -> List[str]:
    files = []
    for ext in EXTS:
        files.extend(glob(os.path.join(root, f"*{ext}")))
        files.extend(glob(os.path.join(root, f"*{ext.upper()}")))
    files.sort()
    return files


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def load_config_from_env_or_json() -> dict:
    """
    Load configuration from environment variables or JSON file.
    Environment variables take priority over JSON file.

    Returns:
        dict: Configuration dictionary
    """
    config = {}

    # Check for JSON config file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.join(script_dir, 'config.json')

    if os.path.exists(config_file):
        print(f"Loading configuration from {config_file}")
        with open(config_file, 'r') as f:
            json_config = json.load(f)

            # Flatten nested structure for easier access
            if 'google_drive_mode' in json_config:
                config.update(json_config['google_drive_mode'])
            if 'local_mode' in json_config:
                config.update(json_config['local_mode'])
            if 'google_sheets_integration' in json_config:
                config.update(json_config['google_sheets_integration'])
            if 'augmentation_settings' in json_config:
                config.update(json_config['augmentation_settings'])

    # Environment variables override JSON config
    env_mappings = {
        'INPUT_FOLDER_ID': 'input_folder_id',
        'OUTPUT_FOLDER_ID': 'output_folder_id',
        'LOCAL_INPUT_PATH': 'local_input_path',
        'LOCAL_OUTPUT_PATH': 'local_output_path',
        'N_SAMPLES_PER_OP': 'n_samples_per_op',
        'MAX_FILES_TO_PROCESS': 'max_files_to_process',
        'SEED': 'seed',
        'TEMP_DIR': 'temp_dir',
        'CREDENTIALS_PATH': 'credentials_path',
        'TOKEN_PATH': 'token_path',
        'SHEET_ID': 'sheet_id',
        'SHEET_WORKSHEET': 'sheet_worksheet',
        'SHEET_ID_COLUMN': 'sheet_id_column',
        'SHEET_AUGMENTED_COLUMN': 'sheet_augmented_column',
    }

    for env_var, config_key in env_mappings.items():
        value = os.getenv(env_var)
        if value is not None:
            # Convert to appropriate type
            if config_key in ['n_samples_per_op', 'seed']:
                config[config_key] = int(value)
            elif config_key == 'max_files_to_process':
                config[config_key] = int(value) if value.lower() != 'none' else None
            else:
                config[config_key] = value

            if env_var in ['INPUT_FOLDER_ID', 'OUTPUT_FOLDER_ID', 'LOCAL_INPUT_PATH', 'LOCAL_OUTPUT_PATH']:
                print(f"Using {config_key} from environment variable")

    return config


# --------- Google Drive Integration ----------

class GoogleDriveClient:
    """Handles Google Drive authentication and file operations."""

    def __init__(self, credentials_path: str = 'credentials.json', token_path: str = 'token.json'):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = None
        self.sheets_service = None
        self.creds = None
        self._authenticate()

    def _authenticate(self):
        """Authenticate with Google Drive and Google Sheets APIs."""
        creds = None

        # Check if token.json exists (previously authenticated)
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)

        # If no valid credentials, authenticate
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(
                        f"Credentials file not found: {self.credentials_path}\n"
                        f"Please download OAuth 2.0 credentials from Google Cloud Console.\n"
                        f"See script header for setup instructions."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)

            # Save credentials for next run
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())

        self.creds = creds
        self.service = build('drive', 'v3', credentials=creds)
        self.sheets_service = build('sheets', 'v4', credentials=creds)
        print("✓ Authenticated with Google Drive and Sheets")

    def download_file(self, file_id: str, destination: str):
        """Download a file from Google Drive by file ID."""
        request = self.service.files().get_media(fileId=file_id)

        with io.FileIO(destination, 'wb') as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    print(f"  Download {int(status.progress() * 100)}%")

        print(f"  ✓ Downloaded to {destination}")

    def list_files_in_folder(self, folder_id: str, mime_type_filter: str = None):
        """List all files in a Google Drive folder."""
        query = f"'{folder_id}' in parents and trashed=false"

        if mime_type_filter:
            query += f" and mimeType='{mime_type_filter}'"

        results = self.service.files().list(
            q=query,
            pageSize=1000,
            fields="files(id, name, mimeType)"
        ).execute()

        return results.get('files', [])

    def download_images_from_folder(self, folder_id: str, destination_dir: str, max_files: Optional[int] = None):
        """Download all images from a Google Drive folder."""
        ensure_dir(destination_dir)

        # Get all files in the folder
        files = self.list_files_in_folder(folder_id)

        # Filter for images
        image_mime_types = [
            'image/jpeg', 'image/jpg', 'image/png',
            'image/tiff', 'image/bmp'
        ]

        image_files = [
            f for f in files
            if f.get('mimeType') in image_mime_types or
            any(f.get('name', '').lower().endswith(ext) for ext in EXTS)
        ]

        total_found = len(image_files)

        # Limit files if max_files is set
        if max_files is not None:
            image_files = image_files[:max_files]
            print(f"Found {total_found} images in folder, downloading first {len(image_files)}")
        else:
            print(f"Found {len(image_files)} images in folder")

        downloaded_files = []
        for idx, file in enumerate(image_files, start=1):
            file_id = file['id']
            file_name = file['name']
            destination = os.path.join(destination_dir, file_name)

            print(f"[{idx}/{len(image_files)}] Downloading: {file_name}")
            self.download_file(file_id, destination)
            downloaded_files.append(destination)

        return downloaded_files

    def upload_file(self, file_path: str, parent_folder_id: str, mime_type: str = None):
        """Upload a file to Google Drive."""
        file_name = os.path.basename(file_path)

        if mime_type is None:
            # Detect mime type based on extension
            ext = os.path.splitext(file_path)[1].lower()
            mime_types = {
                '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                '.png': 'image/png', '.tif': 'image/tiff',
                '.tiff': 'image/tiff', '.bmp': 'image/bmp',
                '.zip': 'application/zip'
            }
            mime_type = mime_types.get(ext, 'application/octet-stream')

        file_metadata = {
            'name': file_name,
            'parents': [parent_folder_id]
        }

        media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)

        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name'
        ).execute()

        return file.get('id')

    def create_folder(self, folder_name: str, parent_folder_id: str = None) -> str:
        """Create a folder in Google Drive."""
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }

        if parent_folder_id:
            file_metadata['parents'] = [parent_folder_id]

        folder = self.service.files().create(
            body=file_metadata,
            fields='id, name'
        ).execute()

        print(f"✓ Created folder: {folder_name} (ID: {folder.get('id')})")
        return folder.get('id')

    def find_folder_by_name(self, folder_name: str, parent_folder_id: str = None) -> Optional[str]:
        """Find a folder by name. Returns folder ID if found, None otherwise."""
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        if parent_folder_id:
            query += f" and '{parent_folder_id}' in parents"

        results = self.service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)'
        ).execute()

        files = results.get('files', [])
        return files[0]['id'] if files else None

    def update_sheet_with_folder_link(self, sheet_id: str, worksheet_name: str,
                                       image_id: str, folder_id: str,
                                       id_column: str = "A", augmented_column: str = "E"):
        """
        Update Google Sheet with augmented folder link.

        Args:
            sheet_id: Google Sheets spreadsheet ID
            worksheet_name: Name of the worksheet
            image_id: Image ID to match in the ID column
            folder_id: Google Drive folder ID to create link for
            id_column: Column letter for image IDs (e.g., "A", "B")
            augmented_column: Column letter for augmented folder links (e.g., "E")
        """
        try:
            # Read the ID column to find the matching row
            id_range = f"'{worksheet_name}'!{id_column}:{id_column}"
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range=id_range
            ).execute()

            values = result.get('values', [])

            if not values:
                print(f"[WARN] Column '{id_column}' in worksheet '{worksheet_name}' is empty")
                return

            # Find row with matching image ID (1-indexed, starting from row 1)
            row_index = None
            for idx, row in enumerate(values, start=1):
                if row and row[0] == image_id:
                    row_index = idx
                    break

            if row_index is None:
                print(f"[WARN] Image ID '{image_id}' not found in column '{id_column}' of worksheet '{worksheet_name}'")
                return

            # Generate folder link
            folder_link = f"https://drive.google.com/drive/folders/{folder_id}"

            # Update cell in augmented_column at the found row
            range_name = f"'{worksheet_name}'!{augmented_column}{row_index}"

            self.sheets_service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=range_name,
                valueInputOption='RAW',
                body={'values': [[folder_link]]}
            ).execute()

            print(f"  ✓ Updated sheet row {row_index} for '{image_id}': {folder_link}")

        except Exception as e:
            print(f"[WARN] Failed to update sheet for '{image_id}': {e}")


# --------- Configuration ----------

@dataclass
class AugmentConfig:
    """
    Configuration for the augmentation pipeline.

    Mode 1: Google Drive (set input_folder_id and output_folder_id)
    Mode 2: Local (set local_input_path and local_output_path)
    """
    # === Google Drive Configuration ===
    input_folder_id: Optional[str] = None    # Google Drive folder ID containing images
    output_folder_id: Optional[str] = None   # Google Drive folder ID for uploading results

    # === Local Configuration ===
    local_input_path: Optional[str] = None   # Local folder path or zip file path
    local_output_path: Optional[str] = None  # Local folder path for saving results

    # === Working Directories ===
    temp_dir: str = "./temp_augmentation"

    # === Augmentation Settings ===
    n_samples_per_op: int = 2  # Number of augmented samples per operation
    seed: int = 42
    max_files_to_process: Optional[int] = None  # Limit number of files (None = all)

    # === Google Drive Credentials ===
    credentials_path: str = "credentials.json"
    token_path: str = "token.json"

    # === Google Sheets Integration ===
    sheet_id: Optional[str] = None          # Google Sheets spreadsheet ID
    sheet_worksheet: str = "database worksheet"  # Worksheet name
    sheet_id_column: str = "A"              # Column for image IDs (e.g., "A", "B")
    sheet_augmented_column: str = "E"       # Column for augmented folder links (e.g., "E")

    @property
    def is_google_drive_mode(self) -> bool:
        """Check if using Google Drive mode."""
        return self.input_folder_id is not None

    @property
    def is_local_mode(self) -> bool:
        """Check if using local mode."""
        return self.local_input_path is not None

    @property
    def input_dir(self) -> str:
        """Get the input directory path."""
        if self.is_local_mode and os.path.isdir(self.local_input_path):
            return self.local_input_path
        return os.path.join(self.temp_dir, "input")

    @property
    def output_dir(self) -> str:
        """Get the output directory path."""
        if self.is_local_mode and self.local_output_path:
            return self.local_output_path
        return os.path.join(self.temp_dir, "output")

    def validate(self):
        """Validate configuration."""
        if self.is_google_drive_mode and self.is_local_mode:
            raise ValueError(
                "Cannot use both Google Drive and local modes. "
                "Set either (input_folder_id + output_folder_id) OR (local_input_path + local_output_path)"
            )

        if not self.is_google_drive_mode and not self.is_local_mode:
            raise ValueError(
                "Must specify input source. "
                "Set either (input_folder_id) for Google Drive OR (local_input_path) for local files"
            )

        if self.is_local_mode:
            if not os.path.exists(self.local_input_path):
                raise FileNotFoundError(f"Local input path does not exist: {self.local_input_path}")

            if not self.local_output_path:
                raise ValueError("local_output_path must be set when using local_input_path")

    def cleanup(self):
        """Remove temporary directories."""
        if os.path.exists(self.temp_dir):
            # Only clean temp dir, not user's local output
            if self.is_local_mode and self.local_output_path:
                # Don't delete if output is inside temp (user's custom location)
                if not self.local_output_path.startswith(self.temp_dir):
                    shutil.rmtree(self.temp_dir)
                    print(f"✓ Cleaned up temporary directory: {self.temp_dir}")
            else:
                shutil.rmtree(self.temp_dir)
                print(f"✓ Cleaned up temporary directory: {self.temp_dir}")


# --------- Operation interface ----------

class AugmentationOperation:
    """
    Base class: every augmentation operation must implement
    - .name (str)
    - .apply(image: np.ndarray, idx: int) -> np.ndarray
    """
    def __init__(self, name: str):
        self.name = name

    def apply(self, image: np.ndarray, idx: int) -> np.ndarray:
        raise NotImplementedError


class AlbumentationsOp(AugmentationOperation):
    """
    Wraps an albumentations.Compose as a modular operation.
    """
    def __init__(self, name: str, transform: A.Compose):
        super().__init__(name)
        self.transform = transform

    def apply(self, image: np.ndarray, idx: int) -> np.ndarray:
        return self.transform(image=image)["image"]


# ------------ Example ops ---------------

def build_default_ops(config: AugmentConfig) -> List[AugmentationOperation]:
    """
    Example set of operations. Replace/extend this with your
    microstructure-specific pipelines.
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

    ops: List[AugmentationOperation] = [
        AlbumentationsOp("geom_mild", geom_mild),
        AlbumentationsOp("geom_strong", geom_strong),
        AlbumentationsOp("intensity", intensity),
    ]
    return ops


class AugmentationDirector:
    def __init__(self, operations: Sequence[AugmentationOperation], config: AugmentConfig):
        self.operations = list(operations)
        self.config = config
        self.drive_client = None

        # names of operations = columns in the CSV
        self.op_names = [op.name for op in self.operations]

        # CSV state file: image_ids x operations
        self.state_path = os.path.join(self.config.output_dir, "augmentation_state.csv")
        self.state = {}  # dict: image_id -> {op_name: count}

    # ---------- CSV state helpers ----------

    def _download_state_from_drive(self):
        """Download existing state CSV from Google Drive if it exists."""
        if not self.config.is_google_drive_mode:
            return

        try:
            # Look for augmentation_state.csv in the output folder
            files = self.drive_client.list_files_in_folder(self.config.output_folder_id)
            state_file = None

            for file in files:
                if file['name'] == 'augmentation_state.csv':
                    state_file = file
                    break

            if state_file:
                print("Found existing augmentation_state.csv in Google Drive, downloading...")
                ensure_dir(self.config.output_dir)
                self.drive_client.download_file(state_file['id'], self.state_path)
                print(f"✓ Downloaded state file")
        except Exception as e:
            print(f"[INFO] Could not download state file: {e}")

    def _load_state(self):
        """Load existing state from CSV if it exists."""
        # For Google Drive mode, try to download state first
        if self.config.is_google_drive_mode:
            self._download_state_from_drive()

        if not os.path.exists(self.state_path):
            return

        with open(self.state_path, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                image_id = row["image_id"]
                self.state[image_id] = {}
                for op_name in self.op_names:
                    val = row.get(op_name, "0") or "0"
                    try:
                        self.state[image_id][op_name] = int(val)
                    except ValueError:
                        self.state[image_id][op_name] = 0

        # Print loaded state summary
        if self.state:
            print(f"Loaded state for {len(self.state)} previously processed images")

    def _save_state(self):
        """Write current state to CSV (image_ids x operations)."""
        ensure_dir(self.config.output_dir)

        fieldnames = ["image_id"] + self.op_names
        with open(self.state_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for image_id in sorted(self.state.keys()):
                row = {"image_id": image_id}
                for op_name in self.op_names:
                    row[op_name] = self.state[image_id].get(op_name, 0)
                writer.writerow(row)

    def _upload_state_to_drive(self):
        """Upload state CSV to Google Drive."""
        if not self.config.is_google_drive_mode:
            return

        if not os.path.exists(self.state_path):
            return

        try:
            # Check if state file already exists in Drive
            files = self.drive_client.list_files_in_folder(self.config.output_folder_id)
            existing_state_file = None

            for file in files:
                if file['name'] == 'augmentation_state.csv':
                    existing_state_file = file
                    break

            if existing_state_file:
                # Delete the old version
                print("Updating augmentation_state.csv in Google Drive...")
                self.drive_client.service.files().delete(fileId=existing_state_file['id']).execute()

            # Upload the new version
            self.drive_client.upload_file(
                self.state_path,
                self.config.output_folder_id,
                mime_type='text/csv'
            )
            print("✓ Uploaded augmentation_state.csv to Google Drive")
        except Exception as e:
            print(f"[WARN] Failed to upload state file: {e}")

    def _unique_id(self) -> str:
        return uuid.uuid4().hex[:12]

    # ---------- core processing ----------

    def process_image(self, img_path: str):
        img = cv2.imread(img_path, cv2.IMREAD_UNCHANGED)
        if img is None:
            print(f"[WARN] Failed to read: {img_path}")
            return

        # Normalize image to 3 channels (RGB) for consistency
        if img.ndim == 2:
            # Grayscale -> RGB
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        elif img.shape[2] == 4:
            # RGBA -> RGB (remove alpha channel)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        elif img.shape[2] != 3:
            print(f"[WARN] Unsupported image format with {img.shape[2]} channels: {img_path}")
            return

        base = os.path.splitext(os.path.basename(img_path))[0]
        out_dir = os.path.join(self.config.output_dir, base)
        ensure_dir(out_dir)

        # get / init state for this image
        counts = self.state.get(base, {op_name: 0 for op_name in self.op_names})

        operations_performed = 0
        operations_skipped = 0

        for op in self.operations:
            op_name = op.name

            # Check if this operation has already been completed for this image
            current_count = counts.get(op_name, 0)
            if current_count >= self.config.n_samples_per_op:
                # Already processed - skip this operation
                operations_skipped += 1
                continue

            # Calculate how many samples we still need to generate
            samples_needed = self.config.n_samples_per_op - current_count

            for i in range(samples_needed):
                aug_img = op.apply(img, idx=current_count + i)
                uid = self._unique_id()
                ts = datetime.now().strftime("%Y%m%dT%H%M%S")
                out_name = f"{op_name}__{uid}__{ts}.jpg"
                out_path = os.path.join(out_dir, out_name)

                to_save = aug_img
                if to_save.ndim == 2:
                    to_save = cv2.cvtColor(to_save, cv2.COLOR_GRAY2BGR)

                cv2.imwrite(out_path, to_save, [cv2.IMWRITE_JPEG_QUALITY, 95])

            # update count for this operation on this image
            counts[op_name] = self.config.n_samples_per_op
            operations_performed += 1

        # save updated counts for this image
        self.state[base] = counts
        self._save_state()

        # Upload state to Drive after each image (for incremental progress tracking)
        if self.config.is_google_drive_mode:
            self._upload_state_to_drive()

        if operations_skipped > 0:
            print(f"  '{base}': {operations_performed} new operations, {operations_skipped} already completed")
        else:
            total_new = operations_performed * self.config.n_samples_per_op
            print(f"  Processed '{base}': +{total_new} aug images → {out_dir}")

    def _verify_augmented_folders_exist(self):
        """
        Verify that augmented folders actually exist in Google Drive.
        Remove entries from state if their corresponding folders don't exist.
        This ensures we re-process images if their augmented folders were deleted.
        """
        if not self.config.is_google_drive_mode or not self.state:
            return

        print("Verifying augmented folders exist in Google Drive...")

        # Get all existing folders in the output directory
        existing_folders = self.drive_client.list_files_in_folder(
            self.config.output_folder_id,
            mime_type_filter='application/vnd.google-apps.folder'
        )
        existing_folder_names = {folder['name'] for folder in existing_folders}

        # Check each image in state
        images_to_reprocess = []
        for image_id in list(self.state.keys()):
            # Check if folder exists for this image
            if image_id not in existing_folder_names:
                # Folder doesn't exist - mark for reprocessing
                images_to_reprocess.append(image_id)
                del self.state[image_id]

        if images_to_reprocess:
            print(f"  Found {len(images_to_reprocess)} images with missing augmented folders")
            print(f"  These will be reprocessed: {', '.join(images_to_reprocess[:5])}{' ...' if len(images_to_reprocess) > 5 else ''}")
            # Save updated state
            self._save_state()
        else:
            print("  ✓ All augmented folders verified")

    def prepare_input(self):
        """Prepare input images (download from Drive or extract from local zip)."""
        print("\n=== Step 1: Prepare Input ===")

        if self.config.is_google_drive_mode:
            # Download from Google Drive
            ensure_dir(self.config.temp_dir)
            ensure_dir(self.config.input_dir)

            # Load state first to know which images have been processed
            self._load_state()

            # Verify that augmented folders actually exist (sync state with reality)
            self._verify_augmented_folders_exist()

            # Get all available images
            files = self.drive_client.list_files_in_folder(self.config.input_folder_id)

            # Filter for images
            image_mime_types = [
                'image/jpeg', 'image/jpg', 'image/png',
                'image/tiff', 'image/bmp'
            ]

            image_files = [
                f for f in files
                if f.get('mimeType') in image_mime_types or
                any(f.get('name', '').lower().endswith(ext) for ext in EXTS)
            ]

            total_available = len(image_files)

            # Filter out already fully processed images if max_files_to_process is set
            if self.config.max_files_to_process is not None:
                unprocessed_images = []
                for file in image_files:
                    file_name = file['name']
                    base_name = os.path.splitext(file_name)[0]

                    # Check if this image is fully processed
                    if base_name in self.state:
                        # Check if all operations are complete
                        counts = self.state[base_name]
                        all_complete = all(
                            counts.get(op_name, 0) >= self.config.n_samples_per_op
                            for op_name in self.op_names
                        )
                        if all_complete:
                            continue  # Skip this image, it's fully processed

                    unprocessed_images.append(file)

                # Limit to max_files_to_process
                images_to_download = unprocessed_images[:self.config.max_files_to_process]

                if len(unprocessed_images) < len(image_files):
                    print(f"Found {total_available} images in folder ({total_available - len(unprocessed_images)} already fully processed)")
                else:
                    print(f"Found {total_available} images in folder")

                if len(images_to_download) < len(unprocessed_images):
                    print(f"Downloading first {len(images_to_download)} unprocessed images")
                else:
                    print(f"Downloading {len(images_to_download)} unprocessed images")
            else:
                # No limit, download all
                images_to_download = image_files
                print(f"Found {total_available} images in folder")

            # Download selected images
            downloaded_files = []
            for idx, file in enumerate(images_to_download, start=1):
                file_id = file['id']
                file_name = file['name']
                destination = os.path.join(self.config.input_dir, file_name)

                print(f"[{idx}/{len(images_to_download)}] Downloading: {file_name}")
                self.drive_client.download_file(file_id, destination)
                downloaded_files.append(destination)

            print(f"✓ Downloaded {len(downloaded_files)} images to {self.config.input_dir}")

        elif self.config.is_local_mode:
            # Handle local input
            if os.path.isfile(self.config.local_input_path):
                # Input is a zip file - extract it
                if self.config.local_input_path.endswith('.zip'):
                    print(f"Extracting zip file: {self.config.local_input_path}")
                    ensure_dir(self.config.input_dir)

                    with zipfile.ZipFile(self.config.local_input_path, 'r') as zip_ref:
                        zip_ref.extractall(self.config.input_dir)

                    print(f"✓ Extracted to {self.config.input_dir}")
                else:
                    raise ValueError(f"Unsupported file type: {self.config.local_input_path}. Only .zip files are supported.")

            elif os.path.isdir(self.config.local_input_path):
                # Input is already a folder
                print(f"Using local folder: {self.config.local_input_path}")
            else:
                raise FileNotFoundError(f"Local input path not found: {self.config.local_input_path}")

    def process_images(self):
        """Process all images with augmentations."""
        print("\n=== Step 2: Process Images ===")

        ensure_dir(self.config.output_dir)

        # Load state if not already loaded (for local mode)
        if not self.state and self.config.is_local_mode:
            self._load_state()

        # Find all images in input directory (including subdirectories)
        image_paths = []
        for root, dirs, files in os.walk(self.config.input_dir):
            for file in files:
                path = os.path.join(root, file)
                if is_image(path):
                    image_paths.append(path)

        image_paths.sort()
        total_found = len(image_paths)

        # For local mode with max_files_to_process, filter unprocessed images
        if self.config.is_local_mode and self.config.max_files_to_process is not None:
            unprocessed_paths = []
            for img_path in image_paths:
                base = os.path.splitext(os.path.basename(img_path))[0]

                # Check if fully processed
                if base in self.state:
                    counts = self.state[base]
                    all_complete = all(
                        counts.get(op_name, 0) >= self.config.n_samples_per_op
                        for op_name in self.op_names
                    )
                    if all_complete:
                        continue  # Skip fully processed images

                unprocessed_paths.append(img_path)

            # Limit to max_files_to_process
            image_paths = unprocessed_paths[:self.config.max_files_to_process]

            if len(unprocessed_paths) < total_found:
                print(f"Found {total_found} input images ({total_found - len(unprocessed_paths)} already fully processed)")
                print(f"Processing {len(image_paths)} unprocessed images")
            else:
                print(f"Found {total_found} input images, processing first {len(image_paths)}")
        else:
            print(f"Found {len(image_paths)} input images")

        for idx, img_path in enumerate(image_paths, start=1):
            print(f"[{idx}/{len(image_paths)}] {os.path.basename(img_path)}")
            self.process_image(img_path)

        print(f"✓ Processing complete")

    def save_results(self):
        """Save or upload augmented images."""
        print("\n=== Step 3: Save Results ===")

        if self.config.is_google_drive_mode:
            # Upload images individually to Google Drive
            print("Uploading augmented images to Google Drive...")

            # Collect all augmented images grouped by folder
            augmented_folders = {}
            for root, dirs, files in os.walk(self.config.output_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    if is_image(file_path):
                        # Get relative folder path
                        rel_path = os.path.relpath(file_path, self.config.output_dir)
                        folder_name = os.path.dirname(rel_path)

                        if folder_name not in augmented_folders:
                            augmented_folders[folder_name] = []
                        augmented_folders[folder_name].append(file_path)

            # Count total images
            total_images = sum(len(images) for images in augmented_folders.values())
            print(f"Found {total_images} augmented images in {len(augmented_folders)} folders to upload")

            # Track which folders we've created and their IDs
            created_folders = {}

            # Upload images folder by folder
            uploaded_count = 0
            current_image = 0

            for folder_name, images in sorted(augmented_folders.items()):
                # Get or create subfolder
                if folder_name:
                    subfolder_id = self.drive_client.find_folder_by_name(
                        folder_name,
                        self.config.output_folder_id
                    )

                    if not subfolder_id:
                        subfolder_id = self.drive_client.create_folder(
                            folder_name,
                            self.config.output_folder_id
                        )

                    target_folder_id = subfolder_id
                    created_folders[folder_name] = subfolder_id
                else:
                    target_folder_id = self.config.output_folder_id

                # Upload images in this folder
                for img_path in images:
                    current_image += 1
                    rel_path = os.path.relpath(img_path, self.config.output_dir)
                    print(f"[{current_image}/{total_images}] Uploading: {rel_path}")
                    self.drive_client.upload_file(img_path, target_folder_id)
                    uploaded_count += 1

            print(f"✓ Uploaded {uploaded_count} images to Google Drive")

            # Update Google Sheet with folder links
            if self.config.sheet_id and created_folders:
                print("\nUpdating Google Sheet with folder links...")
                for image_id, folder_id in created_folders.items():
                    self.drive_client.update_sheet_with_folder_link(
                        self.config.sheet_id,
                        self.config.sheet_worksheet,
                        image_id,
                        folder_id,
                        self.config.sheet_id_column,
                        self.config.sheet_augmented_column
                    )
                print(f"✓ Updated {len(created_folders)} rows in Google Sheet")

            # Upload final state file
            print("\nUploading final augmentation state...")
            self._upload_state_to_drive()

        elif self.config.is_local_mode:
            # Results are already saved to local_output_path
            print(f"✓ Results saved to: {self.config.output_dir}")

            # Count total augmented images
            total_images = sum(1 for root, dirs, files in os.walk(self.config.output_dir)
                             for file in files if is_image(os.path.join(root, file)))
            print(f"  Total augmented images: {total_images}")
            print(f"  State file: {self.state_path}")

    def run(self):
        """Main execution flow."""
        try:
            # Validate configuration
            self.config.validate()

            # Initialize Google Drive client if needed
            if self.config.is_google_drive_mode:
                print("=== Initializing Google Drive ===")
                self.drive_client = GoogleDriveClient(
                    credentials_path=self.config.credentials_path,
                    token_path=self.config.token_path
                )

            # Step 1: Prepare input (download or extract)
            self.prepare_input()

            # Step 2: Process images
            self.process_images()

            # Step 3: Save results (upload or local save)
            self.save_results()

            print("\n✓ All steps completed successfully!")

        except Exception as e:
            print(f"\n✗ Error: {e}")
            raise
        finally:
            # Cleanup temporary files
            print("\n=== Cleanup ===")
            self.config.cleanup()


# ------------ Main Configuration ------------

if __name__ == "__main__":
    """
    Two modes available:

    MODE 1 - Google Drive:
        Set input_folder_id and output_folder_id
        Downloads images from Google Drive, processes them, and uploads results back

    MODE 2 - Local:
        Set local_input_path (folder or .zip file) and local_output_path
        Processes local files and saves results to a local folder

    Configuration Priority (highest to lowest):
        1. Environment variables
        2. config.json file
        3. Hardcoded defaults below
    """

    # Load configuration from environment variables or JSON file
    loaded_config = load_config_from_env_or_json()

    # Create configuration with loaded values or defaults
    if loaded_config:
        config = AugmentConfig(
            input_folder_id=loaded_config.get('input_folder_id'),
            output_folder_id=loaded_config.get('output_folder_id'),
            local_input_path=loaded_config.get('local_input_path'),
            local_output_path=loaded_config.get('local_output_path'),
            n_samples_per_op=loaded_config.get('n_samples_per_op', 2),
            max_files_to_process=loaded_config.get('max_files_to_process'),
            seed=loaded_config.get('seed', 42),
            temp_dir=loaded_config.get('temp_dir', './temp_augmentation'),
            credentials_path=loaded_config.get('credentials_path', 'credentials.json'),
            token_path=loaded_config.get('token_path', 'token.json'),
            sheet_id=loaded_config.get('sheet_id'),
            sheet_worksheet=loaded_config.get('sheet_worksheet', 'database worksheet'),
            sheet_id_column=loaded_config.get('sheet_id_column', 'A'),
            sheet_augmented_column=loaded_config.get('sheet_augmented_column', 'E'),
        )
        print("✓ Configuration loaded successfully")
    else:
        # Fallback to hardcoded example (for backward compatibility)
        print("No configuration found, using hardcoded defaults")

        # === EXAMPLE 1: Google Drive Mode ===
        config_gdrive = AugmentConfig(
            # Google Drive settings
            input_folder_id="1VScZDE8q1xdHIq1kY588uT-detAMDfei",   # Your input folder ID
            output_folder_id="1NK1qtldoJAmYqhSoWQi8e1ZPgMDr5dzD", # Your output folder ID

            # Augmentation settings
            n_samples_per_op=3,                # Number of augmented samples per operation
            max_files_to_process=3,            # Limit files (None = all files)

            # Credentials
            credentials_path="credentials.json",
            token_path="token.json"
        )

        # === EXAMPLE 2: Local Mode - Folder Input ===
        config_local_folder = AugmentConfig(
            # Local settings
            local_input_path="/path/to/your/images/folder",  # Folder containing images
            local_output_path="/path/to/output/folder",      # Where to save results

            # Augmentation settings
            n_samples_per_op=3,
            max_files_to_process=None,  # Process all files
        )

        # === EXAMPLE 3: Local Mode - Zip File Input ===
        config_local_zip = AugmentConfig(
            # Local settings
            local_input_path="/path/to/your/images.zip",  # Zip file containing images
            local_output_path="/path/to/output/folder",   # Where to save results

            # Augmentation settings
            n_samples_per_op=3,
            max_files_to_process=10,  # Process only first 10 images
        )

        # Choose which config to use
        config = config_gdrive  # Change this to use different mode

    ops = build_default_ops(config)
    director = AugmentationDirector(ops, config)
    director.run()
