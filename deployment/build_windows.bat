@echo off
rem Build BASIRA AI desktop for Windows (one-file exe under dist\).
cd /d "%~dp0.."
python -m pip install --quiet pyinstaller
pyinstaller deployment\basira.spec --noconfirm
echo Build output: dist\BASIRA-AI.exe
