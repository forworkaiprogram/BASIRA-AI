#!/bin/bash
set -e

echo "==> Installing system libraries for Qt / PortAudio"
sudo apt-get update -qq
sudo apt-get install -y -qq libgl1 libegl1 libxcb1 libxcb-icccm4 libxcb-cursor0 \
    libxcb-keysyms1 libxcb-shape0 libxcb-randr0 libxcb-xfixes0 libxcb-xkb1 \
    libxcb-render-util0 libxcb-image0 libxcb-shm0 libxcb-sync1 libxcb-util1 \
    libxkbcommon-x11-0 libportaudio2 fonts-noto-core fonts-noto-arabic

echo "==> Installing Python dependencies"
pip install -r requirements.txt

echo "==> Downloading AI models (~87 MB, verified with sha256)"
python scripts/download_models.py

echo "==> Running the test suite"
python -m pytest

echo ""
echo "BASIRA AI devcontainer ready."
echo "  Desktop UI : python run_desktop.py  (opens in the noVNC browser tab, port 6080)"
echo "  Local API  : python scripts/run_server.py --show-token"
