#!/usr/bin/env python3
"""
Flexible File Processing Script

Process files from Google Drive or local storage with custom operations.
Supports Google Sheets tracking and state management.

Usage:
    python process_files.py --operation augment [options]
    python process_files.py --operation custom --module path.to.module [options]

Examples:
    # Run image augmentation
    python process_files.py --operation augment --n-samples 3

    # Run custom operation
    python process_files.py --operation custom --module my_ops.MyOperation
"""

import argparse
import sys
from lib.config import load_config_from_env_or_json, ProcessingConfig
from lib.file_processor import FileProcessor
from lib.augmentation_ops import ImageAugmentationOp, build_default_augmentation_ops


def run_augmentation(config: ProcessingConfig, n_samples: int = 2, seed: int = 42):
    """
    Run image augmentation operation.

    Args:
        config: ProcessingConfig instance
        n_samples: Number of samples per augmentation operation
        seed: Random seed
    """
    print("=== Image Augmentation Mode ===")

    # Build augmentation operations
    aug_ops = build_default_augmentation_ops(seed=seed)

    # Create augmentation file operation
    operation = ImageAugmentationOp(
        operations=aug_ops,
        n_samples_per_op=n_samples,
        seed=seed
    )

    # Run processor
    processor = FileProcessor(operation, config)
    processor.run()


def run_custom_operation(config: ProcessingConfig, module_path: str):
    """
    Run custom operation from a module.

    Args:
        config: ProcessingConfig instance
        module_path: Python module path (e.g., "my_module.MyOperation")
    """
    print(f"=== Custom Operation Mode: {module_path} ===")

    # Import custom operation
    try:
        parts = module_path.rsplit('.', 1)
        if len(parts) == 2:
            module_name, class_name = parts
            module = __import__(module_name, fromlist=[class_name])
            operation_class = getattr(module, class_name)
        else:
            raise ValueError(f"Invalid module path: {module_path}")

        # Instantiate operation
        operation = operation_class()

        # Run processor
        processor = FileProcessor(operation, config)
        processor.run()

    except Exception as e:
        print(f"Error loading custom operation: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Process files from Google Drive or local storage with custom operations"
    )

    parser.add_argument(
        '--operation',
        choices=['augment', 'custom'],
        required=True,
        help='Operation to run (augment=image augmentation, custom=custom module)'
    )

    parser.add_argument(
        '--module',
        type=str,
        help='Python module path for custom operation (e.g., "my_module.MyOperation")'
    )

    # Augmentation-specific options
    parser.add_argument(
        '--n-samples',
        type=int,
        default=2,
        help='Number of samples per augmentation operation (default: 2)'
    )

    parser.add_argument(
        '--seed',
        type=int,
        default=42,
        help='Random seed for reproducibility (default: 42)'
    )

    # Configuration file
    parser.add_argument(
        '--config',
        type=str,
        default='config.json',
        help='Path to configuration file (default: config.json)'
    )

    args = parser.parse_args()

    # Validate arguments
    if args.operation == 'custom' and not args.module:
        parser.error("--module is required when using --operation custom")

    # Load configuration
    loaded_config = load_config_from_env_or_json(args.config)

    if not loaded_config:
        print("Error: No configuration found")
        print("Please create config.json or set environment variables")
        sys.exit(1)

    config = ProcessingConfig(
        input_folder_id=loaded_config.get('input_folder_id'),
        output_folder_id=loaded_config.get('output_folder_id'),
        local_input_path=loaded_config.get('local_input_path'),
        local_output_path=loaded_config.get('local_output_path'),
        max_files_to_process=loaded_config.get('max_files_to_process'),
        temp_dir=loaded_config.get('temp_dir', './temp_processing'),
        credentials_path=loaded_config.get('credentials_path', 'credentials.json'),
        token_path=loaded_config.get('token_path', 'token.json'),
        sheet_id=loaded_config.get('sheet_id'),
        sheet_worksheet=loaded_config.get('sheet_worksheet', 'database worksheet'),
        sheet_id_column=loaded_config.get('sheet_id_column', 'A'),
        sheet_result_column=loaded_config.get('sheet_result_column', 'E'),
    )

    # Run operation
    if args.operation == 'augment':
        run_augmentation(config, n_samples=args.n_samples, seed=args.seed)
    elif args.operation == 'custom':
        run_custom_operation(config, args.module)


if __name__ == "__main__":
    main()
