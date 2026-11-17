# INSTALLATION — BASIRA AI Desktop

## المتطلبات
- Python 3.10+ (مُختبَر على 3.12)
- 4GB RAM كحد أدنى (8GB مستحسن)، مساحة 3GB للنماذج
- كاميرا وميكروفون اختياريان (التطبيق يعمل ويُظهر "غير متوفر" بدونهما)

## Linux (مُختبَر على Debian 13)

```bash
sudo apt install python3-venv libportaudio2 libgl1 libgles2 libegl1 libxcb1
git clone <repo> BASIRA-AI && cd BASIRA-AI
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/download_models.py      # ~250MB مرة واحدة
python scripts/run_desktop.py
```

## Windows 10/11

```bat
py -3 -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python scripts\download_models.py
python scripts\run_desktop.py
```

ملاحظة: على Windows تتضمن حزم sounddevice/PySide6 كل ما يلزم دون حزم نظام.

## بناء ملف تثبيت

```bash
# Linux
bash deployment/build_linux.sh      # → dist/BASIRA-AI
# Windows
deployment\build_windows.bat        # → dist\BASIRA-AI.exe
```

النماذج لا تُضمَّن في الملف التنفيذي؛ تُنزَّل في أول تشغيل عبر
Model Download Manager (`scripts/download_models.py`).

## الخدمة المحلية الخلفية (اختيارية)

```bash
python scripts/run_server.py --show-token   # اطبع التوكن
python scripts/run_server.py                # 127.0.0.1:8765 فقط
```
