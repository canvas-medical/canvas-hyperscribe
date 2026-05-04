"""Parse the Hyperscribe-emitted ROS / PE HTML back into structured sections.

The custom-command HTML produced by `ros_sections.html` is a deterministic
sequence of `<div><b>Title:</b> text</div>` blocks (see
hyperscribe/scribe/templates/ros_sections.html). This parser is the inverse:
given a stored CustomCommand's HTML content, return a list of
`{"title": ..., "text": ...}` dicts.

Used by the "show last visit" feature in the Scribe UI to surface a
read-only reference to the same provider's prior PE / ROS for the same
patient. Implemented with `re` to stay within the Canvas plugin sandbox's
allowed imports (html.parser is not available there).
"""

from __future__ import annotations

import re

# Matches one subsection block: <div ...><b>Title[:]</b> text</div>.
# Two unnamed groups (title, text) so we can iterate `findall`'s tuple
# results — `findall` is the only iterating regex method on the Canvas
# plugin sandbox's allowlist (`finditer`, `Match.group`, etc. are not).
# The title's trailing colon, if present, is stripped during normalization.
# DOTALL lets `text` span newlines for multi-line findings.
_SECTION_PATTERN = re.compile(
    r"<div[^>]*>\s*<b>([^<]*?)</b>([^<]*?)</div>",
    re.IGNORECASE | re.DOTALL,
)


def parse_ros_pe_html(html: str | None) -> list[dict[str, str]]:
    """Return structured sections parsed from a CustomCommand HTML body.

    Returns an empty list if the input is empty, doesn't match the expected
    pattern, or any other parsing problem occurs.
    """
    if not html:
        return []
    sections: list[dict[str, str]] = []
    try:
        for raw_title, raw_text in _SECTION_PATTERN.findall(html):
            title = raw_title.rstrip(":").strip()
            text = raw_text.strip()
            if title:
                sections.append({"title": title, "text": text})
    except Exception:
        return []
    return sections
