import sys
import os

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from PyQt6.QtWidgets import QApplication
from 収集車両PDF集約.pdf_thumbnail_merger import PDFThumbnailMerger

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = PDFThumbnailMerger()
    win.show()
    sys.exit(app.exec())
