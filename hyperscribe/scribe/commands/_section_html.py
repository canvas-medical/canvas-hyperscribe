"""Parse the Hyperscribe-emitted ROS / PE HTML back into structured sections.

The custom-command HTML produced by `ros_sections.html` is a deterministic
sequence of `<div><b>Title:</b> text</div>` blocks (see
hyperscribe/scribe/templates/ros_sections.html). This parser is the inverse:
given a stored CustomCommand's HTML content, return a list of
`{"title": ..., "text": ...}` dicts.

Used by the "show last visit" feature in the Scribe UI to surface a
read-only reference to the same provider's prior PE / ROS for the same
patient. Implemented with `re` to stay within the Canvas plugin sandbox's
allowed imports (html.parser / html.unescape are not available there).
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

# The write path (physical_exam.py / ros.py) runs the rendered HTML through
# `html.encode("ascii", "xmlcharrefreplace").decode("ascii")`, which emits
# numeric character refs (`&#176;`, `&#x27;`, …) for every non-ASCII codepoint.
# Django's autoescape additionally turns `&`, `<`, `>`, `"`, `'` into named
# refs. The Preact UI renders these section payloads as plain text nodes,
# which DON'T auto-decode entities — without this decode step, providers
# would see literal `&#176;`, `&amp;`, etc. in the prior-visit reference UI.
_NUMERIC_REF = re.compile(r"&#([xX][0-9a-fA-F]+|[0-9]+);")
_NAMED_REFS = {"&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&apos;": "'"}


def _decode_html_entities(s: str) -> str:
    """Decode numeric (`&#NNN;` / `&#xHH;`) and the five XML-named (`&amp;` etc.)
    character refs. Sandbox-safe — no `html.unescape`, only `re.sub` and
    `str.replace`. Numeric refs are decoded first so that any literal `&` they
    produce isn't mistakenly re-interpreted in the named-ref pass."""
    def _decode_numeric(match: re.Match[str]) -> str:
        ref = match.group(1)
        try:
            cp = int(ref[1:], 16) if ref[:1] in ("x", "X") else int(ref)
            return chr(cp)
        except (ValueError, OverflowError):
            return match.group(0)
    s = _NUMERIC_REF.sub(_decode_numeric, s)
    for named, char in _NAMED_REFS.items():
        if named in s:
            s = s.replace(named, char)
    return s


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
            title = _decode_html_entities(raw_title.rstrip(":").strip())
            text = _decode_html_entities(raw_text.strip())
            if title:
                sections.append({"title": title, "text": text})
    except Exception:
        return []
    return sections
