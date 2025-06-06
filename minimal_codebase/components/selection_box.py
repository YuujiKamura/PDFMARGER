"""Utility class for selection rectangle with resize handles."""
from PyQt6.QtCore import QRect, QPoint

class SelectionBox:
    def __init__(self, handle_size: int = 8):
        self.rect = QRect()
        self.start_pos = QPoint()
        self.end_pos = QPoint()
        self.handle_size = handle_size
        self.dragging = False
        self.moving = False
        self.resizing = False
        self._resize_handle = None
        self._move_offset = QPoint()

    def is_active(self) -> bool:
        return self.rect.isValid() and not self.rect.isNull()

    def start(self, pos: QPoint):
        self.dragging = True
        self.start_pos = pos
        self.end_pos = pos
        self.rect = QRect(self.start_pos, self.end_pos)

    def _handle_rects(self) -> dict:
        if not self.is_active():
            return {}
        r = self.rect
        s = self.handle_size
        return {
            "tl": QRect(r.left() - s, r.top() - s, s * 2, s * 2),
            "tr": QRect(r.right() - s, r.top() - s, s * 2, s * 2),
            "bl": QRect(r.left() - s, r.bottom() - s, s * 2, s * 2),
            "br": QRect(r.right() - s, r.bottom() - s, s * 2, s * 2),
        }

    def hit_test(self, pos: QPoint) -> str | None:
        for name, rc in self._handle_rects().items():
            if rc.contains(pos):
                return name
        if self.is_active() and self.rect.contains(pos):
            return "move"
        return None

    def begin_action(self, pos: QPoint):
        hit = self.hit_test(pos)
        if hit == "move":
            self.moving = True
            self._move_offset = pos - self.rect.topLeft()
            return
        if hit:
            self.resizing = True
            self._resize_handle = hit
            return
        self.start(pos)

    def update_action(self, pos: QPoint) -> bool:
        if self.dragging:
            self.end_pos = pos
            self.rect = QRect(self.start_pos, self.end_pos).normalized()
            return True
        if self.moving:
            new_top_left = pos - self._move_offset
            self.rect.moveTo(new_top_left)
            return True
        if self.resizing and self._resize_handle:
            r = QRect(self.rect)
            if "l" in self._resize_handle:
                r.setLeft(pos.x())
            if "r" in self._resize_handle:
                r.setRight(pos.x())
            if "t" in self._resize_handle:
                r.setTop(pos.y())
            if "b" in self._resize_handle:
                r.setBottom(pos.y())
            self.rect = r.normalized()
            return True
        return False

    def end_action(self):
        self.dragging = False
        self.moving = False
        self.resizing = False
        self._resize_handle = None

    def scale(self, ratio: float):
        if self.is_active():
            self.rect = QRect(
                int(self.rect.x() * ratio),
                int(self.rect.y() * ratio),
                int(self.rect.width() * ratio),
                int(self.rect.height() * ratio),
            )
            self.start_pos = QPoint(
                int(self.start_pos.x() * ratio),
                int(self.start_pos.y() * ratio),
            )
            self.end_pos = QPoint(
                int(self.end_pos.x() * ratio),
                int(self.end_pos.y() * ratio),
            )

