from __future__ import annotations

from aurora.app.services.chat_service import clean_title


def test_clean_title_keeps_a_plain_short_name() -> None:
    assert clean_title('"Planning a Dubai trip."') == "Planning a Dubai trip"
    assert clean_title("**Fix build error**\nbecause the cache") == "Fix build error"
    assert clean_title("   ") == ""
    assert len(clean_title("x" * 100)) == 60
