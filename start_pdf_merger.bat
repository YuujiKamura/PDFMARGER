@echo off
REM PDFサムネイルマージャーを起動するバッチファイル
setlocal

REM スクリプトのディレクトリに移動
cd /d "%~dp0\minimal_codebase"

REM Pythonの存在確認
where python >nul 2>nul
if errorlevel 1 (
    echo Pythonが見つかりません。PATHを確認してください。
    pause
    exit /b 1
)

REM アプリ起動
python run_pdf_thumbnail_merger.py

endlocal 