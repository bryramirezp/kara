"""Build everything a release ships.

    py -3 packaging/build.py                   build CPU and NVIDIA installers

Leaves in dist/:
    Kara-Setup-<version>.exe          CPU installer
    Kara-Setup-GPU-<version>.exe      NVIDIA installer
    SHA256SUMS.txt                    hashes of both installers

The version is read from __version__ in kara.py, which is the only
place it is written down.

The two builds cannot share a dist/Kara directory, so run them one at a time;
each starts by clearing what the other left.
"""
import hashlib
import os
import re
import shlex
import shutil
import subprocess
import sys

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
    nvidia = os.path.join(APP, "_internal", "nvidia")
    if gpu != os.path.isdir(nvidia):
        flavour = "GPU" if gpu else "CPU"
        sys.exit(f"{flavour} build has the wrong NVIDIA payload")


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


def setup_path(ver, gpu):
    suffix = "-GPU" if gpu else ""
    return os.path.join(DIST, f"Kara-Setup{suffix}-{ver}.exe")


def build_installer(ver, signed, gpu):
    print("== Inno Setup ==")
    iscc = next((p for p in ISCC_CANDIDATES if p and os.path.exists(p)),
                shutil.which("ISCC"))
    if not iscc:
        sys.exit("Inno Setup 6 not found. winget install JRSoftware.InnoSetup")
    cmd = [iscc, f"/DAppVersion={ver}"]
    if gpu:
        cmd.append("/DGpuBuild=1")
    if signed:
        # Inno uses the same provider command to sign setup.exe and unins*.exe.
        inno_command = os.environ["KARA_SIGN_COMMAND"].replace("{file}", "$f")
        cmd.extend(["/DSignKara=1", f"/Skara={inno_command}"])
    run(cmd + [os.path.join("packaging", "installer.iss")])


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


def stamp_docs():
    """Write the new version and installer size into the docs that quote them.

    Runs last, because the size is only knowable once the installer exists.
    """
    print("== docs ==")
    run([sys.executable, os.path.join("tools", "stamp_docs.py")])


def main():
    ver = version()
    print(f"Kara {ver}\n")

    # Each installer is compiled immediately after its matching application
    # payload, so the CPU installer cannot inherit CUDA from the GPU build.
    build_exe(False)
    signed = sign_artifact(os.path.join(APP, "Kara.exe"))
    build_installer(ver, signed, False)

    build_exe(True)
    signed = sign_artifact(os.path.join(APP, "Kara.exe"))
    build_installer(ver, signed, True)

    cpu_setup = setup_path(ver, False)
    gpu_setup = setup_path(ver, True)
    for path in (cpu_setup, gpu_setup):
        if not os.path.exists(path):
            sys.exit(f"expected {path}")
    write_hashes([cpu_setup, gpu_setup])
    stamp_docs()

    print("\n== ready ==")
    for name in sorted(os.listdir(DIST)):
        p = os.path.join(DIST, name)
        if os.path.isfile(p):
            print(f"  {name:44s} {os.path.getsize(p)/1024/1024:7.1f} MB")
    return cpu_setup


if __name__ == "__main__":
    main()
