from __future__ import annotations

import base64
from pathlib import Path

from agentorg.reporting.notebook import build_notebook


_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO5P2j8AAAAASUVORK5CYII="
)


def test_build_notebook_resolves_relative_chart_paths_from_base_dir(temp_dir: Path) -> None:
    reports_dir = temp_dir / "reports"
    charts_dir = reports_dir / "charts"
    charts_dir.mkdir(parents=True)
    png_path = charts_dir / "example.png"
    png_path.write_bytes(_PNG_1X1)

    nb = build_notebook(
        "# Title\n\n## Data & Charts\n\n![Example](charts/example.png)",
        {"example": png_path},
        metadata={"project": "Test"},
        base_dir=reports_dir,
    )

    assert nb is not None
    rendered = "\n".join(cell["source"] for cell in nb.cells if cell["cell_type"] == "markdown")
    assert "Chart not available" not in rendered
    assert "data:image/png;base64" in rendered
