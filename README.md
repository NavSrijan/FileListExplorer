# FileListExplorer

**FileListExplorer** is a high-performance, cross-platform file manager designed to display and preview only a user-supplied, curated list of files from a CSV file. Unlike traditional file managers, FileListExplorer focuses on selective file review, making it ideal for editors, reviewers, and anyone working with a specific set of files.

## Key Features

- **CSV-Driven:** Load a CSV file containing file paths and optional metadata (like file size).
- **Unified List:** View all files in a single, sortable list, regardless of their original folder locations.
- **Thumbnails & Previews:** Fast, cached thumbnails for images; instant video and image preview pane.
- **Resizable & Customizable UI:** Drag to resize panes, switch between list and tile views, and zoom thumbnails in tile mode.
- **Cross-Platform Path Support:** Works with both Windows and Linux-style file paths, even when running on Windows.
- **Drag-and-Drop:** Drag files directly into editing software like Premiere Pro.
- **Optimized Performance:** All heavy operations (like thumbnail generation) are offloaded to background threads for a lag-free experience.

FileListExplorer is perfect for workflows where you need to review, organize, or process a specific set of files—quickly and efficiently.

---

## How to Use

1. **Prepare a CSV file**  
   Create a CSV file listing the files you want to manage. The CSV should have at least a `File Path` column. Optionally, you can include columns like `Filename` and `File Size (bytes)`.

2. **Launch FileListExplorer**  
   Run the application:
   ```
   python file_manager.py
   ```

3. **Load your CSV**  
   - Click the **"Load CSV"** button.
   - Select your CSV file.
   - The files listed in the CSV will appear in the left pane.

4. **Browse and Preview**  
   - Click a file to preview it (image or video) in the right pane.
   - Double-click a file to open it in your system’s default application.
   - Switch between **List** and **Tiles** view using the dropdown.
   - In Tiles view, use the zoom slider to adjust thumbnail size.
   - Drag files from the list into other applications (e.g., video editors).

5. **Supported Platforms**  
   - Works on Windows and Linux.
   - Accepts both Windows and Linux-style file paths in the CSV.

---
## Note for Windows

The video playback may not work, install the standard version of the K-Lite Codec Pack.
https://codecguide.com/download_kl.htm
---

## Sample CSV File

```
Filename,File Size (bytes),File Path
VID_20250518_153950842.mp4,198228378,/mnt/media/Nothing 2a/VID_20250518_153950842.mp4
VID_20250518_000528341.mp4,137962013,/mnt/media/Nothing 2a/VID_20250518_000528341.mp4
photo1.jpg,204800,/mnt/media/Nothing 2a/photo1.jpg
```

- The only required column is `File Path`. Other columns are optional and used for display.

---
