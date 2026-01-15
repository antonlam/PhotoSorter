"""
PhotoSorter GUI: A professional Tkinter GUI application for the PhotoSorter script.

Features:
- Configurable parameters (folders, thresholds, extensions, etc.)
- Preview tab with image scanning and statistics
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

# Import PhotoSorter class from main.py
from main import PhotoSorter


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
        'rename': True,
        'verbose': True,
        'recursive_scan': True,
        'supported_extensions': ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'],
        'non_image_handling': 'Move to Wanted',
        'filename_conflict': 'Counter'
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
            
            # Update supported extensions
            sorter.SUPPORTED_EXTENSIONS = set(self.config['supported_extensions'])
            
            # Log start
            self.output_queue.put(('info', f"Starting {'dry-run ' if self.dry_run else ''}image processing..."))
            self.output_queue.put(('info', f"Import path: {self.config['import_path']}"))
            self.output_queue.put(('info', f"Wanted path: {self.config['wanted_path']}"))
            self.output_queue.put(('info', f"Unwanted path: {self.config['unwanted_path']}"))
            self.output_queue.put(('info', f"Thresholds: {self.config['white_threshold_percent']}% white, {self.config['white_pixel_min']} RGB min"))
            self.output_queue.put(('info', ''))
            
            if self.dry_run:
                self._dry_run_scan(sorter)
            else:
                # Process images
                sorter.process_images()
                
                # Send stats
                self.output_queue.put(('stats', sorter.stats))
            
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


class PhotoSorterGUI:
    """Main GUI application for PhotoSorter."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("PhotoSorter GUI - Professional Image Organizer")
        self.root.geometry("1000x700")
        self.root.minsize(800, 600)
        
        # Configuration
        self.config = ConfigManager.load()
        
        # Threading
        self.worker_thread = None
        self.output_queue = queue.Queue()
        self.processing = False
        
        # Setup UI
        self._setup_styles()
        self._create_widgets()
        self._setup_tooltips()
        self._start_queue_monitor()
    
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
        self._create_preview_tab()
        self._create_processing_tab()
        
        # Status bar
        self._create_status_bar()
    
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
        self._create_path_selector(paths_frame, 'Wanted Folder:', 'wanted_path', 1)
        self._create_path_selector(paths_frame, 'Unwanted Folder:', 'unwanted_path', 2)
        
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
        
        ttk.Button(button_frame, text='Save Config', command=self._save_config).pack(side='left', padx=5)
        ttk.Button(button_frame, text='Load Config', command=self._load_config).pack(side='left', padx=5)
        ttk.Button(button_frame, text='Reset to Defaults', command=self._reset_defaults).pack(side='left', padx=5)
        
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
        
        ttk.Button(parent, text='Browse', command=browse, width=10).grid(row=row, column=2, padx=5)
        
        parent.columnconfigure(1, weight=1)
        setattr(self, f'{config_key}_var', var)
    
    def _create_preview_tab(self):
        """Create Preview tab."""
        preview_frame = ttk.Frame(self.notebook)
        self.notebook.add(preview_frame, text='Preview')
        
        # Scan button
        scan_frame = ttk.Frame(preview_frame, padding=10)
        scan_frame.pack(fill='x')
        
        ttk.Button(scan_frame, text='Scan Folders', command=self._scan_preview).pack(side='left', padx=5)
        ttk.Label(scan_frame, text='(Counts images without moving)', foreground='gray').pack(side='left', padx=5)
        
        # Stats frame
        stats_frame = ttk.LabelFrame(preview_frame, text='Scan Statistics', padding=10)
        stats_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Create tree view for statistics
        self.preview_tree = ttk.Treeview(stats_frame, height=10, columns=('Value',), show='tree headings')
        self.preview_tree.heading('#0', text='Item')
        self.preview_tree.heading('Value', text='Count')
        self.preview_tree.column('#0', width=300)
        self.preview_tree.column('Value', width=100)
        
        scrollbar = ttk.Scrollbar(stats_frame, orient='vertical', command=self.preview_tree.yview)
        self.preview_tree.configure(yscroll=scrollbar.set)
        
        self.preview_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
    
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
        
        self.dry_run_button = ttk.Button(
            control_frame, text='Dry Run', command=self._start_dry_run
        )
        self.dry_run_button.pack(side='left', padx=5)
        
        self.stop_button = ttk.Button(
            control_frame, text='Stop', command=self._stop_processing, state='disabled'
        )
        self.stop_button.pack(side='left', padx=5)
        
        ttk.Button(control_frame, text='Export Log', command=self._export_log).pack(side='left', padx=5)
        
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
        tooltips = {
            'resize_spin': 'Size to resize images to before analysis',
            'white_thresh_scale': 'Percentage threshold for white background classification',
            'white_pixel_spin': 'Minimum RGB value to consider a pixel white',
            'rename_var': 'Rename wanted images with EXIF date prefix',
            'verbose_var': 'Show detailed processing information',
        }
        # Tooltips can be expanded as needed
    
    def _update_white_thresh_label(self, *args):
        """Update white threshold label."""
        self.white_thresh_label.config(text=f"{self.white_thresh_var.get()}%")
    
    def _save_config(self):
        """Save current configuration."""
        self.config.update({
            'import_path': self.import_path_var.get(),
            'wanted_path': self.wanted_path_var.get(),
            'unwanted_path': self.unwanted_path_var.get(),
            'resize_size': self.resize_var.get(),
            'white_threshold_percent': self.white_thresh_var.get(),
            'white_pixel_min': self.white_pixel_var.get(),
            'rename': self.rename_var.get(),
            'verbose': self.verbose_var.get(),
            'recursive_scan': self.recursive_var.get(),
            'supported_extensions': list(self.ext_listbox.get(0, tk.END)),
            'non_image_handling': self.non_image_var.get(),
            'filename_conflict': self.conflict_var.get(),
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
        self.rename_var.set(self.config['rename'])
        self.verbose_var.set(self.config['verbose'])
        self.recursive_var.set(self.config['recursive_scan'])
        
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
            'rename': self.rename_var.get(),
            'verbose': self.verbose_var.get(),
        })
        
        # Start worker thread
        self.worker_thread = PhotoSorterWorker(self.config, self.output_queue, dry_run=True)
        self.worker_thread.start()
    
    def _start_processing(self):
        """Start image processing."""
        if not self._validate_paths():
            messagebox.showerror('Error', 'Invalid paths configuration')
            return
        
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
            'rename': self.rename_var.get(),
            'verbose': self.verbose_var.get(),
        })
        
        # Start worker thread
        self.worker_thread = PhotoSorterWorker(self.config, self.output_queue, dry_run=False)
        self.worker_thread.start()
    
    def _start_dry_run(self):
        """Start dry-run (scan without moving)."""
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
            'rename': self.rename_var.get(),
            'verbose': self.verbose_var.get(),
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


def main():
    """Main entry point."""
    root = tk.Tk()
    app = PhotoSorterGUI(root)
    
    # Hotkeys
    root.bind('<Control-r>', lambda e: app._start_processing() if not app.processing else None)
    root.bind('<Control-s>', lambda e: app._save_config())
    
    root.mainloop()


if __name__ == '__main__':
    main()
