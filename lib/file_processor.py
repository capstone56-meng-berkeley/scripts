"""Base file processor for running operations on files from Google Drive or local storage."""

import os
import shutil
import zipfile
import csv
import logging
from datetime import datetime
from abc import ABC, abstractmethod
from typing import List, Optional, Dict

from .config import ProcessingConfig
from .drive_client import GoogleDriveClient
from .sheets_client import GoogleSheetsClient


def ensure_dir(path: str):
    """Create directory if it doesn't exist."""
    os.makedirs(path, exist_ok=True)


class FileOperation(ABC):
    """
    Abstract base class for file operations.

    Subclass this to create custom operations that can be run
    on files from Google Drive or local storage.
    """

    def __init__(self, name: str):
        """
        Initialize operation.

        Args:
            name: Operation name (used for tracking)
        """
        self.name = name

    @abstractmethod
    def process(self, input_path: str, output_dir: str, file_id: str) -> Optional[dict]:
        """
        Process a single file.

        Args:
            input_path: Path to input file
            output_dir: Directory to save results
            file_id: Unique identifier for the file

        Returns:
            Optional[dict]: Dictionary with processing results (e.g., {"result": output_dir, "samples_generated": 9}),
                          or None if processing failed
        """
        pass

    @abstractmethod
    def get_operation_columns(self) -> List[str]:
        """
        Get list of operation-specific column names for state tracking.

        Returns:
            List of column names
        """
        pass


