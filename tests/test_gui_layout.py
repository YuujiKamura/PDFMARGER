import os
import sys
import pytest
from PyQt6.QtWidgets import QApplication

# Add minimal_codebase to sys.path so tests can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "minimal_codebase"))

from 収集車両PDF集約.pdf_thumbnail_merger import PDFThumbnailMerger


def test_main_window_layout():
    app = QApplication.instance() or QApplication([])
    win = PDFThumbnailMerger()
    win.show()

    central_widget = win.centralWidget()
    assert central_widget is not None

    layout = central_widget.layout()
    assert layout.count() == 2

    assert layout.itemAt(0).widget() is win.viewer

    btn_layout_item = layout.itemAt(1)
    btn_layout = btn_layout_item.layout()
    assert btn_layout.count() == 2
    assert btn_layout.itemAt(0).widget() is win.btn_merge
    assert btn_layout.itemAt(1).widget() is win.btn_merge_all
