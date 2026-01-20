"""
PhotoSorter GUI: A professional Tkinter GUI application for the PhotoSorter script.

Features:
- Configurable parameters (folders, thresholds, extensions, etc.)
- Image scanning and statistics
- Real-time processing with progress feedback
- Thread-safe execution for non-blocking UI
- Configuration save/load (JSON)
- Color-coded logging and dry-run mode

Usage:
    python photosorter_gui.py
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import queue
import json
import os
import sys
from pathlib import Path
from datetime import datetime
import shutil
from PIL import Image, ImageTk

# Import PhotoSorter class from photoSorter.py
from photoSorter import PhotoSorter
# Import flatten_folder function from flattenFolder.py
from flattenFolder import flatten_folder


class ConfigManager:
    """Manage loading and saving GUI configuration."""
    
    CONFIG_FILE = 'photosorter_config.json'
    
    DEFAULT_CONFIG = {
        'import_path': './Import',
        'wanted_path': './Wanted',
        'unwanted_path': './Unwanted',
        'resize_size': 300,
        'white_threshold_percent': 70,
        'white_pixel_min': 240,
        'dark_threshold_percent': 70,
        'dark_pixel_max': 50,
        'rename': True,
        'verbose': True,
        'recursive_scan': True,
        'supported_extensions': ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'],
        'non_image_handling': 'Move to Wanted',
        'filename_conflict': 'Counter',
        'flatten_import_folder': False
    }
    
    @staticmethod
    def load():
        """Load configuration from file or return defaults."""
        if os.path.exists(ConfigManager.CONFIG_FILE):
            try:
                with open(ConfigManager.CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    return {**ConfigManager.DEFAULT_CONFIG, **config}
            except Exception as e:
                print(f"Error loading config: {e}")
        return ConfigManager.DEFAULT_CONFIG.copy()
    
    @staticmethod
    def save(config):
        """Save configuration to file."""
        try:
            with open(ConfigManager.CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
            return True, "Configuration saved successfully"
        except Exception as e:
            return False, f"Error saving config: {e}"


class PhotoSorterWorker(threading.Thread):
    """Worker thread for non-blocking image processing."""
    
    def __init__(self, config, output_queue, dry_run=False):
        super().__init__(daemon=True)
        self.config = config
        self.output_queue = output_queue
        self.dry_run = dry_run
        self.stop_event = threading.Event()
    
    def run(self):
        """Execute image processing in background thread."""
        try:
            # Flatten import folder if enabled
            if self.config.get('flatten_import_folder', False):
                import_path = self.config['import_path']
                if os.path.exists(import_path) and os.path.isdir(import_path):
                    self.output_queue.put(('info', f"Flattening Import Folder: {import_path}"))
                    # Capture print statements from flatten_folder and send to queue
                    import builtins
                    old_print = builtins.print
                    
                    def queue_print(*args, **kwargs):
                        msg = ' '.join(str(arg) for arg in args)
                        self.output_queue.put(('info', msg))
                    
                    try:
                        # Temporarily replace print
                        builtins.print = queue_print
                        
                        flatten_folder(import_path)
                        self.output_queue.put(('info', 'Import folder flattened successfully'))
                        self.output_queue.put(('info', ''))
                    except Exception as e:
                        self.output_queue.put(('error', f"Error flattening folder: {str(e)}"))
                    finally:
                        # Always restore print
                        builtins.print = old_print
                else:
                    self.output_queue.put(('error', f"Import folder does not exist: {import_path}"))
            
            # Create modified PhotoSorter instance with GUI parameters
            sorter = PhotoSorter(
                import_path=self.config['import_path'],
                rename=self.config['rename'],
                verbose=self.config['verbose']
            )
            
            # Apply GUI-configured thresholds
            sorter.RESIZE_SIZE = self.config['resize_size']
            sorter.WHITE_THRESHOLD_PERCENT = self.config['white_threshold_percent']
            sorter.WHITE_PIXEL_MIN = self.config['white_pixel_min']
            sorter.DARK_THRESHOLD_PERCENT = self.config['dark_threshold_percent']
            sorter.DARK_PIXEL_MAX = self.config['dark_pixel_max']
            
            # Update supported extensions
            sorter.SUPPORTED_EXTENSIONS = set(self.config['supported_extensions'])
            
            # Log start
            self.output_queue.put(('info', f"Starting {'dry-run ' if self.dry_run else ''}image processing..."))
            self.output_queue.put(('info', f"Import path: {self.config['import_path']}"))
            self.output_queue.put(('info', f"Wanted path: {self.config['wanted_path']}"))
            self.output_queue.put(('info', f"Unwanted path: {self.config['unwanted_path']}"))
            self.output_queue.put(('info', f"Thresholds: {self.config['white_threshold_percent']}% white ({self.config['white_pixel_min']} RGB min), {self.config['dark_threshold_percent']}% dark ({self.config['dark_pixel_max']} RGB max)"))
            self.output_queue.put(('info', ''))
            
            if self.dry_run:
                self._dry_run_scan(sorter)
            else:
                # Capture print statements during processing
                # This captures the summary from _print_summary() when verbose is True
                import builtins
                old_print = builtins.print
                
                def queue_print(*args, **kwargs):
                    msg = ' '.join(str(arg) for arg in args)
                    self.output_queue.put(('info', msg))
                
                try:
                    # Temporarily replace print to capture output
                    builtins.print = queue_print
                    
                    # Process images
                    sorter.process_images()
                finally:
                    # Always restore print
                    builtins.print = old_print
                
                # Send stats
                self.output_queue.put(('stats', sorter.stats))
                
                # Always explicitly log summary to ensure it's visible
                # This guarantees the summary appears even if verbose is False
                self._log_summary(sorter.stats)
            
            self.output_queue.put(('complete', 'Processing complete'))
            
        except Exception as e:
            self.output_queue.put(('error', f"Processing error: {str(e)}"))
    
    def _dry_run_scan(self, sorter):
        """Scan without moving files (dry-run mode)."""
        try:
            sorter._move_non_image_files = lambda: None  # Skip moving non-image files
            
            image_files = sorter._get_image_files()
            self.output_queue.put(('info', f"Dry-run: Found {len(image_files)} image file(s)\n"))
            
            wanted_count = 0
            unwanted_count = 0
            
            for image_path in sorted(image_files):
                if self.stop_event.is_set():
                    break
                
                self.output_queue.put(('info', f"Scanning: {image_path.name}"))
                
                is_white, white_percent, error = sorter._is_white_background(image_path)
                
                if error:
                    self.output_queue.put(('error', f"  ⚠ {error}"))
                    unwanted_count += 1
                elif is_white:
                    self.output_queue.put(('unwanted', f"  White: {white_percent:.1f}% - Would move to Unwanted"))
                    unwanted_count += 1
                else:
                    self.output_queue.put(('wanted', f"  White: {white_percent:.1f}% - Would move to Wanted"))
                    wanted_count += 1
            
            stats = {
                'wanted': wanted_count,
                'unwanted': unwanted_count,
                'errors': 0,
                'non_image_files': 0
            }
            self.output_queue.put(('stats', stats))
            
        except Exception as e:
            self.output_queue.put(('error', f"Dry-run error: {str(e)}"))
    
    def _log_summary(self, stats):
        """Always log the processing summary regardless of verbose setting."""
        self.output_queue.put(('info', ''))
        self.output_queue.put(('info', '='*60))
        self.output_queue.put(('info', 'Processing Summary:'))
        self.output_queue.put(('info', f"  Wanted:        {stats['wanted']}"))
        self.output_queue.put(('info', f"  Unwanted:      {stats['unwanted']}"))
        self.output_queue.put(('info', f"  Non-image files: {stats['non_image_files']}"))
        self.output_queue.put(('info', f"  Errors:        {stats['errors']}"))
        self.output_queue.put(('info', '='*60))
        self.output_queue.put(('info', ''))


class ToolTip:
    """Create a tooltip for a given widget."""
    
    def __init__(self, widget, text='widget info'):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.id = None
        self.x = self.y = 0
        
        # Bind events
        self.widget.bind('<Enter>', self.enter)
        self.widget.bind('<Leave>', self.leave)
        self.widget.bind('<ButtonPress>', self.leave)
    
    def enter(self, event=None):
        self.schedule()
    
    def leave(self, event=None):
        self.unschedule()
        self.hidetip()
    
    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(500, self.showtip)
    
    def unschedule(self):
        id = self.id
        self.id = None
        if id:
            self.widget.after_cancel(id)
    
    def showtip(self, event=None):
        # Get widget position
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        
        # Create tooltip window
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry("+%d+%d" % (x, y))
        
        label = tk.Label(tw, text=self.text, justify='left',
                        background="#ffffe0", relief='solid', borderwidth=1,
                        font=("tahoma", "8", "normal"), wraplength=250)
        label.pack(ipadx=1)
    
    def hidetip(self):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()


class PhotoSorterGUI:
    """Main GUI application for PhotoSorter."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("PhotoSorter GUI - Professional Image Organizer")
        self.root.geometry("1000x725")
        self.root.minsize(570, 725)
        
        # Configuration
        self.config = ConfigManager.load()
        
        # Threading
        self.worker_thread = None
        self.output_queue = queue.Queue()
        self.processing = False
        
        # Store button references for tooltips
        self.buttons = {}

        # Track which image tab is currently active for keyboard navigation
        self._active_image_folder_key = None
        
        # Setup UI
        self._setup_styles()
        self._create_widgets()
        self._setup_tooltips()
        self._start_queue_monitor()

        # Keyboard navigation for image tabs
        self._bind_image_navigation_keys()
    
    def _setup_styles(self):
        """Configure ttk theme and styles."""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Custom colors
        style.configure('Title.TLabel', font=('Helvetica', 12, 'bold'))
        style.configure('Success.TLabel', foreground='green')
        style.configure('Error.TLabel', foreground='red')
    
    def _create_widgets(self):
        """Create main GUI widgets."""
        # Main container
        main_container = ttk.Frame(self.root)
        main_container.pack(side='top', fill='both', expand=True, padx=5, pady=5)
        
        # Notebook (tabs)
        self.notebook = ttk.Notebook(main_container)
        self.notebook.pack(fill='both', expand=True)
        
        # Create tabs
        self._create_config_tab()
        self._create_processing_tab()
        self._create_duplicated_tab()
        self._create_import_tab()
        self._create_wanted_tab()
        self._create_unwanted_tab()
        
        # Status bar
        self._create_status_bar()

        # Initialize active folder based on currently selected tab (if any)
        self._set_active_image_folder_from_tab()
    
    def _create_config_tab(self):
        """Create Configuration tab."""
        config_frame = ttk.Frame(self.notebook)
        self.notebook.add(config_frame, text='Configuration')
        
        # Create canvas with scrollbar for scrollable content
        canvas = tk.Canvas(config_frame)
        scrollbar = ttk.Scrollbar(config_frame, orient='vertical', command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Paths Section
        paths_frame = ttk.LabelFrame(scrollable_frame, text='Folders', padding=10)
        paths_frame.pack(fill='x', padx=10, pady=5)
        
        self._create_path_selector(paths_frame, 'Import Folder:', 'import_path', 0)
        
        # Flatten Import Folder checkbox
        self.flatten_import_var = tk.BooleanVar(value=self.config.get('flatten_import_folder', False))
        flatten_checkbox = ttk.Checkbutton(
            paths_frame, text='Flatten Import Folder before processing',
            variable=self.flatten_import_var
        )
        flatten_checkbox.grid(row=1, column=0, columnspan=3, sticky='w', padx=5, pady=2)
        
        self._create_path_selector(paths_frame, 'Wanted Folder:', 'wanted_path', 2)
        self._create_path_selector(paths_frame, 'Unwanted Folder:', 'unwanted_path', 3)
        
        # Thresholds Section
        thresh_frame = ttk.LabelFrame(scrollable_frame, text='Image Analysis Thresholds', padding=10)
        thresh_frame.pack(fill='x', padx=10, pady=5)
        
        # Resize Size
        ttk.Label(thresh_frame, text='Resize Size (pixels):').grid(row=0, column=0, sticky='w')
        self.resize_var = tk.IntVar(value=self.config['resize_size'])
        self.resize_spin = ttk.Spinbox(
            thresh_frame, from_=100, to=1000, textvariable=self.resize_var, width=10
        )
        self.resize_spin.grid(row=0, column=1, sticky='w', padx=5)
        
        # White Threshold
        ttk.Label(thresh_frame, text='White Threshold (%):').grid(row=1, column=0, sticky='w')
        self.white_thresh_var = tk.IntVar(value=self.config['white_threshold_percent'])
        self.white_thresh_scale = ttk.Scale(
            thresh_frame, from_=10, to=100, orient='horizontal',
            variable=self.white_thresh_var
        )
        self.white_thresh_scale.grid(row=1, column=1, sticky='ew', padx=5)
        self.white_thresh_label = ttk.Label(thresh_frame, text=f"{self.config['white_threshold_percent']}%")
        self.white_thresh_label.grid(row=1, column=2, padx=5)
        self.white_thresh_var.trace('w', self._update_white_thresh_label)
        
        # White Pixel Min
        ttk.Label(thresh_frame, text='White Pixel Min RGB (0-255):').grid(row=2, column=0, sticky='w')
        self.white_pixel_var = tk.IntVar(value=self.config['white_pixel_min'])
        self.white_pixel_spin = ttk.Spinbox(
            thresh_frame, from_=0, to=255, textvariable=self.white_pixel_var, width=10
        )
        self.white_pixel_spin.grid(row=2, column=1, sticky='w', padx=5)
        
        # Dark Threshold
        ttk.Label(thresh_frame, text='Dark Threshold (%):').grid(row=3, column=0, sticky='w')
        self.dark_thresh_var = tk.IntVar(value=self.config['dark_threshold_percent'])
        self.dark_thresh_scale = ttk.Scale(
            thresh_frame, from_=10, to=100, orient='horizontal',
            variable=self.dark_thresh_var
        )
        self.dark_thresh_scale.grid(row=3, column=1, sticky='ew', padx=5)
        self.dark_thresh_label = ttk.Label(thresh_frame, text=f"{self.config['dark_threshold_percent']}%")
        self.dark_thresh_label.grid(row=3, column=2, padx=5)
        self.dark_thresh_var.trace('w', self._update_dark_thresh_label)
        
        # Dark Pixel Max
        ttk.Label(thresh_frame, text='Dark Pixel Max RGB (0-255):').grid(row=4, column=0, sticky='w')
        self.dark_pixel_var = tk.IntVar(value=self.config['dark_pixel_max'])
        self.dark_pixel_spin = ttk.Spinbox(
            thresh_frame, from_=0, to=255, textvariable=self.dark_pixel_var, width=10
        )
        self.dark_pixel_spin.grid(row=4, column=1, sticky='w', padx=5)
        
        thresh_frame.columnconfigure(1, weight=1)
        
        # Options Section
        options_frame = ttk.LabelFrame(scrollable_frame, text='Processing Options', padding=10)
        options_frame.pack(fill='x', padx=10, pady=5)
        
        self.rename_var = tk.BooleanVar(value=self.config['rename'])
        ttk.Checkbutton(
            options_frame, text='Rename with EXIF date prefix',
            variable=self.rename_var
        ).pack(anchor='w')
        
        self.verbose_var = tk.BooleanVar(value=self.config['verbose'])
        ttk.Checkbutton(
            options_frame, text='Verbose logging',
            variable=self.verbose_var
        ).pack(anchor='w')
        
        self.recursive_var = tk.BooleanVar(value=self.config['recursive_scan'])
        ttk.Checkbutton(
            options_frame, text='Recursive folder scan',
            variable=self.recursive_var
        ).pack(anchor='w')
        
        # Extensions Section
        ext_frame = ttk.LabelFrame(scrollable_frame, text='Supported Extensions', padding=10)
        ext_frame.pack(fill='both', expand=False, padx=10, pady=5)
        
        listbox_frame = ttk.Frame(ext_frame)
        listbox_frame.pack(fill='both', expand=True)
        
        scrollbar_ext = ttk.Scrollbar(listbox_frame)
        scrollbar_ext.pack(side='right', fill='y')
        
        self.ext_listbox = tk.Listbox(
            listbox_frame, height=4, yscrollcommand=scrollbar_ext.set
        )
        self.ext_listbox.pack(side='left', fill='both', expand=True)
        scrollbar_ext.config(command=self.ext_listbox.yview)
        
        for ext in self.config['supported_extensions']:
            self.ext_listbox.insert(tk.END, ext)
        
        # Dropdown Options
        dropdown_frame = ttk.LabelFrame(scrollable_frame, text='Additional Options', padding=10)
        dropdown_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(dropdown_frame, text='Non-image file handling:').grid(row=0, column=0, sticky='w')
        self.non_image_var = tk.StringVar(value=self.config['non_image_handling'])
        ttk.Combobox(
            dropdown_frame, textvariable=self.non_image_var,
            values=['Move to Wanted', 'Skip'], state='readonly', width=20
        ).grid(row=0, column=1, sticky='w', padx=5)
        
        ttk.Label(dropdown_frame, text='Filename conflict handling:').grid(row=1, column=0, sticky='w')
        self.conflict_var = tk.StringVar(value=self.config['filename_conflict'])
        ttk.Combobox(
            dropdown_frame, textvariable=self.conflict_var,
            values=['Counter', 'Overwrite'], state='readonly', width=20
        ).grid(row=1, column=1, sticky='w', padx=5)
        
        # Buttons
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.pack(fill='x', padx=10, pady=10)
        
        save_btn = ttk.Button(button_frame, text='Save Config', command=self._save_config)
        save_btn.pack(side='left', padx=5)
        self.buttons['save_config'] = save_btn
        
        load_btn = ttk.Button(button_frame, text='Load Config', command=self._load_config)
        load_btn.pack(side='left', padx=5)
        self.buttons['load_config'] = load_btn
        
        reset_btn = ttk.Button(button_frame, text='Reset to Defaults', command=self._reset_defaults)
        reset_btn.pack(side='left', padx=5)
        self.buttons['reset_defaults'] = reset_btn
        
        # Pack canvas and scrollbar
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
    
    def _create_path_selector(self, parent, label, config_key, row):
        """Create a path selection control."""
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky='w', pady=5)
        
        var = tk.StringVar(value=self.config[config_key])
        entry = ttk.Entry(parent, textvariable=var, width=40)
        entry.grid(row=row, column=1, sticky='ew', padx=5)
        
        def browse():
            path = filedialog.askdirectory(title=label)
            if path:
                var.set(path)
                self.config[config_key] = path
        
        browse_btn = ttk.Button(parent, text='Browse', command=browse, width=10)
        browse_btn.grid(row=row, column=2, padx=5)
        self.buttons[f'browse_{config_key}'] = browse_btn
        
        parent.columnconfigure(1, weight=1)
        setattr(self, f'{config_key}_var', var)
    
    def _create_processing_tab(self):
        """Create Processing tab."""
        processing_frame = ttk.Frame(self.notebook)
        self.notebook.add(processing_frame, text='Processing')
        
        # Control buttons
        control_frame = ttk.Frame(processing_frame, padding=10)
        control_frame.pack(fill='x')
        
        self.start_button = ttk.Button(
            control_frame, text='Start Processing', command=self._start_processing
        )
        self.start_button.pack(side='left', padx=5)
        self.buttons['start_processing'] = self.start_button
        
        self.dry_run_button = ttk.Button(
            control_frame, text='Dry Run', command=self._start_dry_run
        )
        self.dry_run_button.pack(side='left', padx=5)
        self.buttons['dry_run'] = self.dry_run_button
        
        # scan_btn = ttk.Button(control_frame, text='Scan Folders', command=self._scan_preview)
        # scan_btn.pack(side='left', padx=5)
        # self.buttons['scan_folders'] = scan_btn
        
        # ttk.Label(control_frame, text='(Counts images without moving)', foreground='gray').pack(side='left', padx=5)
        
        self.stop_button = ttk.Button(
            control_frame, text='Stop', command=self._stop_processing, state='disabled'
        )
        self.stop_button.pack(side='left', padx=5)
        self.buttons['stop'] = self.stop_button
        
        export_btn = ttk.Button(control_frame, text='Export Log', command=self._export_log)
        export_btn.pack(side='left', padx=5)
        self.buttons['export_log'] = export_btn
        
        # Progress bar
        progress_frame = ttk.Frame(processing_frame, padding=10)
        progress_frame.pack(fill='x')
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            progress_frame, variable=self.progress_var, maximum=100, mode='indeterminate'
        )
        self.progress_bar.pack(fill='x')
        
        # Log area
        log_frame = ttk.LabelFrame(processing_frame, text='Processing Log', padding=10)
        log_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=20, wrap=tk.WORD, font=('Courier', 9)
        )
        self.log_text.pack(fill='both', expand=True)
        
        # Configure text tags for colors
        self.log_text.tag_configure('wanted', foreground='green')
        self.log_text.tag_configure('unwanted', foreground='red')
        self.log_text.tag_configure('error', foreground='darkred', background='lightyellow')
        self.log_text.tag_configure('info', foreground='blue')
        
        # Stats frame
        stats_frame = ttk.Frame(processing_frame, padding=10)
        stats_frame.pack(fill='x')
        
        self.stats_label = ttk.Label(
            stats_frame, text='Ready', relief='sunken'
        )
        self.stats_label.pack(fill='x')
    
    def _create_duplicated_tab(self):
        """Create Duplicated tab with duplicate set navigation."""
        duplicated_frame = ttk.Frame(self.notebook)
        self.notebook.add(duplicated_frame, text='Duplicated')
        self.duplicated_tab_index = self.notebook.index('end') - 1  # Store tab index
        
        # Main container
        main_frame = ttk.Frame(duplicated_frame)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Progress indicator
        progress_label = ttk.Label(main_frame, text='Duplicate Set #0 of 0', font=('Arial', 12, 'bold'))
        progress_label.pack(pady=5)
        setattr(self, 'duplicated_progress_label', progress_label)
        
        # Navigation frame with 4 arrows
        nav_frame = ttk.Frame(main_frame)
        nav_frame.pack(pady=5)
        
        # Outer arrows (set navigation)
        prev_set_btn = ttk.Button(nav_frame, text='◀◀', width=4, command=lambda: self._navigate_duplicate_set(-1))
        prev_set_btn.pack(side='left', padx=5)
        ToolTip(prev_set_btn, 'Previous duplicate set')
        
        prev_img_btn = ttk.Button(nav_frame, text='◀', width=4, command=lambda: self._navigate_duplicate_inner(-1))
        prev_img_btn.pack(side='left', padx=5)
        ToolTip(prev_img_btn, 'Previous image in set')
        
        next_img_btn = ttk.Button(nav_frame, text='▶', width=4, command=lambda: self._navigate_duplicate_inner(1))
        next_img_btn.pack(side='left', padx=5)
        ToolTip(next_img_btn, 'Next image in set')
        
        next_set_btn = ttk.Button(nav_frame, text='▶▶', width=4, command=lambda: self._navigate_duplicate_set(1))
        next_set_btn.pack(side='left', padx=5)
        ToolTip(next_set_btn, 'Next duplicate set')
        
        # Image display frame
        image_frame = ttk.Frame(main_frame)
        image_frame.pack(fill='both', expand=True, pady=10)
        
        image_label = ttk.Label(image_frame, text='No duplicates found', anchor='center')
        image_label.pack(fill='both', expand=True)
        setattr(self, 'duplicated_image_label', image_label)
        
        # Function bar - horizontal layout
        func_frame = ttk.LabelFrame(main_frame, text='Image Information', padding=10)
        func_frame.pack(fill='x', pady=5)
        
        # Create a horizontal frame for all info and buttons
        info_frame = ttk.Frame(func_frame)
        info_frame.pack(fill='x')
        
        # Image count label
        count_label = ttk.Label(info_frame, text='Image: 0/0')
        count_label.pack(side='left', padx=(0,10))
        setattr(self, 'duplicated_count_label', count_label)
        
        # Image name and size label
        name_label = ttk.Label(info_frame, text='Name: -')
        name_label.pack(side='left', padx=(0,10))
        setattr(self, 'duplicated_name_label', name_label)
        
        # Metadata label
        metadata_label = ttk.Label(info_frame, text='Metadata: -')
        metadata_label.pack(side='left', padx=(0,20))
        setattr(self, 'duplicated_metadata_label', metadata_label)
        
        # Transfer buttons frame - horizontal
        transfer_frame = ttk.Frame(info_frame)
        transfer_frame.pack(side='right')
        
        # Keep one only button
        keep_btn = ttk.Button(transfer_frame, text='Keep one only', 
                             command=self._keep_one_duplicate)
        keep_btn.pack(side='left', padx=2)
        ToolTip(keep_btn, 'Keep the largest file in this set, delete others')
        
        # Initialize duplicate data
        setattr(self, 'duplicate_groups', [])
        setattr(self, 'current_set_index', 0)
        setattr(self, 'current_image_index', 0)
        
        # Load duplicates when tab is selected (not on startup)
        # self._load_duplicates()
    
    def _create_status_bar(self):
        """Create status bar at bottom."""
        status_frame = ttk.Frame(self.root)
        status_frame.pack(side='bottom', fill='x')
        
        self.status_label = ttk.Label(
            status_frame, text='Ready', relief='sunken'
        )
        self.status_label.pack(side='left', fill='x', expand=True, padx=5, pady=2)
    
    def _setup_tooltips(self):
        """Setup tooltips for controls."""
        # Button tooltips
        button_tooltips = {
            'save_config': 'Save current configuration settings to file',
            'load_config': 'Load configuration settings from file',
            'reset_defaults': 'Reset all settings to default values',
            'browse_import_path': 'Browse and select the Import folder containing images to process',
            'browse_wanted_path': 'Browse and select the Wanted folder for images with non-white backgrounds',
            'browse_unwanted_path': 'Browse and select the Unwanted folder for images with white backgrounds',
            'start_processing': 'Start processing images: analyze and move them to Wanted/Unwanted folders',
            'dry_run': 'Preview what would happen without actually moving files (scan only)',
            'scan_folders': 'Scan folders and count images without moving them (preview mode)',
            'stop': 'Stop the current processing operation',
            'export_log': 'Export the processing log to a text file',
        }
        
        # Create tooltips for all buttons
        for button_key, tooltip_text in button_tooltips.items():
            if button_key in self.buttons:
                ToolTip(self.buttons[button_key], tooltip_text)
    
    def _update_white_thresh_label(self, *args):
        """Update white threshold label."""
        self.white_thresh_label.config(text=f"{self.white_thresh_var.get()}%")
    
    def _update_dark_thresh_label(self, *args):
        """Update dark threshold label."""
        self.dark_thresh_label.config(text=f"{self.dark_thresh_var.get()}%")
    
    def _save_config(self):
        """Save current configuration."""
        self.config.update({
            'import_path': self.import_path_var.get(),
            'wanted_path': self.wanted_path_var.get(),
            'unwanted_path': self.unwanted_path_var.get(),
            'resize_size': self.resize_var.get(),
            'white_threshold_percent': self.white_thresh_var.get(),
            'white_pixel_min': self.white_pixel_var.get(),
            'dark_threshold_percent': self.dark_thresh_var.get(),
            'dark_pixel_max': self.dark_pixel_var.get(),
            'rename': self.rename_var.get(),
            'verbose': self.verbose_var.get(),
            'recursive_scan': self.recursive_var.get(),
            'supported_extensions': list(self.ext_listbox.get(0, tk.END)),
            'non_image_handling': self.non_image_var.get(),
            'filename_conflict': self.conflict_var.get(),
            'flatten_import_folder': self.flatten_import_var.get(),
        })
        
        success, message = ConfigManager.save(self.config)
        if success:
            messagebox.showinfo('Success', message)
            self._update_status(message)
        else:
            messagebox.showerror('Error', message)
    
    def _load_config(self):
        """Load configuration from file."""
        self.config = ConfigManager.load()
        
        self.import_path_var.set(self.config['import_path'])
        self.wanted_path_var.set(self.config['wanted_path'])
        self.unwanted_path_var.set(self.config['unwanted_path'])
        self.resize_var.set(self.config['resize_size'])
        self.white_thresh_var.set(self.config['white_threshold_percent'])
        self.white_pixel_var.set(self.config['white_pixel_min'])
        self.dark_thresh_var.set(self.config['dark_threshold_percent'])
        self.dark_pixel_var.set(self.config['dark_pixel_max'])
        self.rename_var.set(self.config['rename'])
        self.verbose_var.set(self.config['verbose'])
        self.recursive_var.set(self.config['recursive_scan'])
        self.flatten_import_var.set(self.config.get('flatten_import_folder', False))
        
        self.ext_listbox.delete(0, tk.END)
        for ext in self.config['supported_extensions']:
            self.ext_listbox.insert(tk.END, ext)
        
        self.non_image_var.set(self.config['non_image_handling'])
        self.conflict_var.set(self.config['filename_conflict'])
        
        messagebox.showinfo('Success', 'Configuration loaded')
    
    def _reset_defaults(self):
        """Reset to default configuration."""
        if messagebox.askyesno('Confirm', 'Reset to default configuration?'):
            self.config = ConfigManager.DEFAULT_CONFIG.copy()
            self._load_config()
    
    def _scan_preview(self):
        """Scan folders and show preview without moving."""
        self._update_status('Scanning folders...')
        
        # Update config
        self.config.update({
            'import_path': self.import_path_var.get(),
            'wanted_path': self.wanted_path_var.get(),
            'unwanted_path': self.unwanted_path_var.get(),
            'resize_size': self.resize_var.get(),
            'white_threshold_percent': self.white_thresh_var.get(),
            'white_pixel_min': self.white_pixel_var.get(),
            'dark_threshold_percent': self.dark_thresh_var.get(),
            'dark_pixel_max': self.dark_pixel_var.get(),
            'rename': self.rename_var.get(),
            'verbose': self.verbose_var.get(),
            'flatten_import_folder': self.flatten_import_var.get(),
        })
        
        # Start worker thread
        self.worker_thread = PhotoSorterWorker(self.config, self.output_queue, dry_run=True)
        self.worker_thread.start()
    
    def _start_processing(self):
        """Start image processing."""
        if not self._validate_paths():
            messagebox.showerror('Error', 'Invalid paths configuration')
            return
        
        # Remove duplicate cache
        if os.path.exists('duplicate_cache.txt'):
            try:
                os.remove('duplicate_cache.txt')
            except:
                pass
        
        self._update_status('Processing images...')
        self.processing = True
        self.start_button.config(state='disabled')
        self.dry_run_button.config(state='disabled')
        self.stop_button.config(state='normal')
        self.progress_bar.start()
        self.log_text.delete(1.0, tk.END)
        
        # Update config
        self.config.update({
            'import_path': self.import_path_var.get(),
            'wanted_path': self.wanted_path_var.get(),
            'unwanted_path': self.unwanted_path_var.get(),
            'resize_size': self.resize_var.get(),
            'white_threshold_percent': self.white_thresh_var.get(),
            'white_pixel_min': self.white_pixel_var.get(),
            'dark_threshold_percent': self.dark_thresh_var.get(),
            'dark_pixel_max': self.dark_pixel_var.get(),
            'rename': self.rename_var.get(),
            'verbose': self.verbose_var.get(),
            'flatten_import_folder': self.flatten_import_var.get(),
        })
        
        # Start worker thread
        self.worker_thread = PhotoSorterWorker(self.config, self.output_queue, dry_run=False)
        self.worker_thread.start()
    
    def _start_dry_run(self):
        """Start dry-run (scan without moving)."""
        # Remove duplicate cache
        if os.path.exists('duplicate_cache.txt'):
            try:
                os.remove('duplicate_cache.txt')
            except:
                pass
        
        self._update_status('Starting dry-run...')
        self.processing = True
        self.start_button.config(state='disabled')
        self.dry_run_button.config(state='disabled')
        self.stop_button.config(state='normal')
        self.progress_bar.start()
        self.log_text.delete(1.0, tk.END)
        
        # Update config
        self.config.update({
            'import_path': self.import_path_var.get(),
            'wanted_path': self.wanted_path_var.get(),
            'unwanted_path': self.unwanted_path_var.get(),
            'resize_size': self.resize_var.get(),
            'white_threshold_percent': self.white_thresh_var.get(),
            'white_pixel_min': self.white_pixel_var.get(),
            'dark_threshold_percent': self.dark_thresh_var.get(),
            'dark_pixel_max': self.dark_pixel_var.get(),
            'rename': self.rename_var.get(),
            'verbose': self.verbose_var.get(),
            'flatten_import_folder': self.flatten_import_var.get(),
        })
        
        # Start worker thread
        self.worker_thread = PhotoSorterWorker(self.config, self.output_queue, dry_run=True)
        self.worker_thread.start()
    
    def _stop_processing(self):
        """Stop processing."""
        self.processing = False
        if self.worker_thread:
            self.worker_thread.stop_event.set()
        
        self._update_status('Processing stopped')
        self.start_button.config(state='normal')
        self.dry_run_button.config(state='normal')
        self.stop_button.config(state='disabled')
        self.progress_bar.stop()
    
    def _validate_paths(self):
        """Validate that required paths exist."""
        import_path = Path(self.import_path_var.get())
        
        if not import_path.exists():
            return False
        
        return True
    
    def _start_queue_monitor(self):
        """Monitor output queue for messages from worker thread."""
        self._check_queue()
    
    def _check_queue(self):
        """Check queue for messages from worker thread."""
        try:
            while True:
                msg_type, msg = self.output_queue.get_nowait()
                
                if msg_type == 'info':
                    self.log_text.insert(tk.END, msg + '\n', 'info')
                elif msg_type == 'wanted':
                    self.log_text.insert(tk.END, msg + '\n', 'wanted')
                elif msg_type == 'unwanted':
                    self.log_text.insert(tk.END, msg + '\n', 'unwanted')
                elif msg_type == 'error':
                    self.log_text.insert(tk.END, msg + '\n', 'error')
                elif msg_type == 'stats':
                    self._update_stats(msg)
                elif msg_type == 'complete':
                    self._processing_complete(msg)
                
                self.log_text.see(tk.END)
        
        except queue.Empty:
            pass
        
        # Schedule next check
        self.root.after(100, self._check_queue)
    
    def _update_stats(self, stats):
        """Update statistics display."""
        total = stats['wanted'] + stats['unwanted'] + stats['non_image_files']
        stats_text = (
            f"Total: {total} | Wanted: {stats['wanted']} | "
            f"Unwanted: {stats['unwanted']} | Non-images: {stats['non_image_files']} | "
            f"Errors: {stats['errors']}"
        )
        self.stats_label.config(text=stats_text)
    
    def _processing_complete(self, message):
        """Handle processing completion."""
        self.log_text.insert(tk.END, '\n' + message + '\n', 'info')
        self.log_text.see(tk.END)
        
        self.processing = False
        self.start_button.config(state='normal')
        self.dry_run_button.config(state='normal')
        self.stop_button.config(state='disabled')
        self.progress_bar.stop()
        
        self._update_status('Processing complete')
    
    def _export_log(self):
        """Export log to file."""
        file_path = filedialog.asksaveasfilename(
            defaultextension='.txt',
            filetypes=[('Text files', '*.txt'), ('All files', '*.*')]
        )
        
        if file_path:
            try:
                with open(file_path, 'w') as f:
                    f.write(self.log_text.get(1.0, tk.END))
                messagebox.showinfo('Success', f'Log exported to {file_path}')
                self._update_status(f'Log exported to {file_path}')
            except Exception as e:
                messagebox.showerror('Error', f'Failed to export log: {e}')
    
    def _update_status(self, message):
        """Update status bar."""
        self.status_label.config(text=message)
    
    def _get_image_files(self, folder_path):
        """Get list of image files from a folder."""
        if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
            return []
        
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp', '.gif'}
        image_files = []
        
        for file in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file)
            if os.path.isfile(file_path):
                ext = os.path.splitext(file)[1].lower()
                if ext in image_extensions:
                    image_files.append(file_path)
        
        return sorted(image_files)
    
    def _create_image_viewer_tab(self, parent_frame, folder_key, tab_name, transfer_options):
        """Create an image viewer tab with navigation and transfer buttons."""
        # Main container
        main_frame = ttk.Frame(parent_frame)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Image display frame with navigation buttons on sides
        image_frame = ttk.Frame(main_frame)
        image_frame.pack(fill='both', expand=True, pady=10)
        
        # Left arrow button
        left_btn = ttk.Button(image_frame, text='◀', width=3, command=lambda fk=folder_key: self._navigate_image(fk, -1))
        left_btn.pack(side='left', padx=5, pady=5)
        setattr(self, f'{folder_key}_left_btn', left_btn)
        
        # Image label (center)
        image_label = ttk.Label(image_frame, text='No images found', anchor='center')
        image_label.pack(side='left', fill='both', expand=True, padx=5)
        setattr(self, f'{folder_key}_image_label', image_label)
        
        # Right arrow button
        right_btn = ttk.Button(image_frame, text='▶', width=3, command=lambda fk=folder_key: self._navigate_image(fk, 1))
        right_btn.pack(side='right', padx=5, pady=5)
        setattr(self, f'{folder_key}_right_btn', right_btn)
        
        # Function bar
        func_frame = ttk.LabelFrame(main_frame, text='Image Information', padding=10)
        func_frame.pack(fill='x', pady=5)
        
        # Image count label
        count_label = ttk.Label(func_frame, text='Image: 0/0', width=20)
        count_label.grid(row=0, column=0, sticky='w', padx=5)
        setattr(self, f'{folder_key}_count_label', count_label)
        
        # Image name and size label
        name_label = ttk.Label(func_frame, text='Name: -', width=40)
        name_label.grid(row=0, column=1, sticky='w', padx=20)
        setattr(self, f'{folder_key}_name_label', name_label)
        
        # Metadata label
        metadata_label = ttk.Label(func_frame, text='Metadata: -', width=35)
        metadata_label.grid(row=1, column=0, columnspan=2, sticky='w', padx=5, pady=2)
        setattr(self, f'{folder_key}_metadata_label', metadata_label)
        
        # Transfer buttons frame
        transfer_frame = ttk.Frame(func_frame)
        transfer_frame.grid(row=0, column=2, rowspan=2, sticky='e', padx=5)
        
        # Create transfer buttons based on options
        for option in transfer_options:
            if option == 'Clear all':
                btn = ttk.Button(transfer_frame, text=option, command=self._clear_unwanted_folder)
            else:
                target_folder = option.replace('Transfer to ', '')
                # Use default parameter to capture values correctly
                btn = ttk.Button(transfer_frame, text=option, 
                               command=lambda t=target_folder, fk=folder_key: self._transfer_image(fk, t))
            btn.pack(side='left', padx=2)
        
        # Configure column weights to prevent expansion
        func_frame.columnconfigure(0, weight=0)
        func_frame.columnconfigure(1, weight=0)
        func_frame.columnconfigure(2, weight=0)
        
        # Store folder key and current index
        setattr(self, f'{folder_key}_images', [])
        setattr(self, f'{folder_key}_current_index', 0)
        setattr(self, f'{folder_key}_folder_key', folder_key)
        
        # Bind tab change event if not already bound
        if not hasattr(self, '_tab_change_bound'):
            self.notebook.bind('<<NotebookTabChanged>>', self._on_tab_changed)
            self._tab_change_bound = True
    
    def _create_import_tab(self):
        """Create Import tab with image viewer."""
        import_frame = ttk.Frame(self.notebook)
        self.notebook.add(import_frame, text='Import')
        self.import_tab_index = self.notebook.index('end') - 1
        self._create_image_viewer_tab(
            import_frame, 
            'import', 
            'Import',
            ['Transfer to Wanted', 'Transfer to Unwanted']
        )
        # Load images initially
        self._load_images('import')
    
    def _create_wanted_tab(self):
        """Create Wanted tab with image viewer."""
        wanted_frame = ttk.Frame(self.notebook)
        self.notebook.add(wanted_frame, text='Wanted')
        self.wanted_tab_index = self.notebook.index('end') - 1
        self._create_image_viewer_tab(
            wanted_frame,
            'wanted',
            'Wanted',
            ['Transfer to Import', 'Transfer to Unwanted']
        )
        # Load images initially
        self._load_images('wanted')
    
    def _create_unwanted_tab(self):
        """Create Unwanted tab with image viewer."""
        unwanted_frame = ttk.Frame(self.notebook)
        self.notebook.add(unwanted_frame, text='Unwanted')
        self.unwanted_tab_index = self.notebook.index('end') - 1
        self._create_image_viewer_tab(
            unwanted_frame,
            'unwanted',
            'Unwanted',
            ['Transfer to Import', 'Transfer to Wanted', 'Clear all']
        )
        # Load images initially
        self._load_images('unwanted')
    
    def _on_tab_changed(self, event=None):
        """Handle tab change event to load images."""
        selected_tab = self.notebook.index(self.notebook.select())
        tab_text = self.notebook.tab(selected_tab, 'text')
        
        if tab_text.startswith('Import'):
            self._active_image_folder_key = 'import'
            self._load_images('import')
        elif tab_text.startswith('Wanted'):
            self._active_image_folder_key = 'wanted'
            self._load_images('wanted')
        elif tab_text.startswith('Unwanted'):
            self._active_image_folder_key = 'unwanted'
            self._load_images('unwanted')
        elif tab_text.startswith('Duplicated'):
            self._active_image_folder_key = None
            self._load_duplicates()
        else:
            self._active_image_folder_key = None
    
    def _load_images(self, folder_key):
        """Load images for a specific folder."""
        # Get folder path from config
        if folder_key == 'import':
            folder_path = self.config.get('import_path', './Import')
        elif folder_key == 'wanted':
            folder_path = self.config.get('wanted_path', './Wanted')
        elif folder_key == 'unwanted':
            folder_path = self.config.get('unwanted_path', './Unwanted')
        else:
            return
        
        # Get image files
        image_files = self._get_image_files(folder_path)
        setattr(self, f'{folder_key}_images', image_files)
        setattr(self, f'{folder_key}_current_index', 0)
        
        # Update UI
        count_label = getattr(self, f'{folder_key}_count_label')
        count_label.config(text=f'Image: 0/{len(image_files)}')
        
        # Update tab title with count
        tab_index = getattr(self, f'{folder_key}_tab_index')
        tab_name = folder_key.capitalize()
        self.notebook.tab(tab_index, text=f'{tab_name} ({len(image_files)})')
        
        if image_files:
            self._display_image(folder_key, 0)
        else:
            self._display_no_image(folder_key)
    
    def _display_image(self, folder_key, index):
        """Display image at given index."""
        images = getattr(self, f'{folder_key}_images')
        if not images or index < 0 or index >= len(images):
            return
        
        image_path = images[index]
        setattr(self, f'{folder_key}_current_index', index)
        
        # Update count label
        count_label = getattr(self, f'{folder_key}_count_label')
        count_label.config(text=f'Image: {index + 1}/{len(images)}')
        
        # Update name label with file size
        name_label = getattr(self, f'{folder_key}_name_label')
        file_size = os.path.getsize(image_path) / (1024 * 1024)  # MB
        name_label.config(text=f'Name: {os.path.basename(image_path)} ({file_size:.1f}MB)')
        
        # Update metadata label
        metadata_label = getattr(self, f'{folder_key}_metadata_label')
        sorter = PhotoSorter()  # Create instance to access metadata method
        metadata = sorter._get_image_metadata(Path(image_path))
        metadata_text = []
        if 'width' in metadata and 'height' in metadata:
            metadata_text.append(f"{metadata['width']}x{metadata['height']}")
        if 'exif_date' in metadata:
            metadata_text.append(f"Date: {metadata['exif_date']}")
        if 'camera_model' in metadata:
            metadata_text.append(f"Camera: {metadata['camera_model']}")
        metadata_label.config(text=f'Metadata: {" | ".join(metadata_text)}' if metadata_text else 'Metadata: -')
        
        # Load and display image
        try:
            img = Image.open(image_path)

            # Resize to 70% of original size (then cap to a max display size)
            w, h = img.size
            new_w = max(1, int(w * 0.5))
            new_h = max(1, int(h * 0.5))
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            # Safety cap so huge photos still fit nicely
            max_width, max_height = 700, 500
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            
            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(img)
            
            # Update label
            image_label = getattr(self, f'{folder_key}_image_label')
            image_label.config(image=photo, text='')
            image_label.image = photo  # Keep a reference
            
        except Exception as e:
            image_label = getattr(self, f'{folder_key}_image_label')
            image_label.config(image='', text=f'Error loading image: {str(e)}')

    def _set_active_image_folder_from_tab(self):
        """Set active image folder key based on current tab selection."""
        try:
            selected_tab = self.notebook.index(self.notebook.select())
            tab_text = self.notebook.tab(selected_tab, 'text')
        except Exception:
            self._active_image_folder_key = None
            return

        if tab_text.startswith('Import'):
            self._active_image_folder_key = 'import'
        elif tab_text.startswith('Wanted'):
            self._active_image_folder_key = 'wanted'
        elif tab_text.startswith('Unwanted'):
            self._active_image_folder_key = 'unwanted'
        else:
            self._active_image_folder_key = None

    def _bind_image_navigation_keys(self):
        """Bind Left/Right arrow keys and A/D keys to navigate images in the active image tab."""
        def should_ignore_keypress():
            w = self.root.focus_get()
            if w is None:
                return False
            cls = w.winfo_class()
            # Avoid interfering with text entry widgets
            return cls in {'Entry', 'Text', 'TEntry', 'TCombobox', 'TSpinbox'}

        def on_left(event=None):
            if should_ignore_keypress():
                return
            selected_tab = self.notebook.index(self.notebook.select())
            tab_text = self.notebook.tab(selected_tab, 'text')
            if tab_text.startswith('Import') or tab_text.startswith('Wanted') or tab_text.startswith('Unwanted'):
                fk = self._active_image_folder_key
                if fk in {'import', 'wanted', 'unwanted'}:
                    self._navigate_image(fk, -1)
            elif tab_text.startswith('Duplicated'):
                self._navigate_duplicate_inner(-1)

        def on_right(event=None):
            if should_ignore_keypress():
                return
            selected_tab = self.notebook.index(self.notebook.select())
            tab_text = self.notebook.tab(selected_tab, 'text')
            if tab_text.startswith('Import') or tab_text.startswith('Wanted') or tab_text.startswith('Unwanted'):
                fk = self._active_image_folder_key
                if fk in {'import', 'wanted', 'unwanted'}:
                    self._navigate_image(fk, 1)
            elif tab_text.startswith('Duplicated'):
                self._navigate_duplicate_inner(1)

        # Bind on root so it works regardless of where focus is (except entries/text)
        self.root.bind('<Left>', on_left)
        self.root.bind('<Right>', on_right)
        self.root.bind('a', on_left)
        self.root.bind('d', on_right)
    
    def _display_no_image(self, folder_key):
        """Display message when no images found."""
        image_label = getattr(self, f'{folder_key}_image_label')
        image_label.config(image='', text='No images found')
        
        name_label = getattr(self, f'{folder_key}_name_label')
        name_label.config(text='Name: -')
    
    def _navigate_image(self, folder_key, direction):
        """Navigate to previous/next image."""
        images = getattr(self, f'{folder_key}_images')
        if not images:
            return
        
        current_index = getattr(self, f'{folder_key}_current_index')
        new_index = (current_index + direction) % len(images)
        self._display_image(folder_key, new_index)
    
    def _transfer_image(self, folder_key, target_folder_key):
        """Transfer current image to target folder."""
        images = getattr(self, f'{folder_key}_images')
        current_index = getattr(self, f'{folder_key}_current_index')
        
        if not images or current_index < 0 or current_index >= len(images):
            messagebox.showwarning('Warning', 'No image selected')
            return
        
        source_path = images[current_index]
        source_folder = os.path.dirname(source_path)
        
        # Get target folder path
        if target_folder_key.lower() == 'import':
            target_folder = self.config.get('import_path', './Import')
        elif target_folder_key.lower() == 'wanted':
            target_folder = self.config.get('wanted_path', './Wanted')
        elif target_folder_key.lower() == 'unwanted':
            target_folder = self.config.get('unwanted_path', './Unwanted')
        else:
            messagebox.showerror('Error', 'Invalid target folder')
            return
        
        # Create target folder if it doesn't exist
        os.makedirs(target_folder, exist_ok=True)
        
        # Get destination path
        filename = os.path.basename(source_path)
        dest_path = os.path.join(target_folder, filename)
        
        # Handle filename conflicts
        counter = 1
        base_name, ext = os.path.splitext(filename)
        while os.path.exists(dest_path):
            new_filename = f"{base_name}_{counter}{ext}"
            dest_path = os.path.join(target_folder, new_filename)
            counter += 1
        
        try:
            # Move file
            shutil.move(source_path, dest_path)
            
            # Update image list
            images.pop(current_index)
            setattr(self, f'{folder_key}_images', images)
            
            # Update current index
            if current_index >= len(images):
                current_index = len(images) - 1
            if current_index < 0:
                current_index = 0
            
            setattr(self, f'{folder_key}_current_index', current_index)
            
            # Update UI
            count_label = getattr(self, f'{folder_key}_count_label')
            count_label.config(text=f'Image: {current_index + 1 if images else 0}/{len(images)}')
            
            # Update tab title
            tab_index = getattr(self, f'{folder_key}_tab_index')
            tab_name = folder_key.capitalize()
            self.notebook.tab(tab_index, text=f'{tab_name} ({len(images)})')
            
            if images:
                self._display_image(folder_key, current_index)
            else:
                self._display_no_image(folder_key)
            
            self._update_status(f'Image moved to {target_folder_key}')
            
        except Exception as e:
            messagebox.showerror('Error', f'Failed to move image: {str(e)}')
    
    def _clear_unwanted_folder(self):
        """Clear all images from Unwanted folder with confirmation."""
        # Double confirmation
        if not messagebox.askyesno('Warning', 
                                  'Are you sure you want to clear ALL images from the Unwanted folder?\n\n'
                                  'This action cannot be undone!'):
            return
        
        if not messagebox.askyesno('Final Confirmation', 
                                  'This will permanently delete all files in the Unwanted folder.\n\n'
                                  'Are you absolutely sure?'):
            return
        
        unwanted_path = self.config.get('unwanted_path', './Unwanted')
        
        if not os.path.exists(unwanted_path):
            messagebox.showinfo('Info', 'Unwanted folder does not exist or is empty')
            return
        
        try:
            deleted_count = 0
            for file in os.listdir(unwanted_path):
                file_path = os.path.join(unwanted_path, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    deleted_count += 1
            
            # Reload images
            self._load_images('unwanted')
            
            messagebox.showinfo('Success', f'Cleared {deleted_count} file(s) from Unwanted folder')
            self._update_status(f'Cleared {deleted_count} file(s) from Unwanted folder')
            
        except Exception as e:
            messagebox.showerror('Error', f'Failed to clear folder: {str(e)}')
    
    def _load_duplicates(self):
        """Load duplicate groups from Wanted folder."""
        DUPLICATE_CACHE_FILE = 'duplicate_cache.txt'
        
        # Check if cache exists
        if os.path.exists(DUPLICATE_CACHE_FILE):
            try:
                duplicate_groups = []
                with open(DUPLICATE_CACHE_FILE, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            paths = [path.strip() for path in line.split(',')]
                            duplicate_groups.append(paths)
                
                setattr(self, 'duplicate_groups', duplicate_groups)
                setattr(self, 'current_set_index', 0)
                setattr(self, 'current_image_index', 0)
                
                # Update progress label
                progress_label = getattr(self, 'duplicated_progress_label')
                if duplicate_groups:
                    progress_label.config(text=f'Duplicate Set #1 of {len(duplicate_groups)}')
                else:
                    progress_label.config(text='Duplicate Set #0 of 0')
                
                # Update tab title
                self.notebook.tab(self.duplicated_tab_index, text=f'Duplicated ({len(duplicate_groups)} sets)')
                
                if duplicate_groups:
                    self._display_duplicate_image(0, 0)
                else:
                    self._display_no_duplicates()
                return
            except Exception as e:
                print(f"Error loading duplicate cache: {e}")
        
        # No cache, compute duplicates
        wanted_path = self.config.get('wanted_path', './Wanted')
        sorter = PhotoSorter()
        duplicate_groups = sorter.find_duplicate_groups(wanted_path)
        
        # Save to cache
        try:
            with open(DUPLICATE_CACHE_FILE, 'w') as f:
                for group in duplicate_groups:
                    line = ','.join(str(path) for path in group)
                    f.write(line + '\n')
        except Exception as e:
            print(f"Error saving duplicate cache: {e}")
        
        setattr(self, 'duplicate_groups', duplicate_groups)
        setattr(self, 'current_set_index', 0)
        setattr(self, 'current_image_index', 0)
        
        # Update progress label
        progress_label = getattr(self, 'duplicated_progress_label')
        if duplicate_groups:
            progress_label.config(text=f'Duplicate Set #1 of {len(duplicate_groups)}')
        else:
            progress_label.config(text='Duplicate Set #0 of 0')
        
        # Update tab title
        self.notebook.tab(self.duplicated_tab_index, text=f'Duplicated ({len(duplicate_groups)} sets)')
        
        if duplicate_groups:
            self._display_duplicate_image(0, 0)
        else:
            self._display_no_duplicates()
    
    def _display_duplicate_image(self, set_index, image_index):
        """Display image from duplicate set."""
        duplicate_groups = getattr(self, 'duplicate_groups')
        if not duplicate_groups or set_index < 0 or set_index >= len(duplicate_groups):
            return
        
        current_set = duplicate_groups[set_index]
        if image_index < 0 or image_index >= len(current_set):
            return
        
        image_path = current_set[image_index]
        setattr(self, 'current_set_index', set_index)
        setattr(self, 'current_image_index', image_index)
        
        # Update progress label
        progress_label = getattr(self, 'duplicated_progress_label')
        progress_label.config(text=f'Duplicate Set #{set_index + 1} of {len(duplicate_groups)}')
        
        # Update count label
        count_label = getattr(self, 'duplicated_count_label')
        count_label.config(text=f'Image: {image_index + 1}/{len(current_set)}')
        
        # Update name label with file size
        name_label = getattr(self, 'duplicated_name_label')
        file_size = os.path.getsize(image_path) / (1024 * 1024)  # MB
        name_label.config(text=f'Name: {os.path.basename(image_path)} ({file_size:.1f}MB)')
        
        # Update metadata label
        metadata_label = getattr(self, 'duplicated_metadata_label')
        sorter = PhotoSorter()
        metadata = sorter._get_image_metadata(Path(image_path))
        metadata_text = []
        if 'width' in metadata and 'height' in metadata:
            metadata_text.append(f"{metadata['width']}x{metadata['height']}")
        if 'exif_date' in metadata:
            metadata_text.append(f"Date: {metadata['exif_date']}")
        if 'camera_model' in metadata:
            metadata_text.append(f"Camera: {metadata['camera_model']}")
        metadata_label.config(text=f'Metadata: {" | ".join(metadata_text)}' if metadata_text else 'Metadata: -')
        
        # Load and display image
        try:
            img = Image.open(image_path)
            
            # Resize for display
            w, h = img.size
            new_w = max(1, int(w * 0.5))
            new_h = max(1, int(h * 0.5))
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
            max_width, max_height = 700, 500
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            
            photo = ImageTk.PhotoImage(img)
            image_label = getattr(self, 'duplicated_image_label')
            image_label.config(image=photo, text='')
            image_label.image = photo
            
        except Exception as e:
            image_label = getattr(self, 'duplicated_image_label')
            image_label.config(image='', text=f'Error loading image: {str(e)}')
    
    def _display_no_duplicates(self):
        """Display message when no duplicates found."""
        image_label = getattr(self, 'duplicated_image_label')
        image_label.config(image='', text='No duplicates found in Wanted folder')
        
        count_label = getattr(self, 'duplicated_count_label')
        count_label.config(text='Image: 0/0')
        
        name_label = getattr(self, 'duplicated_name_label')
        name_label.config(text='Name: -')
        
        metadata_label = getattr(self, 'duplicated_metadata_label')
        metadata_label.config(text='Metadata: -')
    
    def _navigate_duplicate_set(self, direction):
        """Navigate between duplicate sets."""
        duplicate_groups = getattr(self, 'duplicate_groups')
        if not duplicate_groups:
            return
        
        current_set_index = getattr(self, 'current_set_index')
        new_set_index = (current_set_index + direction) % len(duplicate_groups)
        self._display_duplicate_image(new_set_index, 0)
    
    def _navigate_duplicate_inner(self, direction):
        """Navigate within current duplicate set."""
        duplicate_groups = getattr(self, 'duplicate_groups')
        if not duplicate_groups:
            return
        
        current_set_index = getattr(self, 'current_set_index')
        current_image_index = getattr(self, 'current_image_index')
        current_set = duplicate_groups[current_set_index]
        
        new_image_index = (current_image_index + direction) % len(current_set)
        self._display_duplicate_image(current_set_index, new_image_index)
    
    def _transfer_duplicate_image(self, target_folder_key):
        """Transfer current duplicate image to target folder."""
        duplicate_groups = getattr(self, 'duplicate_groups')
        current_set_index = getattr(self, 'current_set_index')
        current_image_index = getattr(self, 'current_image_index')
        
        if not duplicate_groups or current_set_index >= len(duplicate_groups):
            messagebox.showwarning('Warning', 'No duplicate set selected')
            return
        
        current_set = duplicate_groups[current_set_index]
        if current_image_index >= len(current_set):
            messagebox.showwarning('Warning', 'No image selected')
            return
        
        source_path = current_set[current_image_index]
        
        # Get target folder
        if target_folder_key == 'import':
            target_folder = self.config.get('import_path', './Import')
        elif target_folder_key == 'wanted':
            target_folder = self.config.get('wanted_path', './Wanted')
        elif target_folder_key == 'unwanted':
            target_folder = self.config.get('unwanted_path', './Unwanted')
        else:
            return
        
        # Move file
        try:
            base_name = os.path.basename(source_path)
            dest_path = os.path.join(target_folder, base_name)
            
            # Handle conflicts
            if os.path.exists(dest_path):
                name, ext = os.path.splitext(base_name)
                counter = 1
                while os.path.exists(dest_path):
                    dest_path = os.path.join(target_folder, f"{name}_{counter}{ext}")
                    counter += 1
            
            shutil.move(source_path, dest_path)
            
            # Remove from duplicate set
            current_set.pop(current_image_index)
            
            # If set is empty, remove it
            if not current_set:
                duplicate_groups.pop(current_set_index)
                if current_set_index >= len(duplicate_groups):
                    current_set_index = max(0, len(duplicate_groups) - 1)
                current_image_index = 0
            else:
                if current_image_index >= len(current_set):
                    current_image_index = len(current_set) - 1
            
            # Update display
            if duplicate_groups:
                self._display_duplicate_image(current_set_index, current_image_index)
            else:
                self._display_no_duplicates()
                
        except Exception as e:
            messagebox.showerror('Error', f'Failed to transfer image: {str(e)}')
    
    def _keep_one_duplicate(self):
        """Keep the largest file in current duplicate set, delete others."""
        duplicate_groups = getattr(self, 'duplicate_groups')
        current_set_index = getattr(self, 'current_set_index')
        
        if not duplicate_groups or current_set_index >= len(duplicate_groups):
            messagebox.showwarning('Warning', 'No duplicate set selected')
            return
        
        current_set = duplicate_groups[current_set_index]
        if len(current_set) < 2:
            messagebox.showinfo('Info', 'Only one image in this set')
            return
        
        # Find image with largest file size
        largest_index = 0
        largest_size = 0
        for i, img_path in enumerate(current_set):
            try:
                size = os.path.getsize(img_path)
                if size > largest_size:
                    largest_size = size
                    largest_index = i
            except:
                continue
        
        # Keep the largest, delete others
        kept_path = current_set[largest_index]
        deleted_paths = []
        
        for i, img_path in enumerate(current_set):
            if i != largest_index:
                try:
                    os.remove(img_path)
                    deleted_paths.append(os.path.basename(img_path))
                except Exception as e:
                    print(f"Error deleting {img_path}: {e}")
        
        # Remove the set from groups
        duplicate_groups.pop(current_set_index)
        
        # Update indices
        if current_set_index >= len(duplicate_groups):
            current_set_index = max(0, len(duplicate_groups) - 1)
        current_image_index = 0
        
        # Update display
        if duplicate_groups:
            self._display_duplicate_image(current_set_index, 0)
        else:
            self._display_no_duplicates()
        
        # Show confirmation
        messagebox.showinfo('Success', f'Kept: {os.path.basename(kept_path)}\nDeleted: {", ".join(deleted_paths)}')


def main():
    """Main entry point."""
    paths = ['Import', 'Wanted', 'Unwanted']
    for path in paths:
        if not os.path.exists(path):
            os.makedirs(path)
    
    root = tk.Tk()
    app = PhotoSorterGUI(root)
    
    # Hotkeys
    root.bind('<Control-r>', lambda e: app._start_processing() if not app.processing else None)
    root.bind('<Control-s>', lambda e: app._save_config())
    
    root.mainloop()

if __name__ == '__main__':
    main()