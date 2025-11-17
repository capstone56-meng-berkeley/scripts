"""Google Sheets client for tracking operations."""

from typing import Optional
from googleapiclient.discovery import build


class GoogleSheetsClient:
    """Handles Google Sheets operations for tracking file processing."""

    def __init__(self, credentials):
        """
        Initialize Google Sheets client.

        Args:
            credentials: Google OAuth2 credentials
        """
        self.sheets_service = build('sheets', 'v4', credentials=credentials)

    def update_cell(self, sheet_id: str, worksheet_name: str,
                   search_value: str, search_column: str,
                   update_column: str, update_value: str):
        """
        Update a cell in Google Sheet by finding a row and updating a column.

        Args:
            sheet_id: Google Sheets spreadsheet ID
            worksheet_name: Name of the worksheet
            search_value: Value to search for (e.g., file ID)
            search_column: Column letter to search in (e.g., "A")
            update_column: Column letter to update (e.g., "E")
            update_value: Value to write
        """
        try:
            # Read the search column to find the matching row
            search_range = f"'{worksheet_name}'!{search_column}:{search_column}"
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range=search_range
            ).execute()

            values = result.get('values', [])

            if not values:
                print(f"[WARN] Column '{search_column}' in worksheet '{worksheet_name}' is empty")
                return

            # Find row with matching value (1-indexed, starting from row 1)
            row_index = None
            for idx, row in enumerate(values, start=1):
                if row and row[0] == search_value:
                    row_index = idx
                    break

            if row_index is None:
                print(f"[WARN] Value '{search_value}' not found in column '{search_column}' of worksheet '{worksheet_name}'")
                return

            # Update cell in update_column at the found row
            range_name = f"'{worksheet_name}'!{update_column}{row_index}"

            self.sheets_service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=range_name,
                valueInputOption='RAW',
                body={'values': [[update_value]]}
            ).execute()

            print(f"  ✓ Updated sheet row {row_index} for '{search_value}': {update_value}")

        except Exception as e:
            print(f"[WARN] Failed to update sheet for '{search_value}': {e}")

    def batch_update_cells(self, sheet_id: str, worksheet_name: str,
                          updates: dict, search_column: str, update_column: str):
        """
        Batch update multiple cells in Google Sheet.

        Args:
            sheet_id: Google Sheets spreadsheet ID
            worksheet_name: Name of the worksheet
            updates: Dict mapping search_value -> update_value
            search_column: Column letter to search in
            update_column: Column letter to update
        """
        for search_value, update_value in updates.items():
            self.update_cell(
                sheet_id,
                worksheet_name,
                search_value,
                search_column,
                update_column,
                update_value
            )
