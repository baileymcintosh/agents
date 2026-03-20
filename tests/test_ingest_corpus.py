from scripts.ingest_corpus import (
    _apply_keep_ranges,
    _extract_article_body,
    _finalize_content,
    _has_minimum_substance,
    _strip_boilerplate,
    _substantive_char_count,
)


def test_strip_boilerplate_falls_back_to_h1_when_no_long_prose_found():
    text = "\n".join(
        [
            "Select Your Experience",
            "KKR Global",
            "Wealth Professionals",
            "# European Tech CEOs in Conversation",
            "* About",
            "* Approach",
            "Short body paragraph with real article content that is not especially long.",
            "Another short but substantive paragraph explaining what the CEOs discussed.",
        ]
    )

    cleaned = _strip_boilerplate(text)

    assert cleaned.startswith("# European Tech CEOs in Conversation")
    assert "Select Your Experience" not in cleaned


def test_extract_article_body_cuts_footer_boilerplate():
    text = "\n".join(
        [
            "# Marc Rowan Fireside Chat",
            "This is the substantive body of the article and it should remain.",
            "Tags",
            "Recommended For You",
            "Footer link 1",
            "Footer link 2",
        ]
    )

    cleaned = _extract_article_body(text)

    assert "Recommended For You" not in cleaned
    assert "Footer link 1" not in cleaned
    assert "substantive body" in cleaned


def test_finalize_content_drops_leading_pdf_disclaimer_block():
    text = "\n".join(
        [
            "Important information: This document is for informational purposes only and does not constitute investment advice.",
            "Copyright © 2023 Apollo Global Management. All rights reserved.",
            "# Beyond Beta",
            "This paper analyzes the role of alternatives in diversified portfolios.",
        ]
    )

    cleaned = _finalize_content(text)

    assert cleaned.startswith("# Beyond Beta")
    assert "Important information" not in cleaned


def test_minimum_substance_gate_rejects_thin_pages():
    thin = "\n".join(
        [
            "# Strengthening Infrastructure",
            "Watch the video.",
            "Recommended For You",
            "[Another page](https://example.com/another)",
        ]
    )

    assert _substantive_char_count(thin) < 500
    assert not _has_minimum_substance(thin)


def test_minimum_substance_gate_accepts_real_article_body():
    body = " ".join(["This paragraph contains substantive analysis of infrastructure debt markets."] * 12)
    text = f"# Article\n\n{body}\n\n{body}"

    assert _substantive_char_count(text) >= 500
    assert _has_minimum_substance(text)


def test_apply_keep_ranges_stitches_selected_blocks():
    text = "\n".join(["a", "b", "c", "d", "e", "f"])

    kept = _apply_keep_ranges(text, [[2, 3], [5, 6]])

    assert kept == "b\nc\n\ne\nf"
