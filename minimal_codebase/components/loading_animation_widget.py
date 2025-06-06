from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QMovie
import os

class LoadingAnimationWidget(QWidget):
    """
    アニメーション付きローディングウィジェット（Cursor風）
    - GIFアニメやSVGアニメをQLabel+QMovieで表示
    - テキストも表示可能
    - set_messageでメッセージ変更
    """
    def __init__(self, message="読み込み中...", parent=None, gif_path=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setLayout(layout)
        self.label_anim = QLabel(self)
        self.label_anim.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_text = QLabel(message, self)
        self.label_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label_anim)
        layout.addWidget(self.label_text)
        # デフォルトのアニメーションGIF
        if gif_path is None:
            gif_path = os.path.join(os.path.dirname(__file__), "loading_spinner.gif")
        if os.path.exists(gif_path):
            self.movie = QMovie(gif_path)
            self.label_anim.setMovie(self.movie)
            self.movie.start()
        else:
            self.label_anim.setText("●●●")  # Fallback: simple dots
    def set_message(self, message: str):
        self.label_text.setText(message)
    def start(self):
        if hasattr(self, "movie"):
            self.movie.start()
    def stop(self):
        if hasattr(self, "movie"):
            self.movie.stop()
        self.hide() 