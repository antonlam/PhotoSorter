"""
Clear Folders: Removes all files from Import, Unwanted, and Wanted folders.

Usage:
    python clearFolders.py          # Interactive mode with confirmation
    python clearFolders.py confirm  # Force clear without confirmation
"""

import os
import sys
import shutil
from pathlib import Path


def clear_folder(folder_path, force=False):
    """
    Clear all files from a folder.
    
    Args:
        folder_path: Path to folder to clear
        force: If True, skip confirmation prompt
        
    Returns:
        Tuple of (success: bool, message: str, count: int)
    """
    folder_path = Path(folder_path)
    
    if not folder_path.exists():
        return False, f"Folder does not exist: {folder_path}", 0
    
    if not folder_path.is_dir():
        return False, f"Path is not a directory: {folder_path}", 0
    
    try:
        # Get list of files to delete
        files = list(folder_path.rglob('*'))
        file_count = len([f for f in files if f.is_file()])
        
        if file_count == 0:
            return True, f"Folder already empty: {folder_path}", 0
        
        # Ask for confirmation if not forced
        if not force:
            print(f"\n⚠ Found {file_count} file(s) in {folder_path}")
            response = input(f"Delete all files in {folder_path.name}? (yes/no): ").strip().lower()
            if response not in ('yes', 'y'):
                return False, f"Cancelled - no files deleted from {folder_path}", 0
        
        # Delete all files recursively
        deleted_count = 0
        for item in folder_path.rglob('*'):
            if item.is_file():
                try:
                    item.unlink()
                    deleted_count += 1
                except Exception as e:
                    print(f"  ✗ Failed to delete {item.name}: {str(e)}")
        
        # Remove empty subdirectories
        for item in sorted(folder_path.rglob('*'), reverse=True):
            if item.is_dir() and item != folder_path:
                try:
                    if not list(item.iterdir()):  # Only delete if empty
                        item.rmdir()
                except Exception:
                    pass
        
        return True, f"Deleted {deleted_count} file(s) from {folder_path}", deleted_count
        
    except Exception as e:
        return False, f"Error clearing {folder_path}: {str(e)}", 0


def main():
    """Main entry point for clearing folders."""
    # Determine if force mode
    force = len(sys.argv) > 1 and sys.argv[1].lower() in ('confirm', 'force', '1', 'yes')
    
    # Folders to clear
    folders = [
        './Import',
        './Unwanted',
        './Wanted'
    ]
    
    print("="*60)
    print("Clear Folders - Remove all files from Import/Unwanted/Wanted")
    print("="*60)
    
    total_deleted = 0
    total_errors = 0
    
    for folder in folders:
        success, message, count = clear_folder(folder, force=force)
        
        if success:
            status = "✓"
            total_deleted += count
            if count > 0:
                print(f"{status} {message}")
            else:
                print(f"{status} {message}")
        else:
            status = "✗"
            total_errors += 1
            print(f"{status} {message}")
    
    # Print summary
    print("\n" + "="*60)
    print("Summary:")
    print(f"  Total files deleted: {total_deleted}")
    print(f"  Errors: {total_errors}")
    print("="*60 + "\n")


if __name__ == '__main__':
    main()
