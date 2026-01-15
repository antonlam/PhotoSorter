import os
import sys
import shutil
import time
import argparse

def get_unique_dest(top_dir, name):
    base_name, ext = os.path.splitext(name)
    dest = os.path.join(top_dir, name)
    counter = 1
    while os.path.exists(dest):
        new_name = f"{base_name}_{counter}{ext}"
        dest = os.path.join(top_dir, new_name)
        counter += 1
    return dest

def remove_empty_dirs(top_dir):
    """Force remove empty dirs with retry."""
    removed = 0
    for root, dirs, files in os.walk(top_dir, topdown=False):
        if root == top_dir: continue
        # Clear any stray files first
        for name in files:
            try:
                os.remove(os.path.join(root, name))
                print(f"Stray file removed: {os.path.relpath(os.path.join(root, name), top_dir)}")
            except OSError as e:
                print(f"Skip stray file {name}: {e}")
        # Remove dirs
        for dname in list(dirs):  # Copy list as we modify
            dpath = os.path.join(root, dname)
            for attempt in range(3):  # Retry
                try:
                    if not os.listdir(dpath):
                        os.rmdir(dpath)
                        print(f"Removed empty dir: {os.path.relpath(dpath, top_dir)}")
                        removed += 1
                        break
                    else:
                        print(f"Dir not empty (attempt {attempt+1}): {os.path.relpath(dpath, top_dir)} -> {os.listdir(dpath)}")
                except OSError as e:
                    print(f"Retry {attempt+1} failed for {os.path.relpath(dpath, top_dir)}: {e}")
                    time.sleep(0.1)
            else:
                # Last resort
                shutil.rmtree(dpath, ignore_errors=True)
                print(f"Force rmtree: {os.path.relpath(dpath, top_dir)}")
                removed += 1
    return removed

def flatten_folder(top_dir):
    moved_count = 0
    print(f"Flattening {top_dir}...")
    for root, dirs, files in os.walk(top_dir, topdown=False):
        if root == top_dir: continue
        print(f"Processing: {os.path.relpath(root, top_dir)} (files: {len(files)}, dirs: {len(dirs)})")
        for name in files:
            src = os.path.join(root, name)
            atime = os.path.getatime(src)
            mtime = os.path.getmtime(src)
            dest = get_unique_dest(top_dir, name)
            shutil.move(src, dest)
            os.utime(dest, (atime, mtime))
            print(f"  Moved: {os.path.basename(src)} -> {os.path.basename(dest)}")
            moved_count += 1
    print("Files moved. Cleaning dirs...")
    dir_removed = remove_empty_dirs(top_dir)
    print(f"Summary: {moved_count} files moved, {dir_removed} dirs removed.")
    # Final check
    # Final check and selective cleanup
    subdirs = [d for d in os.listdir(top_dir) if os.path.isdir(os.path.join(top_dir, d))]
    if subdirs:
        print(f"Found remaining subdirs: {subdirs}")
        for dname in subdirs:
            dpath = os.path.join(top_dir, dname)
            contents = os.listdir(dpath)
            print(f"Final check: {os.path.relpath(dpath, top_dir)} -> contents: {contents}")
            if contents:
                print(f"  Skipping (has {len(contents)} items): {os.path.relpath(dpath, top_dir)}")
            else:
                shutil.rmtree(dpath, ignore_errors=True)
                print(f"  Force removed empty: {os.path.relpath(dpath, top_dir)}")
    else:
        print("Fully flattened: No subdirs left!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Flatten folder with force dir cleanup.")
    parser.add_argument("dir", nargs="?", default=".", help="Top directory")
    args = parser.parse_args()
    top_dir = os.path.abspath(args.dir)
    if not os.path.isdir(top_dir):
        print(f"Error: {top_dir} not a dir.", file=sys.stderr)
        sys.exit(1)
    flatten_folder(top_dir)
