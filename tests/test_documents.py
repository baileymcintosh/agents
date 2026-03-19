from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from agentorg.tools.search import fetch_document


def test_fetch_document_uses_pdf_parser_when_pdf_detected(temp_dir: Path) -> None:
    mock_response = MagicMock()
    mock_response.headers = {"content-type": "application/pdf"}
    mock_response.content = b"%PDF-1.4 fake"
    mock_response.raise_for_status.return_value = None

    pdf_path = temp_dir / "paper.pdf"

    with patch("agentorg.tools.search.httpx.get", return_value=mock_response), \
         patch("agentorg.tools.search._extract_pdf_text", return_value=("## Page 1\nHello PDF", 3)), \
         patch("agentorg.tools.search._pdf_storage_path", return_value=pdf_path):
        result = fetch_document("https://example.com/paper.pdf")

    assert "**Type:** PDF" in result
    assert "Hello PDF" in result
    assert pdf_path.exists()


def test_fetch_document_falls_back_to_fetch_url_for_html() -> None:
    mock_response = MagicMock()
    mock_response.headers = {"content-type": "text/html"}
    mock_response.content = b"<html></html>"
    mock_response.raise_for_status.return_value = None

    with patch("agentorg.tools.search.httpx.get", return_value=mock_response), \
         patch("agentorg.tools.search.fetch_url", return_value="full article text"):
        result = fetch_document("https://example.com/post")

    assert result == "full article text"