class FileProcessor:
    """
    Process files with custom operations from Google Drive or local storage.

    Supports:
    - Google Drive mode: Download, process, upload
    - Local mode: Process files from local directory
    - State tracking with CSV
    - Google Sheets integration (optional)
    """

    def __init__(self, operation: FileOperation, config: ProcessingConfig):
        """
        Initialize file processor.

        Args:
            operation: FileOperation instance to run on each file
            config: ProcessingConfig instance
        """
        self.operation = operation
        self.config = config
        self.drive_client: Optional[GoogleDriveClient] = None
        self.sheets_client: Optional[GoogleSheetsClient] = None

        # State tracking
        self.state_path = os.path.join(self.config.output_dir, "augmentation_state.csv")
        self.state: Dict[str, dict] = {}  # file_id -> {column: value}

        # Setup logging for warnings
        self._setup_logging()

    def _setup_logging(self):
        """Setup logging to save WARN and ERROR messages to file."""
        ensure_dir(self.config.output_dir)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = os.path.join(self.config.output_dir, f"warnings_{timestamp}.log")

        # Create logger
        self.logger = logging.getLogger('FileProcessor')
        self.logger.setLevel(logging.WARNING)

        # File handler for warnings/errors
        file_handler = logging.FileHandler(log_filename)
        file_handler.setLevel(logging.WARNING)

        # Formatter
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)

        print(f"Logging warnings to: {log_filename}")

    # ---------- State Management ----------

    def _download_state_from_drive(self):
        """Download existing state CSV from Google Drive if it exists."""
        if not self.config.is_google_drive_mode:
            return

        try:
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
            msg = f"Could not download state file: {e}"
            print(f"[INFO] {msg}")
            self.logger.info(msg)

    def _load_state(self):
        """Load existing state from CSV if it exists."""
        if self.config.is_google_drive_mode:
            self._download_state_from_drive()

        if not os.path.exists(self.state_path):
            return

        with open(self.state_path, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                file_id = row["file_id"]
                self.state[file_id] = {k: v for k, v in row.items() if k != "file_id"}

        if self.state:
            print(f"Loaded state for {len(self.state)} previously processed files")

    def _save_state(self):
        """Write current state to CSV."""
        ensure_dir(self.config.output_dir)

        fieldnames = ["file_id"] + self.operation.get_operation_columns()
        with open(self.state_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for file_id in sorted(self.state.keys()):
                row = {"file_id": file_id}
                row.update(self.state[file_id])
                writer.writerow(row)

    def _upload_state_to_drive(self):
        """Upload state CSV to Google Drive."""
        if not self.config.is_google_drive_mode:
            return

        if not os.path.exists(self.state_path):
            return

        try:
            files = self.drive_client.list_files_in_folder(self.config.output_folder_id)
            existing_state_file = None

            for file in files:
                if file['name'] == 'augmentation_state.csv':
                    existing_state_file = file
                    break

            if existing_state_file:
                print("Updating augmentation_state.csv in Google Drive...")
                self.drive_client.delete_file(existing_state_file['id'])

            self.drive_client.upload_file(
                self.state_path,
                self.config.output_folder_id,
                mime_type='text/csv'
            )
            print("✓ Uploaded augmentation_state.csv to Google Drive")
        except Exception as e:
            msg = f"Failed to upload state file: {e}"
            print(f"[WARN] {msg}")
            self.logger.warning(msg)

    def _verify_results_exist(self):
        """
        Verify that result folders actually exist in Google Drive.
        Remove entries from state if results don't exist.
        """
        if not self.config.is_google_drive_mode or not self.state:
            return

        print("Verifying results exist in Google Drive...")

        existing_folders = self.drive_client.list_files_in_folder(
            self.config.output_folder_id,
            mime_type_filter='application/vnd.google-apps.folder'
        )
        existing_folder_names = {folder['name'] for folder in existing_folders}

        files_to_reprocess = []
        for file_id in list(self.state.keys()):
            if file_id not in existing_folder_names:
                files_to_reprocess.append(file_id)
                del self.state[file_id]

        if files_to_reprocess:
            print(f"  Found {len(files_to_reprocess)} files with missing results")
            print(f"  These will be reprocessed: {', '.join(files_to_reprocess[:5])}{' ...' if len(files_to_reprocess) > 5 else ''}")
            self._save_state()
        else:
            print("  ✓ All results verified")

    # ---------- File Processing ----------

    def is_processed(self, file_id: str) -> bool:
        """Check if a file has already been processed."""
        return file_id in self.state

    def process_file(self, file_path: str, file_id: str):
        """
        Process a single file.

        Args:
            file_path: Path to input file
            file_id: Unique identifier for the file
        """
        if self.is_processed(file_id):
            print(f"  Skipping '{file_id}' (already processed)")
            return

        print(f"  Processing '{file_id}'...")

        output_dir = os.path.join(self.config.output_dir, file_id)
        ensure_dir(output_dir)

        # Run the operation
        result = self.operation.process(file_path, output_dir, file_id)

        if result is not None:
            # Mark as processed
            if isinstance(result, dict):
                # Operation returned dict with additional data
                self.state[file_id] = {"status": "completed", **result}
            else:
                # Operation returned just the result path (backwards compatibility)
                self.state[file_id] = {"result": result, "status": "completed"}

            self._save_state()

            if self.config.is_google_drive_mode:
                self._upload_state_to_drive()

            print(f"  ✓ Completed '{file_id}'")
        else:
            print(f"  ✗ Failed to process '{file_id}'")

    # ---------- Execution Flow ----------

    def prepare_input(self):
        """Prepare input files (download from Drive or use local files)."""
        print("\n=== Step 1: Prepare Input ===")

        if self.config.is_google_drive_mode:
            ensure_dir(self.config.temp_dir)
            ensure_dir(self.config.input_dir)

            self._load_state()
            self._verify_results_exist()

            # List files with image extension filter
            image_extensions = ['.jpg', '.jpeg', '.png']
            files = self.drive_client.list_files_in_folder(
                self.config.input_folder_id,
                file_extensions=image_extensions
            )

            total_available = len(files)

            # Filter out already processed files
            unprocessed_files = []
            for file in files:
                file_name = file['name']
                file_id_str = os.path.splitext(file_name)[0]

                # Check if already processed
                if file_id_str not in self.state:
                    unprocessed_files.append(file)

            # Apply max_files_to_process limit to unprocessed files
            if self.config.max_files_to_process is not None:
                files_to_download = unprocessed_files[:self.config.max_files_to_process]

                if len(unprocessed_files) < total_available:
                    print(f"Found {total_available} files in folder ({total_available - len(unprocessed_files)} already processed)")
                else:
                    print(f"Found {total_available} files in folder")

                if len(files_to_download) < len(unprocessed_files):
                    print(f"Downloading first {len(files_to_download)} unprocessed files")
                else:
                    print(f"Downloading {len(files_to_download)} unprocessed files")
            else:
                # No limit, download all unprocessed
                files_to_download = unprocessed_files
                print(f"Found {total_available} files in folder")
                print(f"Downloading {len(files_to_download)} unprocessed files")

            # Download selected files
            for idx, file in enumerate(files_to_download, start=1):
                file_id = file['id']
                file_name = file['name']
                destination = os.path.join(self.config.input_dir, file_name)

                print(f"[{idx}/{len(files_to_download)}] Downloading: {file_name}")
                self.drive_client.download_file(file_id, destination)

        elif self.config.is_local_mode:
            if os.path.isfile(self.config.local_input_path):
                if self.config.local_input_path.endswith('.zip'):
                    print(f"Extracting zip file: {self.config.local_input_path}")
                    ensure_dir(self.config.input_dir)

                    with zipfile.ZipFile(self.config.local_input_path, 'r') as zip_ref:
                        zip_ref.extractall(self.config.input_dir)

                    print(f"✓ Extracted to {self.config.input_dir}")
                else:
                    raise ValueError(f"Unsupported file type: {self.config.local_input_path}")
            elif os.path.isdir(self.config.local_input_path):
                print(f"Using local folder: {self.config.local_input_path}")
            else:
                raise FileNotFoundError(f"Local input path not found: {self.config.local_input_path}")

    def process_files(self):
        """Process all files."""
        print("\n=== Step 2: Process Files ===")

        ensure_dir(self.config.output_dir)

        if not self.state and self.config.is_local_mode:
            self._load_state()

        # Find all files
        file_paths = []
        for root, dirs, files in os.walk(self.config.input_dir):
            for file in files:
                path = os.path.join(root, file)
                file_paths.append(path)

        file_paths.sort()

        # Filter unprocessed if needed
        if self.config.is_local_mode and self.config.max_files_to_process is not None:
            unprocessed_paths = [
                p for p in file_paths
                if os.path.splitext(os.path.basename(p))[0] not in self.state
            ]
            file_paths = unprocessed_paths[:self.config.max_files_to_process]

        print(f"Found {len(file_paths)} files to process")

        for idx, file_path in enumerate(file_paths, start=1):
            file_id = os.path.splitext(os.path.basename(file_path))[0]
            print(f"[{idx}/{len(file_paths)}] {os.path.basename(file_path)}")
            self.process_file(file_path, file_id)

        print(f"✓ Processing complete")

    def save_results(self):
        """Save or upload results."""
        print("\n=== Step 3: Save Results ===")

        if self.config.is_google_drive_mode:
            print("Uploading results to Google Drive...")

            # Collect all result folders
            result_folders = {}
            for root, dirs, files in os.walk(self.config.output_dir):
                for dir_name in dirs:
                    folder_path = os.path.join(root, dir_name)
                    result_folders[dir_name] = folder_path

            # Upload folders
            created_folders = {}
            for file_id, folder_path in result_folders.items():
                subfolder_id = self.drive_client.find_folder_by_name(
                    file_id,
                    self.config.output_folder_id
                )

                if not subfolder_id:
                    subfolder_id = self.drive_client.create_folder(
                        file_id,
                        self.config.output_folder_id
                    )

                created_folders[file_id] = subfolder_id

                # Upload all files in this folder
                for file_name in os.listdir(folder_path):
                    file_path = os.path.join(folder_path, file_name)
                    if os.path.isfile(file_path):
                        self.drive_client.upload_file(file_path, subfolder_id)

            # Update Google Sheet
            if self.config.sheet_id and self.sheets_client and created_folders:
                print("\nUpdating Google Sheet...")
                for file_id, folder_id in created_folders.items():
                    folder_link = f"https://drive.google.com/drive/folders/{folder_id}"
                    self.sheets_client.update_cell(
                        self.config.sheet_id,
                        self.config.sheet_worksheet,
                        file_id,
                        self.config.sheet_id_column,
                        self.config.sheet_result_column,
                        folder_link
                    )

            self._upload_state_to_drive()

        elif self.config.is_local_mode:
            print(f"✓ Results saved to: {self.config.output_dir}")

    def run(self):
        """Main execution flow."""
        try:
            self.config.validate()

            if self.config.is_google_drive_mode:
                print("=== Initializing Google Drive ===")
                self.drive_client = GoogleDriveClient(
                    credentials_path=self.config.credentials_path,
                    token_path=self.config.token_path
                )
                if self.config.sheet_id:
                    self.sheets_client = GoogleSheetsClient(self.drive_client.creds)

            self.prepare_input()
            self.process_files()
            self.save_results()

            print("\n✓ All steps completed successfully!")

        except Exception as e:
            print(f"\n✗ Error: {e}")
            raise
        finally:
            if self.config.is_google_drive_mode and os.path.exists(self.config.temp_dir):
                shutil.rmtree(self.config.temp_dir)
                print(f"✓ Cleaned up temporary directory: {self.config.temp_dir}")
