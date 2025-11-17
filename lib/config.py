"""Configuration management for file processing operations."""

import os
import json
from dataclasses import dataclass
from typing import Optional


def load_config_from_env_or_json(config_file: str = 'config.json') -> dict:
    """
    Load configuration from environment variables or JSON file.
    Environment variables take priority over JSON file.

    Args:
        config_file: Path to JSON configuration file

    Returns:
        dict: Configuration dictionary
    """
    config = {}

    # Check for JSON config file
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
            if 'processing_settings' in json_config:
                config.update(json_config['processing_settings'])

    # Environment variables override JSON config
    env_mappings = {
        'INPUT_FOLDER_ID': 'input_folder_id',
        'OUTPUT_FOLDER_ID': 'output_folder_id',
        'LOCAL_INPUT_PATH': 'local_input_path',
        'LOCAL_OUTPUT_PATH': 'local_output_path',
        'MAX_FILES_TO_PROCESS': 'max_files_to_process',
        'TEMP_DIR': 'temp_dir',
        'CREDENTIALS_PATH': 'credentials_path',
        'TOKEN_PATH': 'token_path',
        'SHEET_ID': 'sheet_id',
        'SHEET_WORKSHEET': 'sheet_worksheet',
        'SHEET_ID_COLUMN': 'sheet_id_column',
        'SHEET_RESULT_COLUMN': 'sheet_result_column',
    }

    for env_var, config_key in env_mappings.items():
        value = os.getenv(env_var)
        if value is not None:
            # Convert to appropriate type
            if config_key == 'max_files_to_process':
                config[config_key] = int(value) if value.lower() != 'none' else None
            else:
                config[config_key] = value

            if env_var in ['INPUT_FOLDER_ID', 'OUTPUT_FOLDER_ID', 'LOCAL_INPUT_PATH', 'LOCAL_OUTPUT_PATH']:
                print(f"Using {config_key} from environment variable")

    return config


@dataclass
class ProcessingConfig:
    """
    Configuration for file processing operations.

    Mode 1: Google Drive (set input_folder_id and output_folder_id)
    Mode 2: Local (set local_input_path and local_output_path)
    """
    # === Google Drive Configuration ===
    input_folder_id: Optional[str] = None    # Google Drive folder ID containing files
    output_folder_id: Optional[str] = None   # Google Drive folder ID for results

    # === Local Configuration ===
    local_input_path: Optional[str] = None   # Local folder path or zip file
    local_output_path: Optional[str] = None  # Local folder path for results

    # === Working Directories ===
    temp_dir: str = "./temp_processing"

    # === Processing Settings ===
    max_files_to_process: Optional[int] = None  # Limit number of files (None = all)

    # === Google Drive Credentials ===
    credentials_path: str = "credentials.json"
    token_path: str = "token.json"

    # === Google Sheets Integration ===
    sheet_id: Optional[str] = None          # Google Sheets spreadsheet ID
    sheet_worksheet: str = "database worksheet"  # Worksheet name
    sheet_id_column: str = "A"              # Column for file IDs
    sheet_result_column: str = "E"          # Column for result links

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
