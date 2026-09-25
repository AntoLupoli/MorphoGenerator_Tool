@echo off
REM ─────────────────────────────────────────────────
REM  MorphoGenerator Tool — Build standalone .exe
REM ─────────────────────────────────────────────────
echo.
echo  Building MorphoGenerator Tool ...
echo.

REM Install dependencies if needed
pip install -r requirements.txt >nul 2>&1

REM Build with PyInstaller
pyinstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name "MorphoGenerator_Tool" ^
    --icon "app.ico" ^
    --add-data "app;app" ^
    --add-data ".prev;.prev" ^
    --add-data ".glb;.glb" ^
    --add-data ".cache;.cache" ^
    --add-data "app_settings.json;." ^
    --add-data "app.ico;." ^
    --hidden-import customtkinter ^
    --hidden-import PIL ^
    --hidden-import PIL.Image ^
    --hidden-import PIL.ImageTk ^
    --hidden-import PIL.ImageDraw ^
    --hidden-import PIL.ImageFont ^
    --hidden-import morpho_visualizer ^
    --hidden-import streamline_extractor ^
    --hidden-import pandas ^
    --hidden-import trimesh ^
    --hidden-import matplotlib ^
    --hidden-import scipy ^
    --collect-all customtkinter ^
    --collect-all tkinterweb ^
    main.py

echo.
echo  Build complete!  Check  dist\MorphoGenerator_Tool.exe
echo.
pause
