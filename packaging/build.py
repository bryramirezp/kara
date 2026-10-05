"""Build everything a release ships.

    py -3 packaging/build.py --gpu-component   build the optional NVIDIA payload
    py -3 packaging/build.py                   build the one installer

Leaves in dist/:
    Kara-Setup-<version>.exe          the only installer
    Kara-GPU-<version>.zip            optional NVIDIA DLL payload
    Kara-<version>-portable.zip       the CPU app, unzip and run
    SHA256SUMS.txt                    hashes of every public artifact

The version is read from __version__ in kara.py, which is the only
place it is written down.

The two builds cannot share a dist/Kara directory, so run them one at a time;
each starts by clearing what the other left.
"""
import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
APP  = os.path.join(DIST, "Kara")

# winget installs Inno Setup per user by default, the GitHub runners get it
# machine-wide through choco, and either way someone may just have it on PATH.
ISCC_CANDIDATES = [
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Inno Setup 6", "ISCC.exe"),
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
]


def version():
    src = open(os.path.join(ROOT, "kara.py"), encoding="utf-8").read()
    m = re.search(r'^__version__\s*=\s*"([^"]+)"', src, re.M)
    if not m:
        sys.exit("no __version__ found in kara.py")
    return m.group(1)


def run(cmd, env=None):
    print("  $", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, cwd=ROOT, check=True, env=env)


def build_exe(gpu):
    print("== PyInstaller ==")
    env = dict(os.environ)
    if gpu:
        env["KARA_GPU"] = "1"
    else:
        # Explicitly cleared rather than merely absent: a shell where it was set
        # for an earlier build would otherwise produce the 570 MB file under
        # the small one's name, and nothing downstream would notice.
        env.pop("KARA_GPU", None)
    # The previous flavour's files are still in there and PyInstaller does not
    # remove what it no longer produces.
    shutil.rmtree(APP, ignore_errors=True)
    run([sys.executable, "-m", "PyInstaller", "--noconfirm",
         os.path.join("packaging", "kara.spec")], env=env)
    exe = os.path.join(APP, "Kara.exe")
    if not os.path.exists(exe):
        sys.exit(f"expected {exe}")


def sign_artifact(path):
    """Run the maintainer-provided Authenticode command, if configured.

    KARA_SIGN_COMMAND must contain ``{file}``; keeping the certificate command
    outside Git avoids putting a PFX, password or provider credentials in this
    repository.  A production release should set it to a SignTool command with
    SHA-256 and an RFC 3161 timestamp.
    """
    command = os.environ.get("KARA_SIGN_COMMAND")
    if not command:
        return False
    if "{file}" not in command:
        sys.exit("KARA_SIGN_COMMAND must contain {file}")
    run([part.replace("{file}", path) for part in shlex.split(command)])
    return True


def build_installer(ver, signed):
    print("== Inno Setup ==")
    iscc = next((p for p in ISCC_CANDIDATES if p and os.path.exists(p)),
                shutil.which("ISCC"))
    if not iscc:
        sys.exit("Inno Setup 6 not found. winget install JRSoftware.InnoSetup")
    cmd = [iscc, f"/DAppVersion={ver}"]
    if signed:
        # Inno uses the same provider command to sign setup.exe and unins*.exe.
        inno_command = os.environ["KARA_SIGN_COMMAND"].replace("{file}", "$f")
        cmd.extend(["/DSignKara=1", f"/Skara={inno_command}"])
    run(cmd + [os.path.join("packaging", "installer.iss")])


def build_zip(ver):
    print("== portable zip ==")
    out = os.path.join(DIST, f"Kara-{ver}-portable.zip")
    if os.path.exists(out):
        os.remove(out)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for folder, _, files in os.walk(APP):
            for name in files:
                full = os.path.join(folder, name)
                # Keep the folder in the archive: unzipping 400 loose files into
                # whatever directory the user happened to be in is unkind.
                z.write(full, os.path.join(
                    "Kara", os.path.relpath(full, APP)))
    return out


def write_hashes(paths):
    print("== SHA256 ==")
    lines = []
    for p in paths:
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        lines.append(f"{h.hexdigest()}  {os.path.basename(p)}")
        print("  " + lines[-1])
    out = os.path.join(DIST, "SHA256SUMS.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return out


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_gpu_component(ver):
    """Build the NVIDIA wheels once, then publish only their DLL tree."""
    build_exe(True)
    source = os.path.join(APP, "_internal", "nvidia")
    if not os.path.isdir(source):
        sys.exit("GPU build did not create dist/Kara/_internal/nvidia")
    out = os.path.join(DIST, f"Kara-GPU-{ver}.zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for folder, _, files in os.walk(source):
            for name in files:
                full = os.path.join(folder, name)
                arcname = os.path.relpath(full, os.path.join(APP, "_internal"))
                z.write(full, arcname.replace(os.sep, "/"))
    manifest = {
        "version": ver,
        "url": f"https://github.com/bryramirezp/kara/releases/download/v{ver}/"
               f"Kara-GPU-{ver}.zip",
        "sha256": _sha256(out),
        "bytes": os.path.getsize(out),
    }
    with open(os.path.join(DIST, f"Kara-GPU-{ver}.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        f.write("\n")
    return out, manifest


def read_gpu_manifest(ver):
    path = os.path.join(DIST, f"Kara-GPU-{ver}.json")
    try:
        with open(path, encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, ValueError):
        sys.exit("GPU component is missing. Run: py -3 packaging/build.py --gpu-component")
    if manifest.get("version") != ver or not os.path.exists(os.path.join(DIST, f"Kara-GPU-{ver}.zip")):
        sys.exit("GPU component metadata does not match this version")
    return manifest


def embed_gpu_manifest(manifest):
    """Place the exact component contract inside the CPU application's data."""
    path = os.path.join(APP, "_internal", "assets", "gpu-component.json")
    if not os.path.exists(os.path.dirname(path)):
        sys.exit("CPU build did not include assets/gpu-component.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        f.write("\n")


def stamp_docs():
    """Write the new version and installer size into the docs that quote them.

    Runs last, because the size is only knowable once the installer exists.
    """
    print("== docs ==")
    run([sys.executable, os.path.join("tools", "stamp_docs.py")])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--gpu-component", action="store_true",
                    help="build the optional NVIDIA DLL zip and its manifest")
    args = ap.parse_args()
    ver = version()
    print(f"Kara {ver}\n")
    if args.gpu_component:
        payload, manifest = build_gpu_component(ver)
        print("\n== GPU component ready ==")
        print("  " + os.path.basename(payload))
        print("  " + manifest["sha256"])
        return payload

    manifest = read_gpu_manifest(ver)
    build_exe(False)
    embed_gpu_manifest(manifest)
    signed = sign_artifact(os.path.join(APP, "Kara.exe"))
    build_installer(ver, signed)
    zip_path = build_zip(ver)
    payload = os.path.join(DIST, f"Kara-GPU-{ver}.zip")
    setup = os.path.join(DIST, f"Kara-Setup-{ver}.exe")
    if not os.path.exists(setup):
        sys.exit(f"expected {setup}")
    write_hashes([setup, zip_path, payload])
    stamp_docs()

    print("\n== ready ==")
    for name in sorted(os.listdir(DIST)):
        p = os.path.join(DIST, name)
        if os.path.isfile(p):
            print(f"  {name:44s} {os.path.getsize(p)/1024/1024:7.1f} MB")
    return setup


if __name__ == "__main__":
    main()
