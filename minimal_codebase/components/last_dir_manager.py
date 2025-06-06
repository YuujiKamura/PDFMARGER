import os
from components.path_manager import get_appdata_path

LAST_DIR_FILE = get_appdata_path('last_pdf_dir.txt')

def load_last_dir():
    try:
        with open(LAST_DIR_FILE, 'r', encoding='utf-8') as f:
            path = f.read().strip()
            if os.path.isdir(path):
                return path
    except Exception:
        pass
    return None

def save_last_dir(path):
    try:
        with open(LAST_DIR_FILE, 'w', encoding='utf-8') as f:
            f.write(path)
    except Exception:
        pass 