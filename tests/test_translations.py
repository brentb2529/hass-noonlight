"""Guard: strings.json (dev source) and translations/en.json (runtime English)
must stay in sync. They are maintained as two files; this catches drift so a
copy edit made in only one of them can't ship wrong/stale UI text."""

from __future__ import annotations

import json
from pathlib import Path

_COMPONENT = Path(__file__).parent.parent / "custom_components" / "noonlight"


def test_strings_and_en_translation_match():
    strings = json.loads((_COMPONENT / "strings.json").read_text("utf-8"))
    en = json.loads(
        (_COMPONENT / "translations" / "en.json").read_text("utf-8")
    )
    assert strings == en, (
        "strings.json and translations/en.json have drifted; keep them "
        "identical (edit both)."
    )
