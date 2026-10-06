"""Release naming and the removal of the dynamic NVIDIA downloader."""
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("kara_build", ROOT / "packaging" / "build.py")
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)


def test_setup_names_are_versioned_and_distinct():
    assert Path(build.setup_path("0.3.4", False)).name == "Kara-Setup-0.3.4.exe"
    assert Path(build.setup_path("0.3.4", True)).name == "Kara-Setup-GPU-0.3.4.exe"


def test_runtime_has_no_dynamic_gpu_downloader():
    source = (ROOT / "kara.py").read_text(encoding="utf-8")
    assert "gpu_component" not in source
    assert "GPU_MANIFEST_FILE" not in source
    assert not (ROOT / "gpu_component.py").exists()
