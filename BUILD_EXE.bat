@echo off
setlocal
cd /d "%~dp0"
title Build NOVA Fortnite Optimizer

echo ================================================
echo       NOVA - FORTNITE OPTIMIZER BUILDER
echo ================================================
echo.

where py >nul 2>nul
if errorlevel 1 (
  echo Python is not installed or the Python Launcher was not found.
  echo Install Python 3.11 or newer from python.org and enable the PATH option.
  echo Then run this file again.
  pause
  exit /b 1
)

echo [1/3] Installing build dependencies...
py -m pip install --upgrade pip
if errorlevel 1 goto :failed
py -m pip install -r requirements.txt
if errorlevel 1 goto :failed

echo.
echo [2/3] Building the Windows executable...
py -m PyInstaller --noconfirm --clean --onefile --windowed --name NOVA_Fortnite_Optimizer --icon assets\nova.ico --collect-all customtkinter fortnite_optimizer.py
if errorlevel 1 goto :failed

echo.
echo [3/3] Build complete!
echo Your app is here:
echo %CD%\dist\NOVA_Fortnite_Optimizer.exe
echo.
echo You can copy that EXE to your Desktop or another folder.
pause
exit /b 0

:failed
echo.
echo BUILD FAILED. Read the error above, then try again.
pause
exit /b 1
