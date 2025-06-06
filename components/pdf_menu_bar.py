from PyQt6.QtWidgets import QMenuBar, QMenu, QFileDialog
from PyQt6.QtGui import QAction
from PyQt6.QtCore import pyqtSignal


class PDFMenuBar(QMenuBar):
    filesOpened = pyqtSignal(list)
    folderOpened = pyqtSignal(str)
    filesAdded = pyqtSignal(list)
    folderAdded = pyqtSignal(str)
    mergeSelectedPDFs = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        file_menu = QMenu("ファイル", self)
        self.addMenu(file_menu)

        open_files_action = QAction("ファイルを開く...", self)
        open_files_action.triggered.connect(self.open_files)
        file_menu.addAction(open_files_action)

        open_folder_action = QAction("フォルダを開く...", self)
        open_folder_action.triggered.connect(self.open_folder)
        file_menu.addAction(open_folder_action)

        add_files_action = QAction("ファイルを追加...", self)
        add_files_action.triggered.connect(self.add_files)
        file_menu.addAction(add_files_action)

        add_folder_action = QAction("フォルダを追加...", self)
        add_folder_action.triggered.connect(self.add_folder)
        file_menu.addAction(add_folder_action)

        merge_action = QAction("選択PDFをマージして保存", self)
        merge_action.triggered.connect(self.mergeSelectedPDFs)
        file_menu.addAction(merge_action)

    def open_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "PDFファイルを開く", "", "PDF Files (*.pdf)")
        if files:
            self.filesOpened.emit(files)

    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "フォルダを開く", "")
        if folder:
            self.folderOpened.emit(folder)

    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "PDFファイルを追加", "", "PDF Files (*.pdf)")
        if files:
            self.filesAdded.emit(files)

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "フォルダを追加", "")
        if folder:
            self.folderAdded.emit(folder) 