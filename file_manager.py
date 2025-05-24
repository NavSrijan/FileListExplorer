import sys
import os
import csv
import threading
import queue
from queue import Queue
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QFileDialog, QMessageBox, QPushButton, QLabel, QSlider, QAbstractItemView, QSplitter, QComboBox
)
from PyQt5.QtCore import Qt, QUrl, QSize, pyqtSignal, QEvent, QTimer
from PyQt5.QtGui import QPixmap, QImage, QIcon, QPixmapCache
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
import hashlib

class FileLoader:
    @staticmethod
    def load_file_paths(csv_path):
        file_paths = []
        with open(csv_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                path = row.get('File Path')
                if path:
                    file_paths.append(path)
        return file_paths

class FileManagerApp(QWidget):
    thumbnail_ready = pyqtSignal(str, int)

    def __init__(self):
        super().__init__()
        self.setWindowTitle('FileListExplorer')
        self.resize(1100, 600)

        # Use QSplitter for resizable panes
        self.splitter = QSplitter(Qt.Horizontal)
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self.splitter)

        # Left: File list
        self.left_widget = QWidget()
        self.left_layout = QVBoxLayout()
        self.left_widget.setLayout(self.left_layout)
        self.splitter.addWidget(self.left_widget)
        self.splitter.setStretchFactor(0, 2)

        self.label = QLabel('No CSV loaded.')
        self.left_layout.addWidget(self.label)

        self.load_button = QPushButton('Load CSV')
        self.load_button.clicked.connect(self.load_csv)
        self.left_layout.addWidget(self.load_button)

        # View mode selector
        self.view_mode_combo = QComboBox()
        self.view_mode_combo.addItems(['List', 'Tiles'])
        self.view_mode_combo.currentIndexChanged.connect(self.change_view_mode)
        self.left_layout.addWidget(self.view_mode_combo)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_widget.setIconSize(QSize(64, 64))
        self.list_widget.itemDoubleClicked.connect(self.open_file)
        self.list_widget.currentItemChanged.connect(self.preview_file)
        self.list_widget.setViewMode(QListWidget.ListMode)
        self.list_widget.setDragEnabled(True)
        self.list_widget.setAcceptDrops(False)
        self.list_widget.setDragDropMode(QAbstractItemView.DragOnly)
        self.left_layout.addWidget(self.list_widget)

        # Right: Preview
        self.right_widget = QWidget()
        self.right_layout = QVBoxLayout()
        self.right_widget.setLayout(self.right_layout)
        self.splitter.addWidget(self.right_widget)
        self.splitter.setStretchFactor(1, 3)

        self.preview_label = QLabel('Preview will appear here.')
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(200)
        self.right_layout.addWidget(self.preview_label)

        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumHeight(200)
        self.right_layout.addWidget(self.video_widget)
        self.video_widget.hide()

        # Video controls
        self.controls_layout = QHBoxLayout()
        self.right_layout.addLayout(self.controls_layout)
        self.play_pause_button = QPushButton('Pause')
        self.play_pause_button.clicked.connect(self.toggle_play_pause)
        self.controls_layout.addWidget(self.play_pause_button)
        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 0)
        self.controls_layout.addWidget(self.seek_slider)
        self.controls_layout.setStretch(0, 0)
        self.controls_layout.setStretch(1, 1)
        self.play_pause_button.hide()
        self.seek_slider.hide()
        self.setup_video_slider()  # Connect slider signals for seeking

        self.media_player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.media_player.setVideoOutput(self.video_widget)
        self.media_player.positionChanged.connect(self.position_changed)
        self.media_player.durationChanged.connect(self.duration_changed)
        self.media_player.stateChanged.connect(self.media_state_changed)

        self.file_paths = []
        self.file_sizes = []
        self.thumbnail_cache = {}
        self.icon_size = 64
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setMinimum(32)
        self.zoom_slider.setMaximum(192)
        self.zoom_slider.setValue(self.icon_size)
        self.zoom_slider.setTickInterval(8)
        self.zoom_slider.setTickPosition(QSlider.TicksBelow)
        self.zoom_slider.valueChanged.connect(self.set_icon_size)
        self.left_layout.addWidget(self.zoom_slider)
        self.zoom_slider.hide()  # Only show in Tiles mode

        self.thumbnail_timer = QTimer(self)
        self.thumbnail_timer.setSingleShot(True)
        self.thumbnail_timer.timeout.connect(self.update_visible_thumbnails_batch)
        self.list_widget.verticalScrollBar().valueChanged.connect(self.schedule_thumbnail_update)
        self.list_widget.horizontalScrollBar().valueChanged.connect(self.schedule_thumbnail_update)
        # Remove eventFilter for less lag

        self.item_refs = []  # Keep references to items for updating icons

        self.thumbnail_ready.connect(self.update_thumbnail_icon)
        self.thumbnail_queue = queue.Queue()
        self.thumbnail_thread = threading.Thread(target=self.thumbnail_worker, daemon=True)
        self.thumbnail_thread.start()
        self.current_preview_path = None
        self.current_preview_image = None
        self.thumbnail_dir = os.path.join(os.path.dirname(__file__), '.thumbnails')
        os.makedirs(self.thumbnail_dir, exist_ok=True)
        self.thumbnail_map = {}  # {(path, icon_size): thumb_path}

    def normalize_path(self, path):
        # If on Windows and path is Linux-style, convert /mnt/c/... to C:\...
        if sys.platform.startswith('win'):
            if path.startswith('/mnt/') and len(path) > 6:
                drive = path[5].upper() + ':'
                rest = path[6:]
                win_path = os.path.join(drive, *rest.split('/'))
                return os.path.normpath(win_path)
            elif path.startswith('/'):
                # Try to convert /c/... to C:\...
                parts = path.strip('/').split('/')
                if len(parts) > 1 and len(parts[0]) == 1:
                    drive = parts[0].upper() + ':'
                    rest = os.path.join(*parts[1:])
                    return os.path.normpath(os.path.join(drive, rest))
        return os.path.normpath(path)

    def set_icon_size(self, value):
        self.icon_size = value
        self.list_widget.setIconSize(QSize(self.icon_size, self.icon_size))
        if self.list_widget.viewMode() == QListWidget.IconMode:
            # Set grid size for tile mode
            self.list_widget.setGridSize(QSize(self.icon_size + 48, self.icon_size + 36))
        # Only queue missing thumbnails for new size
        for item in self.item_refs:
            path = item.data(Qt.UserRole)
            ext = item.data(Qt.UserRole + 1)
            if ext in ['.jpg', '.jpeg', '.png', '.bmp', '.gif'] and os.path.exists(path):
                thumb_path = self.get_thumbnail_path(path, self.icon_size)
                self.thumbnail_map[(path, self.icon_size)] = thumb_path
                if not os.path.exists(thumb_path):
                    self.thumbnail_queue.put((path, self.icon_size))
        self.schedule_thumbnail_update()

    def change_view_mode(self, idx):
        if idx == 0:
            self.list_widget.setViewMode(QListWidget.ListMode)
            self.list_widget.setFlow(QListWidget.TopToBottom)
            self.list_widget.setWrapping(False)
            self.zoom_slider.hide()
        else:
            self.list_widget.setViewMode(QListWidget.IconMode)
            self.list_widget.setFlow(QListWidget.LeftToRight)
            self.list_widget.setWrapping(True)
            self.list_widget.setGridSize(QSize(self.icon_size + 48, self.icon_size + 36))
            self.zoom_slider.show()
        self.schedule_thumbnail_update()

    def schedule_thumbnail_update(self):
        self.thumbnail_timer.start(150)  # Debounce thumbnail update

    def update_visible_thumbnails_batch(self):
        viewport = self.list_widget.viewport()
        for i in range(1, self.list_widget.count()):  # skip header
            item = self.list_widget.item(i)
            rect = self.list_widget.visualItemRect(item)
            if viewport.rect().intersects(rect):
                path = item.data(Qt.UserRole)
                ext = item.data(Qt.UserRole + 1)
                if ext in ['.jpg', '.jpeg', '.png', '.bmp', '.gif'] and os.path.exists(path):
                    thumb_path = self.get_thumbnail_path(path, self.icon_size)
                    if os.path.exists(thumb_path):
                        item.setIcon(QIcon(thumb_path))
                elif ext in ['.mp4', '.avi', '.mov', '.mkv', '.wmv']:
                    item.setIcon(self.style().standardIcon(QLabel().style().SP_MediaPlay))
                else:
                    item.setIcon(self.style().standardIcon(QLabel().style().SP_FileIcon))

    def update_thumbnail_icon(self, path, icon_size):
        thumb_path = self.get_thumbnail_path(path, icon_size)
        for item in self.item_refs:
            if item.data(Qt.UserRole) == path:
                if os.path.exists(thumb_path):
                    item.setIcon(QIcon(thumb_path))

    def thumbnail_worker(self):
        while True:
            try:
                path, icon_size = self.thumbnail_queue.get()
                thumb_path = self.get_thumbnail_path(path, icon_size)
                if not os.path.exists(thumb_path):
                    self.create_and_save_thumbnail(path, thumb_path, icon_size)
                self.thumbnail_ready.emit(path, icon_size)
            except Exception:
                pass

    def get_thumbnail_path(self, path, icon_size=None):
        if icon_size is None:
            icon_size = self.icon_size
        norm_path = self.normalize_path(path)
        h = hashlib.md5((norm_path + str(icon_size)).encode('utf-8')).hexdigest()
        return os.path.join(self.thumbnail_dir, f'{h}.png')

    def create_and_save_thumbnail(self, src_path, thumb_path, icon_size=None):
        if icon_size is None:
            icon_size = self.icon_size
        norm_path = self.normalize_path(src_path)
        try:
            pixmap = QPixmap(norm_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(icon_size, icon_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                scaled.save(thumb_path, 'PNG')
        except Exception:
            pass

    def populate_list(self):
        self.list_widget.clear()
        self.item_refs = []
        header = f"{'#':<4} {'Filename':<30} {'Size (bytes)':>15}"
        header_item = QListWidgetItem(header)
        header_item.setFlags(Qt.NoItemFlags)  # Make header unselectable
        self.list_widget.addItem(header_item)
        for idx, (path, size) in enumerate(zip(self.file_paths, self.file_sizes), 1):
            filename = os.path.basename(path)
            display = f"{idx:<4} {filename:<30.30} {size:>15}"
            item = QListWidgetItem(display)
            ext = os.path.splitext(path)[1].lower()
            # Set icon
            if ext in ['.jpg', '.jpeg', '.png', '.bmp', '.gif'] and os.path.exists(path):
                thumb_path = self.get_thumbnail_path(path, self.icon_size)
                self.thumbnail_map[(path, self.icon_size)] = thumb_path
                if os.path.exists(thumb_path):
                    item.setIcon(QIcon(thumb_path))
                else:
                    item.setIcon(self.style().standardIcon(QLabel().style().SP_FileIcon))
                    self.thumbnail_queue.put((path, self.icon_size))
            elif ext in ['.mp4', '.avi', '.mov', '.mkv', '.wmv']:
                item.setIcon(self.style().standardIcon(QLabel().style().SP_MediaPlay))
            else:
                item.setIcon(self.style().standardIcon(QLabel().style().SP_FileIcon))
            item.setToolTip(path)
            item.setData(Qt.UserRole, path)
            item.setData(Qt.UserRole + 1, ext)
            self.list_widget.addItem(item)
            self.item_refs.append(item)

    def open_file(self, item):
        path = item.data(Qt.UserRole)
        norm_path = self.normalize_path(path)
        if not os.path.exists(norm_path):
            QMessageBox.warning(self, 'File Not Found', f'File does not exist:\n{norm_path}')
            return
        if sys.platform.startswith('win'):
            os.startfile(norm_path)
        else:
            try:
                import subprocess
                subprocess.Popen(['xdg-open', norm_path])
            except Exception as e:
                QMessageBox.information(self, 'Open File', f'Could not open file.\nPath: {norm_path}\nError: {e}')

    def load_csv(self):
        csv_path, _ = QFileDialog.getOpenFileName(self, 'Open CSV File', '', 'CSV Files (*.csv)')
        if not csv_path:
            return
        try:
            self.file_paths, self.file_sizes = self.load_file_paths_and_sizes(csv_path)
            self.populate_list()
            self.label.setText(f'Loaded: {os.path.basename(csv_path)}')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to load CSV: {e}')

    def load_file_paths_and_sizes(self, csv_path):
        paths = []
        sizes = []
        with open(csv_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                path = row.get('File Path')
                size = row.get('File Size (bytes)')
                if path:
                    paths.append(path)
                    sizes.append(size if size else '')
        return paths, sizes

    def resizeEvent(self, event):
        if self.current_preview_image is not None:
            scaled = QPixmap.fromImage(self.current_preview_image).scaled(
                self.preview_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.preview_label.setPixmap(scaled)
        super().resizeEvent(event)

    def set_position(self, position):
        self.media_player.setPosition(position)

    def preview_file(self, current, previous):
        self.media_player.stop()
        self.video_widget.hide()
        self.play_pause_button.hide()
        self.seek_slider.hide()
        self.preview_label.show()
        self.current_preview_path = None
        self.current_preview_image = None
        if not current:
            self.preview_label.setText('Preview will appear here.')
            return
        path = current.data(Qt.UserRole)
        norm_path = self.normalize_path(path)
        ext = os.path.splitext(norm_path)[1].lower()
        if ext in ['.jpg', '.jpeg', '.png', '.bmp', '.gif']:
            if os.path.exists(norm_path):
                self.current_preview_path = norm_path
                image = QImage(norm_path)
                if image.isNull():
                    self.preview_label.setText('Cannot load image.')
                    self.current_preview_image = None
                else:
                    self.current_preview_image = image
                    pixmap = QPixmap.fromImage(image)
                    scaled = pixmap.scaled(self.preview_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.preview_label.setPixmap(scaled)
            else:
                self.preview_label.setText('Image file not found.')
                self.current_preview_image = None
        elif ext in ['.mp4', '.avi', '.mov', '.mkv', '.wmv']:
            if os.path.exists(norm_path):
                self.preview_label.hide()
                self.video_widget.show()
                self.play_pause_button.show()
                self.seek_slider.show()
                self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(norm_path)))
                self.media_player.play()
                self.play_pause_button.setText('Pause')
            else:
                self.preview_label.setText('Video file not found.')
                self.current_preview_image = None
        else:
            self.preview_label.setText('No preview available for this file type.')
            self.current_preview_image = None

    def toggle_play_pause(self):
        if self.media_player.state() == QMediaPlayer.PlayingState:
            self.media_player.pause()
            self.play_pause_button.setText('Play')
        else:
            self.media_player.play()
            self.play_pause_button.setText('Pause')

    def position_changed(self, position):
        self.seek_slider.setValue(position)

    def duration_changed(self, duration):
        self.seek_slider.setRange(0, duration)

    def media_state_changed(self, state):
        if state == QMediaPlayer.PlayingState:
            self.play_pause_button.setText('Pause')
        else:
            self.play_pause_button.setText('Play')

    # Connect sliderMoved and sliderReleased for seeking
    def setup_video_slider(self):
        self.seek_slider.sliderMoved.connect(self.set_position)
        self.seek_slider.sliderReleased.connect(lambda: self.set_position(self.seek_slider.value()))

if __name__ == '__main__':
    print('Starting FileListExplorer...')
    try:
        app = QApplication(sys.argv)
        window = FileManagerApp()
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        print(f'Error starting application: {e}')
