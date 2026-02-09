from __future__ import annotations

import sys
from pathlib import Path

from pokepocketpedia import cli


def test_build_site_copies_reports_and_writes_index(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    snapshot = "2026-02-08"
    reports_dir = tmp_path / "data" / "processed" / "reports" / snapshot
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "meta_overview.html").write_text("<html>meta</html>", encoding="utf-8")
    (reports_dir / "recommendation.deck-a.html").write_text("<html>a</html>", encoding="utf-8")
    (reports_dir / "recommendation.deck-b.html").write_text("<html>b</html>", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        ["pokepocketpedia-build-site", "--snapshot-date", snapshot],
    )
    exit_code = cli.build_site()
    assert exit_code == 0

    docs_root = tmp_path / "docs"
    index_file = docs_root / "index.html"
    assert index_file.exists()
    index_html = index_file.read_text(encoding="utf-8")
    assert "PokePocketPedia Reports" in index_html
    assert f"reports/{snapshot}/meta_overview.html" in index_html
    assert f"reports/{snapshot}/recommendation.deck-a.html" in index_html
    assert (docs_root / ".nojekyll").exists()
    assert (docs_root / "reports" / snapshot / "meta_overview.html").exists()
    assert (docs_root / "reports" / snapshot / "recommendation.deck-a.html").exists()
