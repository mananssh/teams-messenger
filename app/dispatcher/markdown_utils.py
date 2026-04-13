"""Lightweight markdown-to-HTML conversion for Teams and email."""

from __future__ import annotations

import re

_BLOCKQUOTE_STYLE = (
    "border-left:3px solid #6264a7;padding:8px 12px;"
    "margin:8px 0;background:#f5f5f5;color:#333"
)


def markdown_to_html(md: str) -> str:
    """Convert markdown to HTML suitable for Teams chat and email."""
    lines = md.split("\n")
    html_lines: list[str] = []
    in_ul = False
    in_ol = False
    in_bq = False
    bq_lines: list[str] = []

    def _flush_blockquote() -> None:
        nonlocal in_bq
        if in_bq and bq_lines:
            inner = "<br>".join(_inline_format(l) for l in bq_lines)
            html_lines.append(
                f'<blockquote style="{_BLOCKQUOTE_STYLE}">{inner}</blockquote>'
            )
            bq_lines.clear()
        in_bq = False

    def _flush_list() -> None:
        nonlocal in_ul, in_ol
        if in_ul:
            html_lines.append("</ul>")
            in_ul = False
        if in_ol:
            html_lines.append("</ol>")
            in_ol = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("> "):
            _flush_list()
            content = stripped[2:]
            if not in_bq:
                in_bq = True
            bq_lines.append(content)
            continue

        if in_bq:
            if not stripped:
                bq_lines.append("")
                continue
            _flush_blockquote()

        if not stripped:
            _flush_list()
            html_lines.append("<br>")
            continue

        if stripped.startswith("* ") or stripped.startswith("- "):
            _flush_blockquote()
            if in_ol:
                html_lines.append("</ol>")
                in_ol = False
            item = stripped[2:]
            if not in_ul:
                html_lines.append("<ul>")
                in_ul = True
            html_lines.append(f"  <li>{_inline_format(item)}</li>")
            continue

        ol_match = re.match(r"^(\d+)\.\s+(.+)$", stripped)
        if ol_match:
            _flush_blockquote()
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            item = ol_match.group(2)
            if not in_ol:
                html_lines.append("<ol>")
                in_ol = True
            html_lines.append(f"  <li>{_inline_format(item)}</li>")
            continue

        _flush_list()
        _flush_blockquote()

        if stripped.startswith("### "):
            html_lines.append(f"<h3>{_inline_format(stripped[4:])}</h3>")
        elif stripped.startswith("## "):
            html_lines.append(f"<h2>{_inline_format(stripped[3:])}</h2>")
        elif stripped.startswith("# "):
            html_lines.append(f"<h1>{_inline_format(stripped[2:])}</h1>")
        else:
            html_lines.append(f"<p>{_inline_format(stripped)}</p>")

    _flush_blockquote()
    _flush_list()

    return "\n".join(html_lines)


def _inline_format(text: str) -> str:
    """Convert inline markdown (bold, italic, code) to HTML."""
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return text
