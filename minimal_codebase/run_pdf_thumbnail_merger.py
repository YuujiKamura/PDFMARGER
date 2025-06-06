import sys
import os
print('start script')
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
print('sys.path appended')
from PyQt6.QtWidgets import QApplication
print('PyQt6 imported')
from 収集車両PDF集約.pdf_thumbnail_merger import PDFThumbnailMerger
print('PDFThumbnailMerger imported')

if __name__ == "__main__":
    print('main block start')
    app = QApplication(sys.argv)
    print('QApplication created')
    win = PDFThumbnailMerger()
    print('PDFThumbnailMerger instance created')
    win.show()
    print('win.show() called')
    sys.exit(app.exec()) 