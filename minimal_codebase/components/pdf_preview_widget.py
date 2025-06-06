#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
PDFプレビュー用のウィジェット
"""

from PyQt6.QtWidgets import (
    QWidget,
    QMessageBox,
    QMenu,
    QInputDialog,
    QLineEdit,
    QFontDialog,
    QFileDialog,
    QColorDialog,
)
from PyQt6.QtCore import Qt, QRect, QPoint, QThreadPool, QRunnable, pyqtSignal, QObject
from PyQt6.QtGui import (
    QPixmap,
    QImage,
    QPainter,
    QPen,
    QColor,
    QFont,
    QFontMetrics,
)
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
import fitz
import os
import tempfile
from .selection_box import SelectionBox

class OcrWorkerSignals(QObject):
    finished = pyqtSignal(object, object)  # (pages_dict, error)

class OcrWorker(QRunnable):
    def __init__(self, pdf_path):
        super().__init__()
        self.pdf_path = pdf_path
        self.signals = OcrWorkerSignals()
    def run(self):
        try:
            from ocr_tools.document_ai_ocr import DocumentAIOCR
            ocr = DocumentAIOCR()
            pages_dict, err = ocr.extract_ocr_from_pdf(self.pdf_path)
            self.signals.finished.emit(pages_dict, err)
        except Exception as e:
            self.signals.finished.emit(None, str(e))

class PDFPreviewWidget(QWidget):
    """PDFをプレビュー表示するウィジェット（QLabel廃止・自前描画）"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(300, 300)
        self.pdf_path = None
        self.doc = None
        self.pixmap = None  # 原寸画像
        # overlay_textsは原寸(100%)座標で保持する
        # 各要素は (QRect, str, QFont, Qt.AlignmentFlag, QColor)
        self.overlay_texts = []
        self.scale_factor = 1.0
        # --- 矩形選択用 ---
        self.selection = SelectionBox()
        self.setMouseTracking(True)
        self._edit_box = None
        self._selected_overlay = None  # 選択中のテキストボックスindex
        self._drag_offset = QPoint()
        self.thread_pool = QThreadPool()

    def set_scale(self, scale: float):
        """表示倍率を設定 (1.0 = 100%)"""
        if not self.pixmap:
            self.scale_factor = scale
            return
        old_scale = self.scale_factor
        if abs(scale - old_scale) < 0.001:
            return
        ratio = scale / old_scale
        # 選択範囲も倍率に合わせて変換
        def _scale_rect(rect: QRect) -> QRect:
            return QRect(
                int(rect.x() * ratio),
                int(rect.y() * ratio),
                int(rect.width() * ratio),
                int(rect.height() * ratio),
            )

        self.selection.scale(ratio)
        if self._edit_box:
            box_rect = _scale_rect(self._edit_box.geometry())
            self._edit_box.setGeometry(box_rect)
        self.scale_factor = scale
        self.resize(
            int(self.pixmap.width() * scale),
            int(self.pixmap.height() * scale),
        )
        self.update()
    
    def set_pdf(self, pdf_path):
        """PDFをセットして表示
        
        Args:
            pdf_path: PDFファイルのパス
            
        Returns:
            bool: PDFの読み込みに成功したかどうか
        """
        if not pdf_path or not os.path.exists(pdf_path):
            self.pixmap = None
            self.update()
            return False
        
        try:
            # PyMuPDFでPDFを開く
            self.doc = fitz.open(pdf_path)
            self.pdf_path = pdf_path
            
            if len(self.doc) > 0:
                # 最初のページを表示
                page = self.doc.load_page(0)
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
                self.pixmap = QPixmap.fromImage(img)
                self.setFixedSize(
                    int(self.pixmap.width() * self.scale_factor),
                    int(self.pixmap.height() * self.scale_factor),
                )
                self.resize(
                    int(self.pixmap.width() * self.scale_factor),
                    int(self.pixmap.height() * self.scale_factor),
                )
                self.overlay_texts = []
                self.selection = SelectionBox()
                self.update()
                
                return True
            else:
                self.pixmap = None
                self.update()
                return False
                
        except Exception:
            self.pixmap = None
            self.update()
            return False
    
    def print_preview(self):
        """現在表示中のPDFを印刷
        
        Returns:
            bool: 印刷に成功したかどうか
        """
        if not self.pdf_path or not os.path.exists(self.pdf_path):
            QMessageBox.warning(self, "印刷エラー", "印刷するPDFがありません")
            return False
        
        try:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            dialog = QPrintDialog(printer, self)
            
            if dialog.exec() == QPrintDialog.DialogCode.Accepted:
                # PyMuPDFを使用してPDFを直接印刷
                from PyQt6.QtCore import QUrl
                from PyQt6.QtGui import QDesktopServices
                
                # デスクトップサービスでPDFを開いて印刷ダイアログを表示
                QDesktopServices.openUrl(QUrl.fromLocalFile(self.pdf_path))
                return True
                
            return False
            
        except Exception as e:
            QMessageBox.critical(self, "印刷エラー", f"印刷中にエラーが発生しました: {str(e)}")
            return False

    def paintEvent(self, event):
        painter = QPainter(self)
        if self.pixmap:
            scaled = self.pixmap.scaled(
                int(self.pixmap.width() * self.scale_factor),
                int(self.pixmap.height() * self.scale_factor),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            painter.drawPixmap(0, 0, scaled)
        # 上書きテキスト描画
        for i, item in enumerate(self.overlay_texts):
            if len(item) >= 5:
                rect_orig, text, font, align, color = item
            elif len(item) == 4:
                rect_orig, text, font, align = item
                color = QColor(255, 255, 255)
            elif len(item) == 3:
                rect_orig, text, font = item
                align = Qt.AlignmentFlag.AlignCenter
                color = QColor(255, 255, 255)
            else:
                rect_orig, text = item
                font = painter.font()
                font.setPointSize(16)
                align = Qt.AlignmentFlag.AlignCenter
                color = QColor(255, 255, 255)
            rect = QRect(
                int(rect_orig.x() * self.scale_factor),
                int(rect_orig.y() * self.scale_factor),
                int(rect_orig.width() * self.scale_factor),
                int(rect_orig.height() * self.scale_factor),
            )
            painter.setPen(Qt.PenStyle.NoPen)  # 枠線なし
            painter.setBrush(color)
            painter.drawRect(rect)
            painter.setPen(QPen(QColor(0, 0, 0)))
            painter.setFont(font)
            painter.drawText(rect, align, text)
            # 選択中のみ薄い枠線を表示
            if i == self._selected_overlay:
                painter.setPen(QPen(QColor(0, 120, 255, 180), 2, Qt.PenStyle.DashLine))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(rect)
        # 選択範囲描画
        if self.selection.is_active():
            pen = QPen(QColor(0, 120, 255, 180), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.selection.rect)
            for rc in self.selection._handle_rects().values():
                painter.setBrush(QColor(0, 120, 255))
                painter.drawRect(rc)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # テキストボックス選択・移動
            for i, item in enumerate(self.overlay_texts):
                rect_orig = item[0]
                rect = QRect(
                    int(rect_orig.x() * self.scale_factor),
                    int(rect_orig.y() * self.scale_factor),
                    int(rect_orig.width() * self.scale_factor),
                    int(rect_orig.height() * self.scale_factor),
                )
                if rect.contains(event.pos()):
                    self._selected_overlay = i
                    self._drag_offset = event.pos() - rect.topLeft()
                    self.update()
                    return
            self._selected_overlay = None
            self.selection.begin_action(event.pos())
            self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            # テキストボックス選択中なら書体変更・削除メニュー
            if self._selected_overlay is not None:
                menu = QMenu(self)
                font_action = menu.addAction("書体変更")
                align_menu = menu.addMenu("揃え変更")
                left_act = align_menu.addAction("左揃え")
                center_act = align_menu.addAction("中揃え")
                right_act = align_menu.addAction("右揃え")
                delete_action = menu.addAction("削除")
                action = menu.exec(self.mapToGlobal(event.pos()))
                if action == font_action:
                    self.change_overlay_font(self._selected_overlay)
                elif action == left_act:
                    self.change_overlay_alignment(self._selected_overlay, Qt.AlignmentFlag.AlignLeft)
                elif action == center_act:
                    self.change_overlay_alignment(self._selected_overlay, Qt.AlignmentFlag.AlignCenter)
                elif action == right_act:
                    self.change_overlay_alignment(self._selected_overlay, Qt.AlignmentFlag.AlignRight)
                elif action == delete_action:
                    self.overlay_texts.pop(self._selected_overlay)
                    self._selected_overlay = None
                    self.update()
                return
            # 通常の右クリックメニュー
            menu = QMenu(self)
            if self.selection.is_active():
                add_text_action = menu.addAction("テキスト追加（サイズ・書体指定）")
                ocr_action = menu.addAction("選択範囲をOCRして上書き")
                ocr_action.setEnabled(False)
            zoom_menu = menu.addMenu("表示倍率")
            zoom_actions = {}
            for p in [100, 90, 80, 70, 60, 50]:
                act = zoom_menu.addAction(f"{p}%")
                zoom_actions[act] = p
            save_action = menu.addAction("PDFを上書き保存")
            saveas_action = menu.addAction("名前をつけて保存")
            action = menu.exec(self.mapToGlobal(event.pos()))
            if self.selection.is_active():
                if action == add_text_action:
                    self.add_text_box_to_selection()
                elif action == ocr_action:
                    self.ocr_selected_region()
            if action in zoom_actions:
                self.set_scale(zoom_actions[action] / 100.0)
            if action == save_action:
                self.save_pdf(overwrite=True)
            elif action == saveas_action:
                self.save_pdf(overwrite=False)

    def mouseMoveEvent(self, event):
        if self._selected_overlay is not None and event.buttons() & Qt.MouseButton.LeftButton:
            # テキストボックス移動
            item = self.overlay_texts[self._selected_overlay]
            if len(item) >= 5:
                rect_orig, text, font, align, color = item
            elif len(item) == 4:
                rect_orig, text, font, align = item
                color = QColor(255, 255, 255)
            else:
                rect_orig, text, font = item
                align = Qt.AlignmentFlag.AlignCenter
                color = QColor(255, 255, 255)
            new_x = (event.pos().x() - self._drag_offset.x()) / self.scale_factor
            new_y = (event.pos().y() - self._drag_offset.y()) / self.scale_factor
            new_rect = QRect(int(new_x), int(new_y), rect_orig.width(), rect_orig.height())
            self.overlay_texts[self._selected_overlay] = (
                new_rect,
                text,
                font,
                align,
                color,
            )
            self.update()
            return
        if self.selection.update_action(event.pos()):
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.selection.end_action()
            self._drag_offset = QPoint()
            self.update()

    def ocr_selected_region(self):
        # 選択範囲の画像を切り出し
        if not self.doc or not self.selection.is_active():
            QMessageBox.warning(self, "OCR", "有効な範囲が選択されていません")
            return
        # 現在ページの画像を取得
        try:
            page = self.doc.load_page(0)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
            label_geom = self.geometry()
            scale_x = pix.width / self.width()
            scale_y = pix.height / self.height()
            sel = self.selection.rect
            x = int((sel.left() - label_geom.left()) * scale_x)
            y = int((sel.top() - label_geom.top()) * scale_y)
            w = int(sel.width() * scale_x)
            h = int(sel.height() * scale_y)
            cropped = img.copy(x, y, w, h)
            temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
            from PyQt6.QtGui import QPainter
            from PyQt6.QtPrintSupport import QPrinter
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(temp_pdf.name)
            painter = QPainter(printer)
            painter.drawImage(0, 0, cropped)
            painter.end()
            temp_pdf.close()
        except Exception as e:
            QMessageBox.warning(self, "OCR", f"画像切り出し・PDF化失敗: {e}")
            return
        # DocumentAI OCR呼び出しをスレッドで非同期化
        self.setEnabled(False)
        worker = OcrWorker(temp_pdf.name)
        worker.signals.finished.connect(self.on_ocr_finished)
        self.thread_pool.start(worker)

    def on_ocr_finished(self, pages_dict, err):
        self.setEnabled(True)
        if err:
            QMessageBox.warning(self, "OCR", f"OCR失敗: {err}")
            return
        self._last_ocr_result = pages_dict  # OCR結果を保持
        text = ""
        if pages_dict and "0" in pages_dict:
            text = pages_dict["0"].get("text_only", "")
        new_text, ok = QInputDialog.getText(self, "OCR結果編集", "検出文字列を編集:", text=text)
        if ok and new_text:
            self.apply_ocr_text_to_region(new_text)

    def apply_ocr_text_to_region(self, new_text):
        # OCR結果のバウンディングボックスを利用してテキストボックスを重ねる
        # 前回のOCR結果を保持しておく（ocr_selected_regionで取得したpages_dictをself._last_ocr_resultに保存）
        pages_dict = getattr(self, '_last_ocr_result', None)
        if not pages_dict or "0" not in pages_dict:
            QMessageBox.warning(self, "OCR", "OCR結果が見つかりません")
            return
        elements = pages_dict["0"].get("elements", [])
        if not elements:
            QMessageBox.warning(self, "OCR", "OCRボックスが見つかりません")
            return
        # 最初の要素のバウンディングボックスを使う（複数対応は後続）
        vertices = elements[0].get("normalized_vertices", [])
        if len(vertices) != 4:
            QMessageBox.warning(self, "OCR", "バウンディングボックス情報が不正です")
            return
        # 画像サイズ取得
        label_w = self.width()
        label_h = self.height()
        # normalized_verticesをピクセル座標に変換
        xs = [v["x"] for v in vertices]
        ys = [v["y"] for v in vertices]
        min_x = min(xs)
        max_x = max(xs)
        min_y = min(ys)
        max_y = max(ys)
        x = int(min_x * label_w)
        y = int(min_y * label_h)
        w = int((max_x - min_x) * label_w)
        h = int((max_y - min_y) * label_h)
        # 既存の重ねテキストを消す
        self.overlay_texts = []
        # テキストボックスをOCRボックス範囲に合わせて重ねる
        rect_orig = QRect(
            int(x / self.scale_factor),
            int(y / self.scale_factor),
            int(w / self.scale_factor),
            int(h / self.scale_factor),
        )
        self.overlay_texts.append(
            (rect_orig, new_text, QFont(), Qt.AlignmentFlag.AlignCenter, QColor(255, 255, 255))
        )
        self.update()
        # TODO: OCR JSONへの上書き保存処理を後続で実装 

    def mouseDoubleClickEvent(self, event):
        sel = self.selection.rect
        if sel.isNull() or not sel.isValid():
            return
        if self._edit_box:
            self._edit_box.deleteLater()
            self._edit_box = None
        edit = QLineEdit(self)
        edit.setGeometry(sel)
        edit.setStyleSheet("background-color: white; border: 1px solid #888; font-size: 16px;")
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
            (rect_orig, text, edit.font(), edit.alignment(), QColor(255, 255, 255))
        )
        edit.deleteLater()
        self._edit_box = None
        self.update()

    def add_text_box_to_selection(self):
        sel = self.selection.rect
        if sel.isNull() or not sel.isValid():
            return
        # フォント選択ダイアログ
        font, ok = QFontDialog.getFont(QFont("Meiryo", 16), self, "フォントとサイズを選択")
        if not ok:
            return
        # テキスト入力ダイアログ
        text, ok = QInputDialog.getText(self, "テキスト入力", "追加するテキストを入力:")
        if not ok or not text:
            return
        # テキスト幅を計算し、必要なら範囲を広げる
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
            rect.setWidth(text_width + 12)  # 余白
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
            QColor(255, 255, 255), self, "背景色を選択", QColorDialog.ColorDialogOption.ShowAlphaChannel
        )
        if not color.isValid():
            color = QColor(255, 255, 255)
        self.overlay_texts.append((rect, text, font, align, color))
        self.update()

    def change_overlay_font(self, idx):
        item = self.overlay_texts[idx]
        if len(item) >= 5:
            rect, text, font, align, color = item
        elif len(item) == 4:
            rect, text, font, align = item
            color = QColor(255, 255, 255)
        else:
            rect, text, font = item
            align = Qt.AlignmentFlag.AlignCenter
            color = QColor(255, 255, 255)
        new_font, ok = QFontDialog.getFont(font, self, "書体とサイズを変更")
        if not ok:
            return
        # テキスト幅・高さ再計算
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
            color = QColor(255, 255, 255)
        self.overlay_texts[idx] = (new_rect, text, new_font, align, color)
        self.update()

    def change_overlay_alignment(self, idx, align):
        item = self.overlay_texts[idx]
        if len(item) >= 5:
            rect, text, font, _, color = item
        elif len(item) == 4:
            rect, text, font, _ = item
            color = QColor(255, 255, 255)
        elif len(item) == 3:
            rect, text, font = item
            color = QColor(255, 255, 255)
        else:
            rect, text = item
            font = QFont()
            color = QColor(255, 255, 255)
        self.overlay_texts[idx] = (rect, text, font, align, color)
        self.update()

    def save_pdf(self, overwrite=False):
        if not self.pixmap:
            QMessageBox.warning(self, "保存", "画像がありません")
            return
        # 画像＋テキストを合成
        img = self.pixmap.toImage()
        painter = QPainter(img)
        for item in self.overlay_texts:
            if len(item) >= 5:
                rect, text, font, align, color = item
            elif len(item) == 4:
                rect, text, font, align = item
                color = QColor(255, 255, 255)
            elif len(item) == 3:
                rect, text, font = item
                align = Qt.AlignmentFlag.AlignCenter
                color = QColor(255, 255, 255)
            else:
                rect, text = item
                font = painter.font()
                font.setPointSize(16)
                align = Qt.AlignmentFlag.AlignCenter
                color = QColor(255, 255, 255)
            painter.setPen(Qt.PenStyle.NoPen)  # 枠線なし
            painter.setBrush(color)
            painter.drawRect(rect)
            painter.setPen(QPen(QColor(0, 0, 0)))
            painter.setFont(font)
            painter.drawText(rect, align, text)
        painter.end()
        # 一時PNG保存
        import tempfile
        temp_img = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        img.save(temp_img.name)
        temp_img.close()
        # PNG→PDF変換
        from PyQt6.QtPrintSupport import QPrinter
        pdf_path = self.pdf_path if overwrite else None
        if not pdf_path:
            pdf_path, _ = QFileDialog.getSaveFileName(self, "PDFとして保存", "", "PDF Files (*.pdf)")
        if not pdf_path:
            return
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(pdf_path)
        painter = QPainter(printer)
        from PyQt6.QtGui import QImage
        img2 = QImage(temp_img.name)
        rect = painter.viewport()
        size = img2.size()
        size.scale(rect.size(), Qt.AspectRatioMode.KeepAspectRatio)
        painter.setViewport(rect.x(), rect.y(), size.width(), size.height())
        painter.setWindow(img2.rect())
        painter.drawImage(0, 0, img2)
        painter.end()
        QMessageBox.information(self, "保存", f"PDFを保存しました: {pdf_path}") 