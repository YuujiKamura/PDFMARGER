from pathlib import Path
import os
import sys
from typing import Optional

class PathManager:
    """
    プロジェクト内のパスを一元管理するユーティリティクラス。
    どこからimportしても正しい絶対パス/相対パス変換ができる。
    """
    @staticmethod
    def project_root():
        # このファイルの2階層上をプロジェクトルートとする
        return Path(__file__).resolve().parent.parent

    @staticmethod
    def data_dir():
        return PathManager.project_root() / "data"

    @staticmethod
    def credentials_dir():
        return PathManager.project_root() / "credentials"

    @staticmethod
    def abs_path(path):
        """相対パスまたは絶対パスを絶対パスに変換"""
        p = Path(path)
        if p.is_absolute():
            return p
        return (PathManager.project_root() / p).resolve()

    @staticmethod
    def rel_path(path):
        """絶対パスをプロジェクトルートからの相対パスに変換"""
        p = Path(path).resolve()
        try:
            return p.relative_to(PathManager.project_root())
        except ValueError:
            return p  # 変換できない場合は絶対パスのまま返す

    @staticmethod
    def documentai_config_path():
        """DocumentAI用のデフォルト設定ファイルの絶対パスを返す"""
        return PathManager.data_dir() / "documentai_config.json"

    @staticmethod
    def load_documentai_config():
        """DocumentAI用のデフォルト設定（dict）を返す。ファイルがなければ空dict"""
        import json
        config_path = PathManager.documentai_config_path()
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                return json.load(f)
        return {}

def get_appdata_dir() -> str:
    """
    アプリ固有の作業ファイル・設定ファイルを保存するディレクトリの絶対パスを返す。
    OSごとに適切な場所（Windows: %APPDATA%、Mac: ~/Library/Application Support、Linux: ~/.config など）
    """
    appname = "pdf_thumbnail_merger"
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.path.expanduser("~/.config")
    path = os.path.join(base, appname)
    os.makedirs(path, exist_ok=True)
    return path

def get_appdata_path(filename: str) -> str:
    """
    アプリ固有ディレクトリ配下のファイル絶対パスを返す
    """
    return os.path.join(get_appdata_dir(), filename)
