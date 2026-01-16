# PhotoSorter

A professional Python application for automatically classifying and organizing images based on white background dominance analysis. Choose between a powerful command-line interface via `photoSorter.py` or the comprehensive GUI application `main.py`.

## Table of Contents

- [Overview](#overview)
- [Requirements](#requirements)
- [Installation](#installation)
- [main.py Usage](#mainpy-usage)
- [photoSorter.py CLI](#photosorterpy-cli)
- [Utility Scripts](#utility-scripts)
- [Configuration](#configuration)
- [How It Works](#how-it-works)
- [Folder Structure](#folder-structure)
- [Advanced Features](#advanced-features)
- [Keyboard Shortcuts](#keyboard-shortcuts)
- [Troubleshooting](#troubleshooting)

## Overview

**main.py** launches the PhotoSorter GUI, a thread-safe Tkinter application that provides full control over image organization. It integrates the core `photoSorter.py` logic with real-time previews, configurable thresholds, image viewers, and logging. The GUI supports dry-run scanning, live processing feedback, and persistent JSON configuration via `photosorter_config.json`.

Key workflow: Configure folders/thresholds → Preview results → Process images → Review in image tabs.

## Requirements

- **Python**: 3.10+
- **Dependencies**:
  | Package | Purpose |
  |---------|---------|
  | `opencv-python` | Image analysis (white pixel detection)|
  | `Pillow` (PIL) | Image resizing, EXIF reading  |
  | `tkinter` | GUI (bundled with most Python installs)|

## Installation

1. Place all files (`main.py`, `photoSorter.py`, etc.) in a project folder.
2. Install dependencies:
   ```bash
   pip install opencv-python Pillow
   ```
3. Verify:
   ```bash
   python -c "import cv2, PIL, tkinter; print('Ready!')"
   ```

## main.py Usage

**Launch the GUI**:
```bash
python main.py
```
The window opens at 1000x725px with tabs: **Configuration**, **Processing**, **Import**, **Wanted**, **Unwanted**.

### Step-by-Step Workflow

1. **Configuration Tab** (Scrollable with canvas):
   - **Folders**: Browse/set Import (source), Wanted (keepers), Unwanted (white-background rejects).
   - **Thresholds**:
     | Setting | Range/Default | Effect |
     |---------|---------------|--------|
     | Resize Size | 100-1000 / 300px | Balances speed/accuracy; larger = slower   |
     | White Threshold % | 10-100 / 70% | % white pixels to classify as unwanted   |
     | White Pixel Min RGB | 0-255 / 240 | Min RGB value counted as "white"   |
   - **Options**: Rename (EXIF prefix), Verbose, Recursive scan, Flatten Import (via `flattenFolder.py`), Extensions list.
   - Buttons: **Save Config** (to JSON), **Load Config**, **Reset**. 

2. **Preview/Dry-Run** (Processing Tab):
   - Click **Dry Run** to scan without moving files.
   - View stats: Wanted/Unwanted/Errors/Non-images.
   - Logs color-coded: Green (wanted), Red (unwanted/errors), Blue (info). 

3. **Processing**:
   - Click **Start Processing** (or Ctrl+R).
   - Progress bar, real-time stats/logs update via queue/threading.
   - **Stop** button halts thread safely.
   - **Export Log** saves colored output to .txt. 

4. **Image Viewer Tabs** (Import/Wanted/Unwanted):
   - Auto-loads thumbnails (supported: .jpg/.png/etc.) with navigation arrows.
   - Transfer buttons: Move images between folders (e.g., "Transfer to Wanted").
   - Keyboard: Arrow keys navigate current tab's images.

5. **Status Bar**: Shows current status (e.g., "Processing complete").

**Example Session**:
- Set Import to photos folder.
- Dry-run: "Found 150 images, 30 unwanted."
- Process: Files move; Wanted gets renamed like `20260116_photo.jpg`.
- Review Unwanted tab, transfer mistakes back.

## photoSorter.py CLI

For scripting:
```bash
python photoSorter.py ./Import  # Defaults: rename=true, verbose=true
python photoSorter.py ./Import rename=false verbose=false
```
Core logic used by GUI; outputs summary stats. 

## Utility Scripts

- **clearFolders.py**: `python clearFolders.py` (interactive delete from all folders). 
- **flattenFolder.py**: Flattens nested Import structure (auto-called if enabled). 

## Configuration

Auto-saves to `photosorter_config.json`:
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
  "flatten_import_folder": false
}
```
Edit manually or via GUI.

## How It Works

1. **Scan**: Recursive list of supported images/non-images. 
2. **Analyze**: Resize → Count white pixels (R/G/B ≥ threshold) → % white. 
3. **Classify**:
   - >Threshold % white → Unwanted.
   - Else → Wanted (rename if EXIF present: `YYYYMMDD_name.ext`).
   - Non-images → Wanted. 
4. **Handle Conflicts**: Append counter (e.g., `_1`). 
5. **Threading**: Worker thread prevents UI freeze; queue for log/stats. 

## Folder Structure

```
PhotoSorter/
├── main.py                 # GUI launcher
├── photoSorter.py          # Core classifier
├── flattenFolder.py        # Nested folder flattener
├── clearFolders.py         # Folder cleaner
├── photosorter_config.json # Settings
├── Import/                 # ← Drop images here
├── Wanted/                 # Keepers (renamed)
└── Unwanted/               # White-background rejects
```

## Advanced Features

- **Tooltips**: Hover controls for help. 
- **Print Capture**: Redirects `photoSorter.py` output to GUI log.
- **Non-blocking**: Daemon threads, stop events. 
- **Custom Extensions**: Edit in config. 

## Keyboard Shortcuts

| Key     | Action              |
|---------|---------------------|
| Ctrl+R  | Start Processing   |
| Ctrl+S  | Save Config        |
| Arrows  | Navigate images    | 

## Troubleshooting

- **No tkinter**: `python -m tkinter` test.
- **Slow**: Lower resize_size; check disk.
- **Permissions**: `chmod 755 *folders*`.
- **No EXIF**: Original name preserved.
- **Errors in log**: Corrupt images skipped. 

**Version**: 2.0  
**Updated**: January 16, 2026 