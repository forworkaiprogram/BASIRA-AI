# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for BASIRA AI desktop (Linux/Windows).
# Build:  pyinstaller deployment/basira.spec --noconfirm
import os
from pathlib import Path

block_cipher = None
root = Path(SPECPATH).parent


def find_system_libraries(names):
    """Locate shared libraries that PyInstaller cannot resolve from
    site-packages (e.g. libGL required by Qt's runtime plugins).
    Searches LD_LIBRARY_PATH and common system library directories."""
    import glob

    found = []
    search_dirs = [d for d in os.environ.get("LD_LIBRARY_PATH", "").split(os.pathsep) if d]
    search_dirs += [
        "/usr/lib/x86_64-linux-gnu",
        "/usr/lib/aarch64-linux-gnu",
        "/usr/lib64",
        "/usr/lib",
        "/lib/x86_64-linux-gnu",
        "/lib64",
        "/lib",
    ]
    for name in names:
        for d in search_dirs:
            hits = sorted(glob.glob(os.path.join(d, name)))
            if hits:
                found.append((os.path.realpath(hits[-1]), "."))
                break
    return found


# Qt needs libGL/libEGL at runtime; on minimal systems they live outside
# site-packages so bundle them when present (users without them install
# libgl1/libegl1 per docs/INSTALLATION.md).
gl_binaries = find_system_libraries(
    ["libGL.so.1*", "libGLdispatch.so.0*", "libglx.so.0*", "libEGL.so.1*", "libGLESv2.so.2*"]
)

a = Analysis(
    [str(root / "scripts" / "run_desktop.py")],
    pathex=[str(root)],
    binaries=gl_binaries,
    datas=[
        (str(root / "basira" / "desktop"), "basira/desktop"),
    ],
    hiddenimports=[
        "basira.engines.vision.detector",
        "basira.engines.vision.ocr",
        "basira.engines.sign.hand_tracker",
        "basira.engines.audio.stt",
        "basira.engines.language.tts",
        "easyocr",
        "mediapipe",
        "faster_whisper",
        "piper",
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.protocols.websockets.websockets_impl",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "IPython", "jupyter"],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas,
    name="BASIRA-AI",
    console=False,
    icon=str(root / "desktop_assets" / "basira.ico") if os.name == "nt" else None,
)

# Models are NOT bundled: the app downloads them on first run via
# scripts/download_models.py (Model Download Manager keeps updates small).
