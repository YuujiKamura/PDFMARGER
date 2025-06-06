from PyQt6.QtWidgets import (
    QLineEdit,
    QFontDialog,
    QInputDialog,
    QColorDialog,
    QMessageBox,
    QFileDialog,
)
from PyQt6.QtGui import (
    QFont,
    QFontMetrics,
    QPainter,
    QPen,
    QColor,
    QImage,
)
from PyQt6.QtCore import QRect, Qt
from PyQt6.QtPrintSupport import QPrinter
import tempfile


class OverlayEditorMixin:
    """Mixin providing text overlay editing features."""

    def mouseDoubleClickEvent(self, event):
        sel = self.selection.rect
        if sel.isNull() or not sel.isValid():
            return
        if self._edit_box:
            self._edit_box.deleteLater()
            self._edit_box = None
        edit = QLineEdit(self)
        edit.setGeometry(sel)
        edit.setStyleSheet(
            "background-color: white; border: 1px solid #888; font-size: 16px;"
        )
        edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        edit.setText("")
        edit.setFocus()
        edit.returnPressed.connect(lambda: self.apply_edit_box_text(edit))
        edit.editingFinished.connect(lambda: self.apply_edit_box_text(edit))
        edit.show()
        self._edit_box = edit
        self.update()

    def apply_edit_box_text(self, edit):
        text = edit.text()
        rect = edit.geometry()
        rect_orig = QRect(
            int(rect.x() / self.scale_factor),
            int(rect.y() / self.scale_factor),
            int(rect.width() / self.scale_factor),
            int(rect.height() / self.scale_factor),
        )
        self.overlay_texts.append(
            (rect_orig, text, edit.font(), edit.alignment(), QColor(0, 0, 0, 0))
        )
        edit.deleteLater()
        self._edit_box = None
        self.update()

    def add_text_box_to_selection(self):
        sel = self.selection.rect
        if sel.isNull() or not sel.isValid():
            return
        font, ok = QFontDialog.getFont(QFont("Meiryo", 16), self, "フォントとサイズを選択")
        if not ok:
            return
        text, ok = QInputDialog.getText(self, "テキスト入力", "追加するテキストを入力:")
        if not ok or not text:
            return
        metrics = QFontMetrics(font)
        text_width = metrics.horizontalAdvance(text)
        text_height = metrics.height()
        rect = QRect(
            int(sel.x() / self.scale_factor),
            int(sel.y() / self.scale_factor),
            int(sel.width() / self.scale_factor),
            int(sel.height() / self.scale_factor),
        )
        if text_width > rect.width():
            rect.setWidth(text_width + 12)
        if text_height > rect.height():
            rect.setHeight(text_height + 8)
        align_items = ["左揃え", "中揃え", "右揃え"]
        align_map = {
            "左揃え": Qt.AlignmentFlag.AlignLeft,
            "中揃え": Qt.AlignmentFlag.AlignCenter,
            "右揃え": Qt.AlignmentFlag.AlignRight,
        }
        align_txt, ok = QInputDialog.getItem(
            self,
            "文字揃え選択",
            "揃えを選択:",
            align_items,
            1,
            False,
        )
        if not ok:
            align = Qt.AlignmentFlag.AlignCenter
        else:
            align = align_map.get(align_txt, Qt.AlignmentFlag.AlignCenter)
        color = QColorDialog.getColor(
            QColor(255, 255, 255, 0),
            self,
            "背景色を選択",
            QColorDialog.ColorDialogOption.ShowAlphaChannel,
        )
        if not color.isValid():
            color = QColor(0, 0, 0, 0)
        self.overlay_texts.append((rect, text, font, align, color))
        self.update()

    def change_overlay_font(self, idx):
        item = self.overlay_texts[idx]
        if len(item) >= 5:
            rect, text, font, align, color = item
        elif len(item) == 4:
            rect, text, font, align = item
            color = QColor(0, 0, 0, 0)
        else:
            rect, text, font = item
            align = Qt.AlignmentFlag.AlignCenter
            color = QColor(0, 0, 0, 0)
        new_font, ok = QFontDialog.getFont(font, self, "書体とサイズを変更")
        if not ok:
            return
        metrics = QFontMetrics(new_font)
        text_width = metrics.horizontalAdvance(text)
        text_height = metrics.height()
        new_rect = QRect(rect)
        if text_width > new_rect.width():
            new_rect.setWidth(text_width + 12)
        if text_height > new_rect.height():
            new_rect.setHeight(text_height + 8)
        align_items = ["左揃え", "中揃え", "右揃え"]
        align_map = {
            "左揃え": Qt.AlignmentFlag.AlignLeft,
            "中揃え": Qt.AlignmentFlag.AlignCenter,
            "右揃え": Qt.AlignmentFlag.AlignRight,
        }
        align_txt, ok = QInputDialog.getItem(
            self,
            "文字揃え選択",
            "揃えを選択:",
            align_items,
            align_items.index("中揃え"),
            False,
        )
        if ok:
            align = align_map.get(align_txt, align)
        color = QColorDialog.getColor(
            color,
            self,
            "背景色を選択",
            QColorDialog.ColorDialogOption.ShowAlphaChannel,
        )
        if not color.isValid():
            color = QColor(0, 0, 0, 0)
        self.overlay_texts[idx] = (new_rect, text, new_font, align, color)
        self.update()

    def change_overlay_alignment(self, idx, align):
        item = self.overlay_texts[idx]
        if len(item) >= 5:
            rect, text, font, _, color = item
        elif len(item) == 4:
            rect, text, font, _ = item
            color = QColor(0, 0, 0, 0)
        elif len(item) == 3:
            rect, text, font = item
            color = QColor(0, 0, 0, 0)
        else:
            rect, text = item
            font = QFont()
            color = QColor(0, 0, 0, 0)
        self.overlay_texts[idx] = (rect, text, font, align, color)
        self.update()

    def save_pdf(self, overwrite=False):
        if not self.pixmap:
            QMessageBox.warning(self, "保存", "画像がありません")
            return
        img = self.pixmap.toImage()
        painter = QPainter(img)
        for item in self.overlay_texts:
            if len(item) >= 5:
                rect, text, font, align, color = item
            elif len(item) == 4:
                rect, text, font, align = item
                color = QColor(0, 0, 0, 0)
            elif len(item) == 3:
                rect, text, font = item
                align = Qt.AlignmentFlag.AlignCenter
                color = QColor(0, 0, 0, 0)
            else:
                rect, text = item
                font = painter.font()
                font.setPointSize(16)
                align = Qt.AlignmentFlag.AlignCenter
                color = QColor(0, 0, 0, 0)
            painter.setPen(Qt.PenStyle.NoPen)
            if color.alpha() > 0:
                painter.setBrush(color)
                painter.drawRect(rect)
            painter.setPen(QPen(QColor(0, 0, 0)))
            painter.setFont(font)
            painter.drawText(rect, align, text)
        painter.end()
        temp_img = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        img.save(temp_img.name)
        temp_img.close()
        pdf_path = self.pdf_path if overwrite else None
        if not pdf_path:
            pdf_path, _ = QFileDialog.getSaveFileName(self, "PDFとして保存", "", "PDF Files (*.pdf)")
        if not pdf_path:
            return
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(pdf_path)
        painter = QPainter(printer)
        img2 = QImage(temp_img.name)
        rect = painter.viewport()
        size = img2.size()
        size.scale(rect.size(), Qt.AspectRatioMode.KeepAspectRatio)
        painter.setViewport(rect.x(), rect.y(), size.width(), size.height())
        painter.setWindow(img2.rect())
        painter.drawImage(0, 0, img2)
        painter.end()
        QMessageBox.information(self, "保存", f"PDFを保存しました: {pdf_path}")
