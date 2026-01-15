# PhotoSorter

A professional Python application for automatically classifying and organizing images based on white background dominance analysis. Choose between a powerful command-line interface or an intuitive GUI application.

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
  - [Command Line Interface](#command-line-interface)
  - [GUI Application](#gui-application)
  - [Utility Scripts](#utility-scripts)
- [Configuration](#configuration)
- [Folder Structure](#folder-structure)
- [Advanced Features](#advanced-features)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)

## Features

### Core Functionality
✅ **Intelligent Image Classification** - Analyzes images and classifies them as "wanted" or "unwanted" based on white background percentage  
✅ **EXIF Date Renaming** - Automatically renames wanted images using EXIF DateTimeOriginal metadata  
✅ **Non-Image File Handling** - Automatically moves documents, PDFs, and other non-image files to the Wanted folder  
✅ **Recursive Scanning** - Processes images in nested folder structures  
✅ **Conflict Resolution** - Handles duplicate filenames with intelligent counter system  

### CLI Features
✅ **Named & Positional Parameters** - Flexible argument parsing (e.g., `rename=true verbose=false`)  
✅ **Rename Control** - Enable/disable EXIF date prefixing  
✅ **Verbose Logging** - Toggle detailed output or silent mode  
✅ **Real-time Statistics** - Processing summary with counts  

### GUI Features
✅ **Professional UI** - Modern Tkinter interface with multiple tabs  
✅ **Live Configuration** - All parameters configurable via intuitive controls  
✅ **Preview/Dry-Run** - Scan folders without moving files to preview results  
✅ **Real-time Processing** - Color-coded logging with live progress feedback  
✅ **Threading** - Non-blocking UI during image processing  
✅ **Config Persistence** - Save/load configurations as JSON  
✅ **Log Export** - Export processing logs to file  
✅ **Hotkeys** - Ctrl+R to run, Ctrl+S to save config  

### Utility Scripts
✅ **Folder Cleanup** - Clear Import, Unwanted, and Wanted folders with safety confirmations  

## Requirements

- **Python**: 3.10 or higher
- **Dependencies**:
  - `opencv-python` (cv2) - Image analysis
  - `Pillow` (PIL) - EXIF data extraction
  - `tkinter` - GUI (usually included with Python)

## Installation

### 1. Clone or Download the Repository
```bash
git clone <repository-url>
cd PhotoSorter
```

### 2. Install Dependencies
```bash
pip install opencv-python Pillow
```

Or using `uv` (recommended):
```bash
uv pip install opencv-python Pillow
```

### 3. Verify Installation
```bash
python -c "import cv2, PIL, tkinter; print('All dependencies installed!')"
```

## Quick Start

### Using the GUI (Recommended)
```bash
python photosorter_gui.py
```

The GUI will launch with default settings. Navigate to the Configuration tab, set your folders, and click "Start Processing".

### Using Command Line
```bash
# Default: import from ./Import, rename=true, verbose=true
python main.py

# Custom import path
python main.py ./MyImages

# With named parameters
python main.py ./MyImages rename=true verbose=false

# All parameters
python main.py ./MyImages rename=false verbose=true
```

## Usage

### Command Line Interface

#### Basic Usage
```bash
# Process images in default ./Import folder
python main.py
```

#### With Custom Path (Positional)
```bash
# Process images from specific folder
python main.py /path/to/images
```

#### With Named Parameters
```bash
# Disable renaming, enable verbose logging
python main.py ./Import rename=false verbose=true

# Enable renaming, disable logging (silent mode)
python main.py ./Import rename=true verbose=false

# Parameters can be in any order
python main.py rename=false verbose=false ./Import
```

#### Parameter Reference
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `import_path` | string | `./Import` | Path to folder with images to process |
| `rename` | boolean | `true` | Rename wanted images with EXIF date prefix |
| `verbose` | boolean | `true` | Show detailed processing information |

#### Expected Output
```
============================================================
Processing Summary:
  Wanted:          45
  Unwanted:        12
  Non-image files: 3
  Errors:          0
============================================================
```

---

### GUI Application

#### Launching
```bash
python photosorter_gui.py
```

#### Tabs Overview

**1. Configuration Tab**
- **Folders Section**: Set Import, Wanted, and Unwanted paths
- **Thresholds Section**: 
  - Resize Size (100-1000 pixels)
  - White Threshold (10-100%)
  - White Pixel Min RGB (0-255)
- **Processing Options**: 
  - Rename with EXIF date
  - Verbose logging
  - Recursive folder scan
- **Extensions**: Manage supported file formats
- **Buttons**: Save/Load/Reset configuration

**2. Preview Tab**
- Scan folders without moving files
- View estimated wanted/unwanted counts
- See detailed scan results

**3. Processing Tab**
- Start/Stop/Dry Run buttons
- Real-time progress bar
- Color-coded logging:
  - 🟢 Green = Wanted images
  - 🔴 Red = Unwanted images/errors
  - 🔵 Blue = Info messages
- Live statistics display
- Export log button

#### Workflow Example
1. Open GUI: `python photosorter_gui.py`
2. Go to **Configuration** tab
3. Click Browse to set Import folder
4. Adjust thresholds if needed
5. Click **Save Config** to persist settings
6. Go to **Preview** tab → Click **Scan Folders**
7. Review preview results
8. Go to **Processing** tab → Click **Start Processing**
9. Monitor real-time log and stats
10. Export log when complete

#### Keyboard Shortcuts
| Shortcut | Action |
|----------|--------|
| `Ctrl+R` | Start processing |
| `Ctrl+S` | Save configuration |

---

### Utility Scripts

#### Clear Folders

Remove all files from Import, Unwanted, and Wanted folders.

**Interactive Mode** (with confirmations):
```bash
python clearFolders.py
```

**Force Mode** (no confirmations):
```bash
python clearFolders.py confirm
python clearFolders.py force
```

**Output Example**:
```
✓ Deleted 45 file(s) from ./Import
✓ Deleted 12 file(s) from ./Unwanted
✓ Deleted 89 file(s) from ./Wanted

============================================================
Summary:
  Total files deleted: 146
  Errors: 0
============================================================
```

## Configuration

### Default Configuration
The first run creates `photosorter_config.json` with defaults:
```json
{
  "import_path": "./Import",
  "wanted_path": "./Wanted",
  "unwanted_path": "./Unwanted",
  "resize_size": 300,
  "white_threshold_percent": 70,
  "white_pixel_min": 240,
  "rename": true,
  "verbose": true,
  "recursive_scan": true,
  "supported_extensions": [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"],
  "non_image_handling": "Move to Wanted",
  "filename_conflict": "Counter"
}
```

### Customizing Configuration

**Via GUI**:
1. Adjust settings in Configuration tab
2. Click "Save Config" to persist

**Via JSON**:
1. Edit `photosorter_config.json`
2. Restart GUI or reload config

**Key Settings**:
- **white_threshold_percent**: Lower = more images classified as wanted (sensitive)
- **white_pixel_min**: Lower = considers more pixels as white
- **resize_size**: Larger = slower but potentially more accurate

## Folder Structure

```
PhotoSorter/
├── main.py                    # Core PhotoSorter class
├── photosorter_gui.py         # GUI application
├── clearFolders.py            # Utility to clear folders
├── photosorter_config.json    # Configuration (auto-generated)
├── README.md                  # This file
├── pyproject.toml             # Project metadata
│
├── Import/                    # Source folder (place images here)
├── Wanted/                    # Classified images without white background
└── Unwanted/                  # Classified images with white background
```

## Advanced Features

### White Background Analysis

**How It Works**:
1. Image is resized to 300x300 pixels (configurable)
2. Pixels with R, G, B all ≥ 240 (configurable) are considered white
3. White pixel percentage is calculated
4. If percentage > threshold (default 70%), image goes to Unwanted
5. Otherwise, image goes to Wanted

**Fine-tuning**:
- **Too many false positives (wanted in unwanted)?** → Lower white_threshold_percent
- **Too many false negatives (unwanted in wanted)?** → Raise white_threshold_percent
- **Sensitivity to near-white?** → Adjust white_pixel_min (lower = more sensitive)

### EXIF Date Renaming

If rename is enabled, wanted images are renamed with format:
```
YYYYMMDD_original_filename.jpg
Example: 20250115_photo.jpg
```

If image lacks EXIF data, original filename is preserved.

### Non-Image File Handling

Files that are NOT image formats (.txt, .pdf, .xlsx, etc.) are automatically moved to the Wanted folder. This prevents loss of important data.

### Conflict Resolution

If a file with the same name already exists:
1. **Counter Mode** (default): Appends counter (e.g., `photo_1.jpg`, `photo_2.jpg`)
2. **Overwrite Mode**: Replaces existing file

## Examples

### Example 1: Basic Processing
```bash
# Process images from ./Import with default settings
python main.py
```

### Example 2: Silent Mode (No Output)
```bash
# Process but don't print status messages
python main.py ./Import rename=true verbose=false
```

### Example 3: Dry Run Preview
```bash
# Via GUI: Go to Preview tab → Click "Scan Folders"
# Or via CLI dry-run simulation (see processing tab in GUI)
```

### Example 4: Batch Processing Multiple Folders
```bash
# Create script to process multiple folders
for folder in ./Batch1 ./Batch2 ./Batch3; do
  echo "Processing $folder..."
  python main.py "$folder" rename=true verbose=true
done
```

### Example 5: Automated Cleanup & Process
```bash
# Clear all folders, then process fresh batch
python clearFolders.py confirm
python main.py ./Import rename=true verbose=true
```

## Troubleshooting

### Issue: "Import folder not found"
**Solution**: Ensure the Import folder exists or specify correct path
```bash
# Create folders if they don't exist
mkdir Import Wanted Unwanted
```

### Issue: "No image files found"
**Solution**: Check that images are in correct folder with supported extensions
```bash
# Supported formats: .jpg, .jpeg, .png, .bmp, .tiff, .webp
```

### Issue: GUI doesn't launch
**Solution**: Verify tkinter is installed
```bash
python -m tkinter  # Should show a test window
```

### Issue: EXIF data not found for some images
**Solution**: This is normal. Images without EXIF data retain original names. Check verbose logging for details.

### Issue: Processing is slow
**Solution**: 
- Reduce `resize_size` in configuration
- Process fewer images at a time
- Check for corrupted images (they may timeout)

### Issue: Folder Permissions Error
**Solution**: Ensure you have write permissions to Import, Wanted, and Unwanted folders
```bash
# Linux/Mac
chmod 755 Import Wanted Unwanted

# Or run with appropriate privileges
```

## Performance Tips

- **Resize Size**: 300px is balanced for accuracy/speed. Reduce to 150-200 for faster processing.
- **Batch Processing**: Process large batches in groups to monitor progress.
- **SSD Storage**: Place folders on SSD for faster file operations.
- **Verbose Logging**: Disable in production for slight performance improvement.

## API Reference (For Developers)

### PhotoSorter Class

```python
from main import PhotoSorter

# Initialize
sorter = PhotoSorter(
    import_path='./Import',
    rename=True,
    verbose=True
)

# Modify thresholds
sorter.RESIZE_SIZE = 300
sorter.WHITE_THRESHOLD_PERCENT = 70
sorter.WHITE_PIXEL_MIN = 240
sorter.SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png'}

# Process images
sorter.process_images()

# Access statistics
print(sorter.stats)
# {'wanted': 45, 'unwanted': 12, 'errors': 0, 'non_image_files': 3}
```

## License

This project is provided as-is for personal and educational use.

## Support & Feedback

For issues or suggestions, please check:
1. Troubleshooting section above
2. Verify all dependencies are installed
3. Check configuration settings in GUI or JSON

---

**Version**: 1.0  
**Last Updated**: January 15, 2026  
**Python**: 3.10+
