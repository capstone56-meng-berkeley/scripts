"""
Example custom file operation.

This demonstrates how to create a custom operation that can be run
with the flexible file processor.
"""

import os
from typing import List, Optional
from lib.file_processor import FileOperation


class ImageResizeOperation(FileOperation):
    """
    Example operation: Resize images to multiple sizes.

    This demonstrates the FileOperation interface.
    """

    def __init__(self, sizes: List[tuple] = None):
        """
        Initialize resize operation.

        Args:
            sizes: List of (width, height) tuples for resizing
        """
        super().__init__("image_resize")
        self.sizes = sizes or [(256, 256), (512, 512), (1024, 1024)]

    def get_operation_columns(self) -> List[str]:
        """Get columns for state tracking."""
        return ["result", "status", "sizes_generated"]

    def process(self, input_path: str, output_dir: str, file_id: str) -> Optional[dict]:
        """
        Resize an image to multiple sizes.

        Args:
            input_path: Path to input image
            output_dir: Directory to save resized images
            file_id: Unique identifier for the file

        Returns:
            Dictionary with processing results, or None if failed
        """
        import cv2

        # Load image
        img = cv2.imread(input_path)
        if img is None:
            print(f"    [WARN] Failed to read: {input_path}")
            return None

        # Generate resized versions
        for width, height in self.sizes:
            resized = cv2.resize(img, (width, height))
            out_name = f"{file_id}_{width}x{height}.jpg"
            out_path = os.path.join(output_dir, out_name)
            cv2.imwrite(out_path, resized)

        print(f"    Generated {len(self.sizes)} resized versions")
        return {
            "result": output_dir,
            "sizes_generated": len(self.sizes)
        }


class TextFileProcessingOperation(FileOperation):
    """
    Example operation: Process text files (e.g., word count).

    This demonstrates processing non-image files.
    """

    def __init__(self):
        super().__init__("text_processing")

    def get_operation_columns(self) -> List[str]:
        """Get columns for state tracking."""
        return ["result", "status", "word_count", "line_count"]

    def process(self, input_path: str, output_dir: str, file_id: str) -> Optional[dict]:
        """
        Process a text file - count words and lines.

        Args:
            input_path: Path to input text file
            output_dir: Directory to save results
            file_id: Unique identifier for the file

        Returns:
            Dictionary with processing results, or None if failed
        """
        if not input_path.endswith(('.txt', '.md', '.py')):
            print(f"    Skipping non-text file: {input_path}")
            return None

        try:
            with open(input_path, 'r') as f:
                content = f.read()

            # Count words and lines
            word_count = len(content.split())
            line_count = len(content.splitlines())

            # Save statistics
            stats_path = os.path.join(output_dir, f"{file_id}_stats.txt")
            with open(stats_path, 'w') as f:
                f.write(f"File: {file_id}\n")
                f.write(f"Words: {word_count}\n")
                f.write(f"Lines: {line_count}\n")

            print(f"    Processed text file: {word_count} words, {line_count} lines")
            return {
                "result": output_dir,
                "word_count": word_count,
                "line_count": line_count
            }

        except Exception as e:
            print(f"    [WARN] Error processing text file: {e}")
            return None


# Example usage:
#
# python process_files.py --operation custom --module examples.custom_operation_example.ImageResizeOperation
# python process_files.py --operation custom --module examples.custom_operation_example.TextFileProcessingOperation
