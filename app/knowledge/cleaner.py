# ingest/cleaner.py
"""
Text cleaning before chunking.

Production cleaning pipeline:
  1. Optionally strip HTML tags (if content is HTML)
  2. Decode HTML entities (&amp; → &, &nbsp; → space)
  3. Remove common boilerplate (scripts, styles, nav, footer)
  4. Normalize whitespace (collapse runs of spaces/tabs)
  5. Normalize line breaks (cap consecutive newlines)
  6. Drop lines that are pure noise (only punctuation/digits)

Why this matters:
  Raw HTML fed to an embedding model pollutes the vectors with
  <div>, <script>, class="...", data-* attributes, and CSS. Cleaning
  first gives 10–30% better retrieval in practice.
"""
import html
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


# Tags whose entire content should be removed (not just the tag).
STRIP_TAG_BLOCKS = [
    "script", "style", "noscript", "iframe",
    "nav", "footer", "header", "aside",
]


def _strip_html_blocks(text: str) -> str:
    """Remove full <script>...</script>, <style>...</style>, etc."""
    for tag in STRIP_TAG_BLOCKS:
        pattern = rf"<{tag}\b[^>]*>.*?</{tag}>"
        text = re.sub(pattern, " ", text, flags=re.DOTALL | re.IGNORECASE)
    return text


def _strip_html_tags(text: str) -> str:
    """Remove all remaining HTML tags."""
    return re.sub(r"<[^>]+>", " ", text)


def _normalize_whitespace(text: str) -> str:
    """Collapse runs of spaces/tabs; cap consecutive newlines at 2."""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def _drop_noise_lines(text: str) -> str:
    """
    Drop lines that carry no information:
      - Only punctuation/symbols
      - Only 1–2 characters
      - Only digits (no context — usually page numbers or counters)
    """
    out = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            out.append("")   # keep blank lines for paragraph breaks
            continue

        # Pure punctuation/symbols
        if re.fullmatch(r"[\W_]+", stripped):
            continue

        # Very short fragments
        if len(stripped) < 3:
            continue

        # Pure digits (rarely useful alone)
        if re.fullmatch(r"\d+", stripped):
            continue

        out.append(line)

    return "\n".join(out)


def clean_text(
    raw:         str,
    strip_html:  bool = True,
    drop_noise:  bool = True,
) -> str:
    """
    Clean raw text for embedding and retrieval.

    Args:
        raw:        the raw text from the API
        strip_html: remove HTML tags + script/style blocks
        drop_noise: drop lines that carry no semantic content

    Returns:
        Cleaned text, ready for chunking.
    """
    if not raw or not raw.strip():
        return ""

    text = raw

    if strip_html:
        text = _strip_html_blocks(text)
        text = _strip_html_tags(text)

    # Decode entities like &amp; &#39; &nbsp;
    text = html.unescape(text)

    # Normalize whitespace
    text = _normalize_whitespace(text)

    if drop_noise:
        text = _drop_noise_lines(text)

    # Final trim
    text = text.strip()

    logger.debug(
        "Cleaned text: %d → %d chars",
        len(raw), len(text),
    )
    return text