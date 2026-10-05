# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build for Kara.

    py -3 -m PyInstaller --noconfirm packaging/kara.spec
    set KARA_GPU=1 && py -3 -m PyInstaller ... packaging/kara.spec

The normal build is the one small CPU application.  The GPU invocation is only
an internal release step: packaging/build.py extracts its NVIDIA DLL tree into
the optional, verified Kara-GPU zip and never produces a second installer.

onedir rather than onefile: onefile unpacks the whole thing into a temporary
folder on every single launch, which for 190 MB is a wait before anything even
appears on screen, and for 1.2 GB would be unusable.
"""
import glob
import os
import site
import sys
from PyInstaller.utils.hooks import (collect_all, collect_data_files,
                                     collect_dynamic_libs)

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
GPU = bool(os.environ.get("KARA_GPU"))
print("== Kara spec: %s build ==" % ("GPU" if GPU else "processor-only"))

datas = [
    (os.path.join(ROOT, "assets", "icon.ico"), "assets"),
    (os.path.join(ROOT, "assets", "gpu-component.json"), "assets"),
]
binaries = []
hiddenimports = []

# Python 3.11 on Windows can report a valid Tcl/Tk installation as broken to
# PyInstaller's hook.  Kara imports CustomTkinter at startup, so ship the
# standard-library modules, DLLs and script directories explicitly.
PYTHON_ROOT = sys.base_prefix
TCL_DIR = next((p for p in glob.glob(os.path.join(PYTHON_ROOT, "tcl", "tcl*"))
                if os.path.isfile(os.path.join(p, "init.tcl"))), None)
TK_DIR = next((p for p in glob.glob(os.path.join(PYTHON_ROOT, "tcl", "tk*"))
               if os.path.isfile(os.path.join(p, "pkgIndex.tcl"))), None)
if not TCL_DIR or not TK_DIR:
    raise SystemExit("Python Tcl/Tk runtime is incomplete")
for name in ("_tkinter.pyd", "tcl86t.dll", "tk86t.dll"):
    path = os.path.join(PYTHON_ROOT, "DLLs", name)
    if not os.path.isfile(path):
        raise SystemExit("Python Tcl/Tk binary is missing: " + path)
    binaries.append((path, "."))
datas += [(TCL_DIR, os.path.join("tcl", os.path.basename(TCL_DIR))),
          (TK_DIR, os.path.join("tcl", os.path.basename(TK_DIR))),
          (os.path.join(PYTHON_ROOT, "Lib", "tkinter"), "tkinter")]
hiddenimports += ["_tkinter"]

# Reads its theme JSON and its fonts from disk at runtime.
datas += collect_data_files("customtkinter")
# Ships the PortAudio DLL as package data.
datas += collect_data_files("sounddevice")
# Ships the Silero voice-activity model as an .onnx file.
datas += collect_data_files("faster_whisper")
# The engine itself: a 57 MB DLL that no import scan would ever notice.
binaries += collect_dynamic_libs("ctranslate2")

# Runs the voice-activity model. Loads its providers dynamically, so nothing
# short of collect_all finds them.
for pkg in ("onnxruntime", "av"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h


def nvidia_dlls():
    """The CUDA DLLs, keeping the nvidia/<lib>/bin shape the wheels ship them in.

    collect_dynamic_libs would flatten them into one directory. The shape is not
    decoration: kara._add_nvidia_dlls walks exactly this layout to hand each
    folder to os.add_dll_directory, which since Python 3.8 is the only way an
    extension module finds a DLL at all. Flattened, ctranslate2 would fail to
    load a model with a message naming cublas64_12.dll, in a build that is
    carrying cublas64_12.dll.
    """
    roots = []
    for getter in ("getsitepackages", "getusersitepackages"):
        if hasattr(site, getter):
            got = getattr(site, getter)()
            roots.extend(got if isinstance(got, list) else [got])

    found = []
    for root in roots:
        for folder in glob.glob(os.path.join(root, "nvidia", "*", "bin")):
            dest = os.path.relpath(folder, root)          # nvidia\<lib>\bin
            for dll in glob.glob(os.path.join(folder, "*.dll")):
                found.append((dll, dest))
    if not found:
        raise SystemExit(
            "KARA_GPU is set but no NVIDIA wheels were found.\n"
            "  pip install -r requirements-gpu.txt")
    print("   %d CUDA DLLs" % len(found))
    return found


if GPU:
    binaries += nvidia_dlls()

EXCLUDES = [
    "torch",        # faster-whisper runs on ctranslate2, not torch
    "matplotlib", "scipy", "pandas", "IPython", "pytest", "setuptools",
]
if not GPU:
    # 925 MB of CUDA libraries, kept out of the ordinary download. The GPU build
    # adds them back through nvidia_dlls() above rather than through the import
    # scan, because the scan cannot preserve the directory layout they need.
    EXCLUDES.append("nvidia")

a = Analysis(
    [os.path.join(ROOT, "kara.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="Kara",
    debug=False,
    strip=False,
    upx=False,          # UPX-packed binaries trip antivirus heuristics
    console=False,      # tray app: a console window would sit there empty
    icon=os.path.join(ROOT, "assets", "icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Kara",
)
