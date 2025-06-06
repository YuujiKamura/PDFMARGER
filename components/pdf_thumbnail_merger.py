import sys
import os
from PyQt6.QtWidgets import (
    QMainWindow, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QMessageBox,
    QApplication, QWidget
)
from components.pdf_menu_bar import PDFMenuBar
from components.pdf_thumbnail_list_viewer import PDFThumbnailListViewer
from components.last_dir_manager import load_last_dir, save_last_dir
from components.pdf_save_utils import save_pdf_pages
from components.path_manager import get_appdata_path


class PDFThumbnailMerger(QMainWindow):
    def __init__(self, pdf_dir=None):
        super().__init__()
        if pdf_dir is None:
            pdf_dir = load_last_dir()
        self.pdf_dir = pdf_dir
        self.viewer = PDFThumbnailListViewer(pdf_dir)
        # 状態ファイルがあれば復元、なければ全ページ読込
        state_path = get_appdata_path("last_pdf_edit_state.json")
        try:
            if os.path.exists(state_path):
                self.viewer.load_state(state_path)
            else:
                self.viewer.load_all_pages_async()
        except Exception as e:
            print(f"状態ファイル読込失敗: {e}")
            self.viewer.load_all_pages_async()
        self.setWindowTitle("PDFページサムネイル選択・結合ツール")
        self.resize(1200, 800)
        # メインウィジェットとレイアウト
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        vlayout = QVBoxLayout(central_widget)
        # メニューバー追加
        self.menu_bar = PDFMenuBar(self)
        self.menu_bar.filesOpened.connect(self.on_files_opened)
        self.menu_bar.folderOpened.connect(self.on_folder_opened)
        self.menu_bar.filesAdded.connect(self.on_files_added)
        self.menu_bar.folderAdded.connect(self.on_folder_added)
        self.menu_bar.mergeSelectedPDFs.connect(self.merge_selected_pages)
        self.setMenuBar(self.menu_bar)
        # --- 作業状態保存メニューのみ追加 ---
        self.menu_bar.addAction("作業状態を保存", self.save_edit_state)
        self.menu_bar.addAction("作業状態をクリアして保存", self.clear_and_save_edit_state)
        # サムネイルグリッドビューア追加
        vlayout.addWidget(self.viewer)
        # 操作ボタン
        btn_layout = QHBoxLayout()
        self.btn_merge = QPushButton("選択ページでPDF結合")
        self.btn_merge.clicked.connect(self.merge_selected_pages)
        btn_layout.addWidget(self.btn_merge)
        self.btn_merge_all = QPushButton("表示PDFを結合")
        self.btn_merge_all.clicked.connect(self.merge_all_pages)
        btn_layout.addWidget(self.btn_merge_all)
        vlayout.addLayout(btn_layout)

    def on_files_opened(self, files):
        state_path = get_appdata_path("last_pdf_edit_state.json")
        try:
            self.viewer.pdf_files = [os.path.abspath(f) for f in files]
            self.viewer.pdf_dir = (
                os.path.dirname(self.viewer.pdf_files[0])
                if self.viewer.pdf_files else None
            )
            if self.viewer.pdf_dir:
                save_last_dir(self.viewer.pdf_dir)
            self.viewer.load_all_pages_async()
        except Exception as e:
            print(f"状態ファイル読込失敗: {e}")
            print(f"PDFファイル読込失敗: {e}")
            self.viewer.load_all_pages_async()

    def on_folder_opened(self, folder):
        state_path = get_appdata_path("last_pdf_edit_state.json")
        try:
            self.viewer.pdf_dir = folder
            self.viewer.pdf_files = [
                f
                for f in os.listdir(folder)
                if f.lower().endswith(".pdf")
            ]
            if folder:
                save_last_dir(folder)
            self.viewer.load_all_pages_async()
        except Exception as e:
            print(f"状態ファイル読込失敗: {e}")
            print(f"フォルダ読込失敗: {e}")
            self.viewer.load_all_pages_async()

    def on_files_added(self, files):
        state_path = get_appdata_path("last_pdf_edit_state.json")
        try:
            self.viewer.pdf_files.extend([os.path.abspath(f) for f in files])
            if files:
                save_last_dir(os.path.dirname(files[0]))
            self.viewer.load_all_pages_async()
        except Exception as e:
            print(f"状態ファイル読込失敗: {e}")
            print(f"PDFファイル追加失敗: {e}")
            self.viewer.load_all_pages_async()

    def on_folder_added(self, folder):
        state_path = get_appdata_path("last_pdf_edit_state.json")
        try:
            new_files = [
                os.path.join(folder, f)
                for f in os.listdir(folder)
                if f.lower().endswith(".pdf")
            ]
            self.viewer.pdf_files.extend(new_files)
            if folder:
                save_last_dir(folder)
            self.viewer.load_all_pages_async()
        except Exception as e:
            print(f"状態ファイル読込失敗: {e}")
            print(f"フォルダ追加失敗: {e}")
            self.viewer.load_all_pages_async()

    def merge_selected_pages(self):
        selected = self.viewer.get_selected_pages()
        if not selected:
            QMessageBox.warning(self, "警告", "ページが選択されていません")
            return
        save_path, _ = QFileDialog.getSaveFileName(
            self, "保存先PDF", self.viewer.pdf_dir, "PDF Files (*.pdf)"
        )
        if not save_path:
            return
        save_pdf_pages(selected, save_path)
        QMessageBox.information(self, "完了", f"{save_path} に保存しました")

    def merge_all_pages(self):
        # 現在リストに表示されている全ページを結合
        all_infos = [info for (info, item) in self.viewer.page_items]
        if not all_infos:
            QMessageBox.warning(self, "警告", "結合するページがありません")
            return
        save_path, _ = QFileDialog.getSaveFileName(
            self, "保存先PDF", self.viewer.pdf_dir, "PDF Files (*.pdf)"
        )
        if not save_path:
            return
        save_pdf_pages(all_infos, save_path)
        QMessageBox.information(self, "完了", f"{save_path} に保存しました")

    def save_edit_state(self):
        try:
            self.viewer.save_state()
            QMessageBox.information(self, "保存", "作業状態を保存しました")
        except Exception as e:
            print(f"状態保存失敗: {e}")
            QMessageBox.warning(self, "エラー", "作業状態の保存に失敗しました")

    def clear_and_save_edit_state(self):
        """
        表示・キャッシュをクリアし、空の状態をデフォルトキャッシュ（last_pdf_edit_state.json）に保存
        """
        try:
            self.viewer.page_items = []
            self.viewer.pdf_files = []
            self.viewer.clear()
            self.viewer.thumbnail_cache.clear()
            # 空状態をデフォルトキャッシュに保存
            state_path = get_appdata_path("last_pdf_edit_state.json")
            self.viewer.save_state(state_path)
            QMessageBox.information(self, "保存", "作業状態をクリアしてデフォルトキャッシュに保存しました")
        except Exception as e:
            print(f"状態クリア保存失敗: {e}")
            QMessageBox.warning(self, "エラー", "作業状態のクリア保存に失敗しました")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = PDFThumbnailMerger()
    win.show()
    sys.exit(app.exec()) 