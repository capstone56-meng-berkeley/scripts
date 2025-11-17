"""Google Drive client for file operations."""

import os
import io
from typing import List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets'
]


class GoogleDriveClient:
    """Handles Google Drive authentication and file operations."""

    def __init__(self, credentials_path: str = 'credentials.json', token_path: str = 'token.json'):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = None
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
                        f"See documentation for setup instructions."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)

            # Save credentials for next run
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())

        self.creds = creds
        self.service = build('drive', 'v3', credentials=creds)
        print("✓ Authenticated with Google Drive")

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

    def list_files_in_folder(self, folder_id: str, mime_type_filter: str = None,
                            exclude_google_docs: bool = True,
                            file_extensions: List[str] = None) -> List[dict]:
        """
        List all files in a Google Drive folder.

        Args:
            folder_id: Google Drive folder ID
            mime_type_filter: Optional MIME type filter
            exclude_google_docs: If True, exclude Google Docs/Sheets/Slides files
            file_extensions: Optional list of file extensions to filter (e.g., ['.jpg', '.png'])

        Returns:
            List of file dictionaries
        """
        query = f"'{folder_id}' in parents and trashed=false"

        if mime_type_filter:
            query += f" and mimeType='{mime_type_filter}'"

        if exclude_google_docs:
            # Exclude Google Workspace files (Docs, Sheets, Slides, etc.)
            google_mime_types = [
                'application/vnd.google-apps.document',
                'application/vnd.google-apps.spreadsheet',
                'application/vnd.google-apps.presentation',
                'application/vnd.google-apps.form',
                'application/vnd.google-apps.drawing',
                'application/vnd.google-apps.site'
            ]
            for gmt in google_mime_types:
                query += f" and mimeType!='{gmt}'"

        results = self.service.files().list(
            q=query,
            pageSize=1000,
            fields="files(id, name, mimeType)"
        ).execute()

        files = results.get('files', [])

        # Filter by file extensions if specified
        if file_extensions:
            # Normalize extensions to lowercase and ensure they start with '.'
            normalized_exts = [ext if ext.startswith('.') else f'.{ext}'
                             for ext in file_extensions]
            normalized_exts = [ext.lower() for ext in normalized_exts]

            files = [
                f for f in files
                if any(f['name'].lower().endswith(ext) for ext in normalized_exts)
            ]

        return files

    def upload_file(self, file_path: str, parent_folder_id: str, mime_type: str = None) -> str:
        """Upload a file to Google Drive."""
        file_name = os.path.basename(file_path)

        if mime_type is None:
            # Detect mime type based on extension
            ext = os.path.splitext(file_path)[1].lower()
            mime_types = {
                '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                '.png': 'image/png', '.tif': 'image/tiff',
                '.tiff': 'image/tiff', '.bmp': 'image/bmp',
                '.zip': 'application/zip', '.csv': 'text/csv'
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

    def delete_file(self, file_id: str):
        """Delete a file from Google Drive."""
        self.service.files().delete(fileId=file_id).execute()
