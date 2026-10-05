"""Download and install Kara's optional NVIDIA runtime safely.

The manifest comes from the installed Kara build.  A release builder writes its
exact URL, byte count and SHA-256 into that manifest after it has built the GPU
payload.  This module deliberately accepts only the NVIDIA DLL layout Kara
loads, never arbitrary files from an archive.
"""
import hashlib
import json
import os
from pathlib import PurePosixPath
import shutil
import tempfile
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import zipfile


class GpuComponentError(RuntimeError):
    """The optional GPU component could not be trusted or installed."""


def load_manifest(path):
    """Read and validate the release-bound GPU component manifest."""
    try:
        with open(path, encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, ValueError) as exc:
        raise GpuComponentError("GPU support is not available in this Kara build.") from exc

    required = ("version", "url", "sha256", "bytes")
    if not all(manifest.get(key) for key in required):
        raise GpuComponentError("GPU support is not available in this Kara build.")
    if (not isinstance(manifest["version"], str)
            or not isinstance(manifest["url"], str)
            or not isinstance(manifest["sha256"], str)
            or len(manifest["sha256"]) != 64
            or any(ch not in "0123456789abcdef" for ch in manifest["sha256"].lower())
            or not isinstance(manifest["bytes"], int)
            or manifest["bytes"] <= 0):
        raise GpuComponentError("GPU support manifest is invalid.")

    url = urlparse(manifest["url"])
    if url.scheme != "https" or url.hostname != "github.com":
        raise GpuComponentError("GPU support manifest has an untrusted download URL.")
    return manifest


def component_dir(app_dir, manifest):
    return os.path.join(app_dir, "gpu", manifest["version"])


def _marker_path(app_dir, manifest):
    return os.path.join(component_dir(app_dir, manifest), "kara-gpu.json")


def is_installed(app_dir, manifest):
    """True only for a component that was verified by this Kara release."""
    try:
        with open(_marker_path(app_dir, manifest), encoding="utf-8") as f:
            marker = json.load(f)
        if marker != manifest:
            return False
    except (OSError, ValueError):
        return False

    root = component_dir(app_dir, manifest)
    for folder, _, files in os.walk(os.path.join(root, "nvidia")):
        if any(name.lower().startswith("cublas64_") and name.lower().endswith(".dll")
               for name in files):
            return True
    return False


def _safe_member(info):
    """Return a safe NVIDIA DLL path, or reject the archive member."""
    if info.is_dir():
        return None
    path = PurePosixPath(info.filename)
    parts = path.parts
    mode = info.external_attr >> 16
    if (path.is_absolute() or ".." in parts or len(parts) < 4
            or parts[0] != "nvidia" or parts[-2] != "bin"
            or path.suffix.lower() != ".dll" or mode & 0o170000 == 0o120000):
        raise GpuComponentError("GPU support archive contains an unsafe file.")
    return path


def download_and_install(app_dir, manifest, progress=None):
    """Fetch, hash and atomically activate the optional NVIDIA DLLs.

    ``progress(received, total)`` is called from the caller's worker thread.
    Nothing is activated until the complete archive has passed every check.
    """
    if is_installed(app_dir, manifest):
        return component_dir(app_dir, manifest)

    os.makedirs(os.path.join(app_dir, "gpu"), exist_ok=True)
    fd, archive_path = tempfile.mkstemp(prefix="kara-gpu-", suffix=".zip",
                                        dir=os.path.join(app_dir, "gpu"))
    staging = None
    try:
        digest = hashlib.sha256()
        received = 0
        request = Request(manifest["url"], headers={"User-Agent": "Kara"})
        with os.fdopen(fd, "wb") as out, urlopen(request, timeout=30) as response:
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                received += len(block)
                if received > manifest["bytes"]:
                    raise GpuComponentError("GPU support download is larger than expected.")
                digest.update(block)
                out.write(block)
                if progress:
                    progress(received, manifest["bytes"])

        if received != manifest["bytes"]:
            raise GpuComponentError("GPU support download is incomplete.")
        if digest.hexdigest().lower() != manifest["sha256"].lower():
            raise GpuComponentError("GPU support download did not match its security check.")

        staging = tempfile.mkdtemp(prefix="kara-gpu-", dir=os.path.join(app_dir, "gpu"))
        dll_count = 0
        with zipfile.ZipFile(archive_path) as archive:
            for info in archive.infolist():
                relative = _safe_member(info)
                if relative is None:
                    continue
                target = os.path.join(staging, *relative.parts)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with archive.open(info) as source, open(target, "wb") as destination:
                    shutil.copyfileobj(source, destination)
                dll_count += 1

        if not dll_count or not any(
            name.lower().startswith("cublas64_") and name.lower().endswith(".dll")
            for _, _, names in os.walk(os.path.join(staging, "nvidia")) for name in names):
            raise GpuComponentError("GPU support archive is missing the CUDA libraries Kara needs.")

        with open(os.path.join(staging, "kara-gpu.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, sort_keys=True)

        target = component_dir(app_dir, manifest)
        if is_installed(app_dir, manifest):
            return target
        os.replace(staging, target)
        staging = None
        return target
    except zipfile.BadZipFile as exc:
        raise GpuComponentError("GPU support download is not a valid archive.") from exc
    finally:
        try:
            os.unlink(archive_path)
        except OSError:
            pass
        if staging:
            shutil.rmtree(staging, ignore_errors=True)
