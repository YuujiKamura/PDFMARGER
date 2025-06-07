from PyQt6.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QLabel,
    QAbstractItemView,
    QDialog,
    QVBoxLayout,
    QScrollArea,
    QMessageBox,
    QWidget,
    QHBoxLayout,
    QPushButton,
    QMenu,
    QFileDialog,
    QApplication,
)
from PyQt6.QtCore import (
    Qt,
    QSize,
    QThreadPool,
    QRunnable,
    pyqtSignal,
    QObject,
    QTimer,
    QPoint,
)
import os
import pprint
import json
from collections import namedtuple
from components.pdf_preview_widget import PDFPreviewWidget
from components.path_manager import get_appdata_path
from components.loading_animation_widget import LoadingAnimationWidget

PDFPageInfo = namedtuple('PDFPageInfo', ['pdf_path', 'page_num'])

class ThumbnailWorkerSignals(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
    finished = pyqtSignal(object, object, object)  # (pdf_path, page_num, image)

class ThumbnailWorker(QRunnable):
    def __init__(self, pdf_path, page_num, thumb_w, thumb_h, callback, signals):
        super().__init__()
        self.pdf_path = pdf_path
        self.page_num = page_num
        self.thumb_w = thumb_w
        self.thumb_h = thumb_h
        self.signals = signals
        self.signals.finished.connect(callback)

    def run(self):
        try:
            import fitz
            from PyQt6.QtGui import QImage
            doc = fitz.open(self.pdf_path)
            page = doc.load_page(self.page_num)
            pix = page.get_pixmap(matrix=fitz.Matrix(0.7, 0.7))
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
            doc.close()
            self.signals.finished.emit(self.pdf_path, self.page_num, img)
        except Exception as e:
            print(f"{self.pdf_path} ページ{self.page_num+1} サムネイル生成失敗: {e}")
            self.signals.finished.emit(self.pdf_path, self.page_num, None)

# --- ここから非同期PDFリスト読み込み用Worker ---
class PDFListLoadWorkerSignals(QObject):
    finished = pyqtSignal(list)  # [(pdf_path, page_num)]

class PDFListLoadWorker(QRunnable):
    def __init__(self, pdf_dir, pdf_files):
        super().__init__()
        self.pdf_dir = pdf_dir
        self.pdf_files = pdf_files
        self.signals = PDFListLoadWorkerSignals()

    def run(self):
        result = []
        for pdf_file in self.pdf_files:
            pdf_path = (
                pdf_file
                if os.path.isabs(pdf_file)
                else os.path.join(self.pdf_dir, pdf_file)
            )
            try:
                import fitz
                doc = fitz.open(pdf_path)
                for i in range(len(doc)):
                    result.append((pdf_path, i))
                doc.close()
            except Exception as e:
                print(f"{pdf_file} 読み込み失敗: {e}")
        self.signals.finished.emit(result)

    # --- 従来の一括ロードも保持 ---
    def load_all_pages(self):
        self.clear()
        self.page_items = []
        if not self.pdf_files and self.pdf_dir:
            self.pdf_files = [f for f in os.listdir(self.pdf_dir) if f.lower().endswith('.pdf')]
        for pdf_file in self.pdf_files:
            pdf_path = (
                pdf_file
                if os.path.isabs(pdf_file)
                else os.path.join(self.pdf_dir, pdf_file)
            )
            try:
                import fitz
                doc = fitz.open(pdf_path)
                for i in range(len(doc)):
                    info = PDFPageInfo(pdf_path=pdf_path, page_num=i)
                    item = QListWidgetItem()
                    item.setData(Qt.ItemDataRole.UserRole, info)
                    item.setSizeHint(QSize(self.thumb_w + 180, self.thumb_h + 16))
                    pixmap = self.get_thumbnail(pdf_path, i, self.on_thumbnail_ready)
                    widget = QWidget()
                    hbox = QHBoxLayout(widget)
                    label = QLabel()
                    if pixmap:
                        label.setPixmap(pixmap)
                    label.setFixedSize(self.thumb_w, self.thumb_h)
                    hbox.addWidget(label)
                    text = QLabel(f"{os.path.basename(pdf_path)}\nページ{i+1}")
                    hbox.addWidget(text)
                    btn_up = QPushButton('↑')
                    btn_up.setFixedWidth(28)
                    btn_up.clicked.connect(lambda _, it=item: self.move_item(it, -1))
                    hbox.addWidget(btn_up)
                    btn_down = QPushButton('↓')
                    btn_down.setFixedWidth(28)
                    btn_down.clicked.connect(lambda _, it=item: self.move_item(it, 1))
                    hbox.addWidget(btn_down)
                    hbox.addStretch(1)
                    widget.setLayout(hbox)
                    self.addItem(item)
                    self.setItemWidget(item, widget)
                    self.page_items.append((info, item))
                doc.close()
            except Exception as e:
                print(f"{pdf_file} 読み込み失敗: {e}")

class PDFThumbnailListViewer(QListWidget):
    pdf_list_loaded = pyqtSignal(list)  # [(pdf_path, page_num)]

    def __init__(self, pdf_dir=None):
        super().__init__()
        self.pdf_dir = pdf_dir
        self.pdf_files = []
        self.thumb_w = 180
        self.thumb_h = 240
        self.thumbnail_cache = {}  # (pdf_path, page_num) -> QPixmap
        self.thread_pool = QThreadPool()
        try:
            max_workers = max(1, os.cpu_count() // 2)
            self.thread_pool.setMaxThreadCount(max_workers)
        except Exception:
            self.thread_pool.setMaxThreadCount(2)
        self.setViewMode(QListWidget.ViewMode.ListMode)
        self.setIconSize(QSize(self.thumb_w, self.thumb_h))
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.setSpacing(8)
        self.setMovement(QListWidget.Movement.Static)
        self.setFlow(QListWidget.Flow.TopToBottom)
        self.setWrapping(False)
        self.itemDoubleClicked.connect(self.on_item_doubleclicked)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.pdf_list_loaded.connect(self._on_pdf_list_loaded)
        self._workers = []  # ThumbnailWorkerの参照保持用
        self._signals = []  # signalsの参照保持用
        self._pdf_page_iter = None  # incremental loading iterator
        self._thumbnail_requested = set()  # avoid duplicate loads
        self._initial_load_rows = 0
        # ローディングアニメーションウィジェット
        self.loading_widget = LoadingAnimationWidget("サムネイルを読み込み中...", parent=self)
        self.loading_widget.setFixedSize(200, 120)
        self.loading_widget.hide()
        # trigger lazy thumbnail loading on scroll
        self.verticalScrollBar().valueChanged.connect(self._load_visible_thumbnails)

    def get_thumbnail(self, pdf_path, page_num, callback=None):
        key = (pdf_path, page_num)
        if key in self.thumbnail_cache:
            return self.thumbnail_cache[key]
        if callback:
            signals = ThumbnailWorkerSignals(self)
            worker = ThumbnailWorker(pdf_path, page_num, self.thumb_w, self.thumb_h, callback, signals)
            self._workers.append(worker)
            self._signals.append(signals)
            def on_finished(*args, **kwargs):
                if worker in self._workers:
                    self._workers.remove(worker)
                if signals in self._signals:
                    self._signals.remove(signals)
                callback(*args, **kwargs)
            try:
                signals.finished.disconnect(callback)
            except Exception:
                pass
            signals.finished.connect(on_finished)
            self.thread_pool.start(worker)
            return None
        try:
            import fitz
            from PyQt6.QtGui import QImage, QPixmap
            doc = fitz.open(pdf_path)
            page = doc.load_page(page_num)
            pix = page.get_pixmap(matrix=fitz.Matrix(0.7, 0.7))
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(img).scaled(self.thumb_w, self.thumb_h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.thumbnail_cache[key] = pixmap
            doc.close()
            return pixmap
        except Exception as e:
            print(f"{pdf_path} ページ{page_num+1} サムネイル生成失敗: {e}")
            return None

    def on_thumbnail_ready(self, pdf_path, page_num, image):
        key = (pdf_path, page_num)
        self._thumbnail_requested.discard(key)
        if image is not None:
            from PyQt6.QtGui import QPixmap
            pixmap = QPixmap.fromImage(image).scaled(
                self.thumb_w,
                self.thumb_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.thumbnail_cache[key] = pixmap
            for (info, item) in self.page_items:
                if info.pdf_path == pdf_path and info.page_num == page_num:
                    widget = self.itemWidget(item)
                    if widget:
                        label = widget.findChild(QLabel)
                        if label:
                            label.setPixmap(pixmap)
                    break

    def show_loading(self, message=None):
        if message:
            self.loading_widget.set_message(message)
        self.loading_widget.move(
            (self.width() - self.loading_widget.width()) // 2,
            (self.height() - self.loading_widget.height()) // 2
        )
        self.loading_widget.show()
        self.loading_widget.start()
        self.setDisabled(True)

    def hide_loading(self):
        self.loading_widget.hide()
        self.loading_widget.stop()
        self.setDisabled(False)

    def load_all_pages_async(self):
        self.show_loading("サムネイルを読み込み中...")
        self.clear()
        self.page_items = []
        if not self.pdf_files and self.pdf_dir:
            self.pdf_files = [f for f in os.listdir(self.pdf_dir) if f.lower().endswith('.pdf')]
        worker = PDFListLoadWorker(self.pdf_dir, self.pdf_files)
        worker.signals.finished.connect(self.pdf_list_loaded.emit)
        self.thread_pool.start(worker)

    def _on_pdf_list_loaded(self, pdf_page_list):
        self.clear()
        self.page_items = []
        self._pdf_page_iter = iter(pdf_page_list)
        self._initial_load_rows = self._visible_row_threshold()
        self._process_page_batch()

    def _visible_row_threshold(self) -> int:
        row_h = self.thumb_h + 16 + self.spacing()
        if row_h <= 0:
            return 0
        rows = max(1, self.viewport().height() // row_h)
        return rows * 2

    def _process_page_batch(self, batch_size: int = 10):
        """Process a small batch of pages to keep UI responsive."""
        if self._pdf_page_iter is None:
            return
        for _ in range(batch_size):
            try:
                pdf_path, page_num = next(self._pdf_page_iter)
            except StopIteration:
                self._pdf_page_iter = None
                self.hide_loading()
                return
            info = PDFPageInfo(pdf_path=pdf_path, page_num=page_num)
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, info)
            item.setSizeHint(QSize(self.thumb_w + 180, self.thumb_h + 16))
            row_index = self.count()
            if row_index < getattr(self, "_initial_load_rows", 0):
                key = (pdf_path, page_num)
                self._thumbnail_requested.add(key)
                pixmap = self.get_thumbnail(pdf_path, page_num, self.on_thumbnail_ready)
            else:
                pixmap = None
            widget = QWidget()
            hbox = QHBoxLayout(widget)
            label = QLabel()
            if pixmap:
                label.setPixmap(pixmap)
            label.setFixedSize(self.thumb_w, self.thumb_h)
            hbox.addWidget(label)
            text = QLabel(f"{os.path.basename(pdf_path)}\nページ{page_num+1}")
            hbox.addWidget(text)
            btn_up = QPushButton('↑')
            btn_up.setFixedWidth(28)
            btn_up.clicked.connect(lambda _, it=item: self.move_item(it, -1))
            hbox.addWidget(btn_up)
            btn_down = QPushButton('↓')
            btn_down.setFixedWidth(28)
            btn_down.clicked.connect(lambda _, it=item: self.move_item(it, 1))
            hbox.addWidget(btn_down)
            hbox.addStretch(1)
            widget.setLayout(hbox)
            self.addItem(item)
            self.setItemWidget(item, widget)
            self.page_items.append((info, item))
        QApplication.processEvents()
        self._load_visible_thumbnails()
        QTimer.singleShot(0, self._process_page_batch)

    def _load_visible_thumbnails(self):
        """Load thumbnails for items that are currently visible."""
        if not self.page_items:
            return
        vh = self.viewport().height()
        row_h = self.thumb_h + 16 + self.spacing()
        rows = max(1, vh // row_h)
        top_index = self.indexAt(QPoint(0, 0)).row()
        if top_index == -1:
            top_index = 0
        bottom_index = self.indexAt(QPoint(0, vh - 1)).row()
        if bottom_index == -1:
            bottom_index = self.count() - 1
        start = max(0, top_index - rows)
        end = min(self.count() - 1, bottom_index + rows)
        for row in range(start, end + 1):
            info, item = self.page_items[row]
            key = (info.pdf_path, info.page_num)
            if key in self.thumbnail_cache or key in self._thumbnail_requested:
                continue
            self._thumbnail_requested.add(key)
            self.get_thumbnail(info.pdf_path, info.page_num, self.on_thumbnail_ready)

    def on_item_doubleclicked(self, item):
        """
        ダブルクリック時の動作: 選択したPDFページをプレビュー表示
        """
        info = item.data(Qt.ItemDataRole.UserRole)
        if info is None:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(
            f"プレビュー: {os.path.basename(info.pdf_path)} ページ{info.page_num+1}"
        )
        vbox = QVBoxLayout(dlg)
        scroll = QScrollArea(dlg)
        preview = PDFPreviewWidget(scroll)
        preview.set_pdf(info.pdf_path)
        scroll.setWidget(preview)
        scroll.setWidgetResizable(True)
        vbox.addWidget(scroll)
        dlg.setLayout(vbox)
        dlg.resize(800, 1000)
        dlg.exec()

    def save_state(self, path=None):
        """
        現在のページ順序・選択状態をJSONで保存
        """
        import json
        from PyQt6.QtWidgets import QFileDialog
        if path is None:
            path, _ = QFileDialog.getSaveFileName(self, "状態保存ファイル", "", "JSON Files (*.json)")
            if not path:
                return
        state = {
            "pages": [
                {"pdf_path": info.pdf_path, "page_num": info.page_num}
                for info, _ in getattr(self, "page_items", [])
            ],
            "selected": [i for i, (_, item) in enumerate(getattr(self, "page_items", [])) if item.isSelected()]
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def load_state(self, path=None):
        """
        保存されたページ順序・選択状態を復元
        """
        import json
        from PyQt6.QtWidgets import QFileDialog
        if path is None:
            path, _ = QFileDialog.getOpenFileName(self, "状態ファイルを選択", "", "JSON Files (*.json)")
            if not path:
                return
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)
        self.clear()
        self.page_items = []
        for page in state.get("pages", []):
            info = PDFPageInfo(pdf_path=page["pdf_path"], page_num=page["page_num"])
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, info)
            item.setSizeHint(QSize(self.thumb_w + 180, self.thumb_h + 16))
            widget = QWidget()
            hbox = QHBoxLayout(widget)
            label = QLabel()
            label.setFixedSize(self.thumb_w, self.thumb_h)
            hbox.addWidget(label)
            text = QLabel(f"{os.path.basename(info.pdf_path)}\nページ{info.page_num+1}")
            hbox.addWidget(text)
            btn_up = QPushButton('↑')
            btn_up.setFixedWidth(28)
            btn_up.clicked.connect(lambda _, it=item: self.move_item(it, -1))
            hbox.addWidget(btn_up)
            btn_down = QPushButton('↓')
            btn_down.setFixedWidth(28)
            btn_down.clicked.connect(lambda _, it=item: self.move_item(it, 1))
            hbox.addWidget(btn_down)
            hbox.addStretch(1)
            widget.setLayout(hbox)
            self.addItem(item)
            self.setItemWidget(item, widget)
            self.page_items.append((info, item))
        # 選択状態復元
        for i in state.get("selected", []):
            if 0 <= i < len(self.page_items):
                self.page_items[i][1].setSelected(True)

    def move_item(self, item, direction):
        """
        指定したitemをdirection（-1:上, 1:下）に移動する
        """
        row = self.row(item)
        new_row = row + direction
        if 0 <= new_row < self.count():
            self.takeItem(row)
            self.insertItem(new_row, item)
            self.setCurrentRow(new_row)
            # page_itemsの順序も同期
            info_item = self.page_items.pop(row)
            self.page_items.insert(new_row, info_item)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.count() == 0:
            from PyQt6.QtGui import QPainter, QFont, QColor
            painter = QPainter(self.viewport())
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            font = QFont()
            font.setPointSize(14)
            painter.setFont(font)
            painter.setPen(QColor(128, 128, 128))
            msg = "ファイルメニューからフォルダまたはPDFファイルを選択して下さい"
            rect = self.viewport().rect()
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, msg)
            painter.end()

