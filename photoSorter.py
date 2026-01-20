"""
PhotoSorter: Classifies and organizes images based on white background dominance.

Script processes all images from an 'Import' folder, classifying them as 'wanted' 
or 'unwanted' based on white background analysis, then moves them to respective folders.
Wanted images are renamed with EXIF DateTimeOriginal prefix if available.

Usage:
    python main.py [optional path to Import folder, default './Import']
"""

import cv2
import os
import sys
import shutil
import glob
from pathlib import Path
from datetime import datetime
from PIL import Image
from PIL.ExifTags import TAGS
import imagehash


class PhotoSorter:
    """Analyzes and sorts images based on white background dominance."""
    
    # Configuration
    RESIZE_SIZE = 300
    WHITE_THRESHOLD_PERCENT = 40
    WHITE_PIXEL_MIN = 150  # R, G, B all >= 240 for white
    DARK_THRESHOLD_PERCENT = 40
    DARK_PIXEL_MAX = 50  # R, G, B all <= 50 for dark
    
    # Supported image extensions (case-insensitive)
    SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
    
    def __init__(self, import_path='./Import', rename=True, verbose=True):
        """
        Initialize PhotoSorter with source folder path.
        
        Args:
            import_path: Path to folder containing images to process
            rename: Boolean to enable/disable renaming wanted images with EXIF date prefix
            verbose: Boolean to enable/disable console output (except errors)
        """
        self.import_path = Path(import_path)
        self.wanted_path = Path('./Wanted')
        self.unwanted_path = Path('./Unwanted')
        self.rename = rename
        self.verbose = verbose
        
        # Validate and create output folders if needed
        self._validate_paths()
        
        self.stats = {'wanted': 0, 'unwanted': 0, 'errors': 0, 'non_image_files': 0}
    
    def _validate_paths(self):
        """Validate input folder and create output folders if needed."""
        if not self.import_path.exists():
            raise ValueError(f"Import folder not found: {self.import_path}")
        
        if not self.import_path.is_dir():
            raise ValueError(f"Import path is not a directory: {self.import_path}")
        
        # Create output folders if they don't exist
        self.wanted_path.mkdir(exist_ok=True)
        self.unwanted_path.mkdir(exist_ok=True)
    
    def _get_image_files(self):
        """
        Recursively find all supported image files in import folder.
        
        Returns:
            List of pathlib.Path objects for image files
        """
        image_files = []
        
        for ext in self.SUPPORTED_EXTENSIONS:
            # Search recursively for both uppercase and lowercase extensions
            image_files.extend(self.import_path.rglob(f'*{ext}'))
            image_files.extend(self.import_path.rglob(f'*{ext.upper()}'))
        
        # Remove duplicates (same file found with different case extensions)
        return list(set(image_files))
    
    def _move_non_image_files(self):
        """
        Move all non-image files from import folder to Wanted folder.
        """
        try:
            for item in self.import_path.iterdir():
                if item.is_file():
                    # Check if it's not an image file
                    if item.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
                        dest_path = self.wanted_path / item.name
                        
                        # Handle filename conflicts
                        if dest_path.exists():
                            base_name = item.stem
                            ext = item.suffix
                            counter = 1
                            while dest_path.exists():
                                dest_path = self.wanted_path / f"{base_name}_{counter}{ext}"
                                counter += 1
                        
                        shutil.move(str(item), str(dest_path))
                        if self.verbose:
                            print(f"Moved non-image file: {item.name} to Wanted")
                        self.stats['non_image_files'] += 1
        except Exception as e:
            print(f"✗ Error moving non-image files: {str(e)}")
    
    def _is_white_background(self, image_path):
        """
        Analyze image to determine if it has dominant white background.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Tuple of (is_white: bool, white_percent: float, error: str or None)
        """
        try:
            # Load image with cv2
            img = cv2.imread(str(image_path))
            
            if img is None:
                return False, 0, "Failed to load image with cv2"
            
            # Resize for faster processing
            img_resized = cv2.resize(img, (self.RESIZE_SIZE, self.RESIZE_SIZE), 
                                    interpolation=cv2.INTER_AREA)
            
            # Convert BGR to RGB-compatible format (cv2 uses BGR)
            # Check pixels where B >= 240 AND G >= 240 AND R >= 240
            b, g, r = cv2.split(img_resized)
            
            # Count white pixels (all channels >= 240)
            white_mask = (b >= self.WHITE_PIXEL_MIN) & \
                        (g >= self.WHITE_PIXEL_MIN) & \
                        (r >= self.WHITE_PIXEL_MIN)
            
            white_count = cv2.countNonZero(white_mask.astype('uint8'))
            total_pixels = self.RESIZE_SIZE * self.RESIZE_SIZE
            white_percent = (white_count / total_pixels) * 100
            
            is_white = white_percent > self.WHITE_THRESHOLD_PERCENT
            
            return is_white, white_percent, None
            
        except Exception as e:
            return False, 0, f"Error analyzing image: {str(e)}"
    
    def _is_dark_background(self, image_path):
        """
        Analyze image to determine if it has dominant dark background.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Tuple of (is_dark: bool, dark_percent: float, error: str or None)
        """
        try:
            # Load image with cv2
            img = cv2.imread(str(image_path))
            
            if img is None:
                return False, 0, "Failed to load image with cv2"
            
            # Resize for faster processing
            img_resized = cv2.resize(img, (self.RESIZE_SIZE, self.RESIZE_SIZE), 
                                    interpolation=cv2.INTER_AREA)
            
            # Convert BGR to RGB-compatible format (cv2 uses BGR)
            # Check pixels where B <= 50 AND G <= 50 AND R <= 50
            b, g, r = cv2.split(img_resized)
            
            # Count dark pixels (all channels <= 50)
            dark_mask = (b <= self.DARK_PIXEL_MAX) & \
                       (g <= self.DARK_PIXEL_MAX) & \
                       (r <= self.DARK_PIXEL_MAX)
            
            dark_count = cv2.countNonZero(dark_mask.astype('uint8'))
            total_pixels = self.RESIZE_SIZE * self.RESIZE_SIZE
            dark_percent = (dark_count / total_pixels) * 100
            
            is_dark = dark_percent > self.DARK_THRESHOLD_PERCENT
            
            return is_dark, dark_percent, None
            
        except Exception as e:
            return False, 0, f"Error analyzing image: {str(e)}"
    
    def _get_exif_datetime(self, image_path):
        """
        Extract DateTimeOriginal (tag 36867) from image EXIF data.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Tuple of (datetime_string: str or None, error: str or None)
            datetime_string format: YYYYMMDD
        """
        try:
            with Image.open(image_path) as img:
                exif_data = img._getexif()
                
                if exif_data is None:
                    return None, "No EXIF data found"
                
                # Tag 36867 is DateTimeOriginal
                datetime_original = exif_data.get(36867)
                
                if datetime_original is None:
                    return None, "DateTimeOriginal tag not found"
                
                # Parse datetime string (format: "YYYY:MM:DD HH:MM:SS")
                datetime_obj = datetime.strptime(datetime_original, "%Y:%m:%d %H:%M:%S")
                date_prefix = datetime_obj.strftime("%Y%m%d")
                
                return date_prefix, None
                
        except Exception as e:
            return None, f"Error reading EXIF: {str(e)}"
    
    def _get_image_metadata(self, image_path):
        """
        Extract basic metadata from image file.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Dict with metadata (size, dimensions, exif_date, etc.)
        """
        metadata = {}
        try:
            # File size
            stat = image_path.stat()
            metadata['file_size'] = stat.st_size
            metadata['file_size_mb'] = stat.st_size / (1024 * 1024)
            
            # Image dimensions
            with Image.open(image_path) as img:
                metadata['width'], metadata['height'] = img.size
                
                # EXIF date
                exif_data = img._getexif()
                if exif_data:
                    datetime_original = exif_data.get(36867)  # DateTimeOriginal
                    if datetime_original:
                        try:
                            datetime_obj = datetime.strptime(datetime_original, "%Y:%m:%d %H:%M:%S")
                            metadata['exif_date'] = datetime_obj.strftime("%Y-%m-%d %H:%M:%S")
                        except:
                            pass
                            
                    # Camera model
                    model = exif_data.get(272)  # Model
                    if model:
                        metadata['camera_model'] = model
                        
        except Exception as e:
            metadata['error'] = str(e)
            
        return metadata
    
    def _compute_image_hash(self, image_path, hash_size=8):
        """
        Compute perceptual hash for image comparison.
        
        Args:
            image_path: Path to image file
            hash_size: Size of hash (higher = more precise but slower)
            
        Returns:
            ImageHash object or None if error
        """
        try:
            with Image.open(image_path) as img:
                # Resize to standard size for consistent hashing
                img_resized = img.resize((self.RESIZE_SIZE, self.RESIZE_SIZE), Image.Resampling.LANCZOS)
                # Convert to grayscale for better hash consistency
                img_gray = img_resized.convert('L')
                # Compute perceptual hash
                return imagehash.phash(img_gray, hash_size=hash_size)
        except Exception as e:
            print(f"Error computing hash for {image_path}: {e}")
            return None
    
    def find_duplicate_groups(self, folder_path, similarity_threshold=0.9):
        """
        Find groups of duplicate images in a folder using perceptual hashing.
        
        Args:
            folder_path: Path to folder containing images
            similarity_threshold: Threshold for considering images similar (0-1)
            
        Returns:
            List of duplicate groups, each group is a list of image paths
        """
        folder = Path(folder_path)
        if not folder.exists():
            return []
        
        # Get all image files
        image_files = []
        for ext in self.SUPPORTED_EXTENSIONS:
            image_files.extend(folder.glob(f'*{ext}'))
            image_files.extend(folder.glob(f'*{ext.upper()}'))
        
        if len(image_files) < 2:
            return []
        
        # Compute hashes for all images
        hashes = {}
        for img_path in image_files:
            hash_val = self._compute_image_hash(img_path)
            if hash_val:
                hashes[img_path] = hash_val
        
        # Group similar images
        duplicate_groups = []
        processed = set()
        
        for img1, hash1 in hashes.items():
            if img1 in processed:
                continue
                
            group = [img1]
            processed.add(img1)
            
            for img2, hash2 in hashes.items():
                if img2 in processed:
                    continue
                    
                # Calculate similarity (1 - hamming_distance / max_distance)
                distance = hash1 - hash2
                max_distance = len(hash1.hash) ** 2  # For hash_size=8, max_distance=64
                similarity = 1 - (distance / max_distance)
                
                if similarity >= similarity_threshold:
                    group.append(img2)
                    processed.add(img2)
            
            if len(group) > 1:
                duplicate_groups.append(group)
        
        return duplicate_groups
    
    def _generate_new_filename(self, original_path, date_prefix):
        """
        Generate new filename with EXIF date prefix.
        
        Args:
            original_path: Path object of original file
            date_prefix: EXIF date in YYYYMMDD format
            
        Returns:
            New filename with date prefix
        """
        original_name = original_path.name
        return f"{date_prefix}_{original_name}"
    
    def _move_image(self, image_path, is_wanted, new_filename=None):
        """
        Move image to appropriate folder (Wanted or Unwanted).
        
        Args:
            image_path: Path to image file
            is_wanted: Boolean indicating if image should go to Wanted folder
            new_filename: Optional new filename for wanted images
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            dest_folder = self.wanted_path if is_wanted else self.unwanted_path
            
            # Use new filename if provided, otherwise keep original name
            dest_filename = new_filename if new_filename else image_path.name
            dest_path = dest_folder / dest_filename
            
            # Handle filename conflicts by appending counter
            if dest_path.exists():
                base_name = dest_filename.rsplit('.', 1)[0]
                ext = '.' + dest_filename.rsplit('.', 1)[1]
                counter = 1
                while dest_path.exists():
                    dest_filename = f"{base_name}_{counter}{ext}"
                    dest_path = dest_folder / dest_filename
                    counter += 1
            
            # Move the file
            shutil.move(str(image_path), str(dest_path))
            
            folder_name = "Wanted" if is_wanted else "Unwanted"
            message = f"Moved {image_path.name} to {folder_name}"
            if new_filename and is_wanted:
                message += f" as {dest_filename}"
            
            return True, message, dest_filename
            
        except Exception as e:
            return False, f"Error moving {image_path.name}: {str(e)}", None
    
    def process_images(self):
        """
        Process all images in import folder.
        Analyzes each image and moves to appropriate folder.
        """
        # Move non-image files to Wanted folder first
        self._move_non_image_files()
        
        image_files = self._get_image_files()
        
        if not image_files:
            if self.verbose:
                print("No image files found in Import folder.")
            return
        
        if self.verbose:
            print(f"\nFound {len(image_files)} image(s) to process.\n")
        
        for image_path in sorted(image_files):
            if self.verbose:
                print(f"Processing: {image_path.name}")
            
            try:
                # Analyze image for white background
                is_white, white_percent, error = self._is_white_background(image_path)
                
                if error:
                    print(f"✗ {error} - Classifying as unwanted")
                    success, msg, _ = self._move_image(image_path, is_wanted=False)
                    if success:
                        if self.verbose:
                            print(f"  ✓ {msg}")
                        self.stats['unwanted'] += 1
                    else:
                        print(f"  ✗ {msg}")
                        self.stats['errors'] += 1
                    continue
                
                # Classify based on white percentage
                if is_white:
                    # Unwanted: white background dominant
                    if self.verbose:
                        print(f"  White background: {white_percent:.1f}% - Unwanted")
                    success, msg, _ = self._move_image(image_path, is_wanted=False)
                    if success:
                        if self.verbose:
                            print(f"  ✓ {msg}")
                        self.stats['unwanted'] += 1
                    else:
                        print(f"  ✗ {msg}")
                        self.stats['errors'] += 1
                else:
                    # Check for dark background
                    is_dark, dark_percent, dark_error = self._is_dark_background(image_path)
                    
                    if dark_error:
                        # If dark analysis fails, treat as neither
                        if self.verbose:
                            print(f"  White background: {white_percent:.1f}% - Dark analysis failed - Unwanted")
                        success, msg, _ = self._move_image(image_path, is_wanted=False)
                        if success:
                            if self.verbose:
                                print(f"  ✓ {msg}")
                            self.stats['unwanted'] += 1
                        else:
                            print(f"  ✗ {msg}")
                            self.stats['errors'] += 1
                        continue
                    
                    if is_dark:
                        # Wanted: dark background dominant
                        if self.verbose:
                            print(f"  Dark background: {dark_percent:.1f}% - Wanted")
                        
                        new_filename = None
                        if self.rename:
                            date_prefix, exif_error = self._get_exif_datetime(image_path)
                            
                            if date_prefix:
                                new_filename = self._generate_new_filename(image_path, date_prefix)
                                if self.verbose:
                                    print(f"  EXIF date found: {date_prefix}")
                            else:
                                if self.verbose:
                                    print(f"  No EXIF DateTimeOriginal: {exif_error if exif_error else 'N/A'}")
                        else:
                            if self.verbose:
                                print(f"  Rename disabled - keeping original filename")
                        
                        success, msg, dest_filename = self._move_image(image_path, is_wanted=True, 
                                                       new_filename=new_filename)
                        if success:
                            if self.verbose:
                                print(f"  ✓ {msg}")
                            self.stats['wanted'] += 1
                        else:
                            print(f"  ✗ {msg}")
                            self.stats['errors'] += 1
                    else:
                        # Neither white nor dark dominant - unwanted
                        if self.verbose:
                            print(f"  White: {white_percent:.1f}%, Dark: {dark_percent:.1f}% - Unwanted")
                        success, msg, _ = self._move_image(image_path, is_wanted=False)
                        if success:
                            if self.verbose:
                                print(f"  ✓ {msg}")
                            self.stats['unwanted'] += 1
                        else:
                            print(f"  ✗ {msg}")
                            self.stats['errors'] += 1
                
            except Exception as e:
                print(f"✗ Unexpected error: {str(e)}")
                self.stats['errors'] += 1
        
        # Print summary
        self._print_summary()
    
    def _print_summary(self):
        """Print processing summary statistics."""
        print("\n" + "="*60)
        print("Processing Summary:")
        print(f"  Wanted:        {self.stats['wanted']}")
        print(f"  Unwanted:      {self.stats['unwanted']}")
        print(f"  Non-image files: {self.stats['non_image_files']}")
        print(f"  Errors:        {self.stats['errors']}")
        print("="*60 + "\n")


def main():
    """Main entry point for PhotoSorter."""
    # Parse command line arguments
    import_path = './Import'
    rename = True
    verbose = True
    
    if len(sys.argv) > 1:
        import_path = sys.argv[1]
    if len(sys.argv) > 2:
        rename = sys.argv[2].lower() in ('true', '1', 'yes')
    if len(sys.argv) > 3:
        verbose = sys.argv[3].lower() in ('true', '1', 'yes')
    
    try:
        sorter = PhotoSorter(import_path, rename=rename, verbose=verbose)
        sorter.process_images()
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
