import json
import zipfile

from tools import trace_report


def test_load_deduplicates_export_copies_without_losing_distinct_cycles(tmp_path):
    rows = [
        {"machine": "PC", "seq": 1, "ts": "2026-01-01T00:00:00+00:00"},
        {"machine": "PC", "seq": 2, "ts": "2026-01-01T00:00:00+00:00"},
    ]
    content = "".join(json.dumps(row) + "\n" for row in rows)
    (tmp_path / "trace.jsonl").write_text(content, encoding="utf-8")
    extracted = tmp_path / "extracted"
    extracted.mkdir()
    (extracted / "trace.jsonl").write_text(content, encoding="utf-8")
    with zipfile.ZipFile(tmp_path / "diagnostics.zip", "w") as archive:
        archive.writestr("trace.jsonl", content)

    loaded, paths = trace_report.load(str(tmp_path))

    assert len(paths) == 3
    assert loaded == rows
