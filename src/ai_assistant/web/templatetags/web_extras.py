"""Custom Django template filters."""

from __future__ import annotations

import re

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name="markdown_to_html", is_safe=True)
def markdown_to_html(value: str) -> str:
    """Convert a subset of Markdown to safe HTML for server-rendered content."""
    if not value:
        return ""
    text = str(value)

    # Fenced code blocks
    text = re.sub(
        r"```(\w*)\n(.*?)```",
        lambda m: f'<pre><code class="lang-{m.group(1)}">{_escape(m.group(2))}</code></pre>',
        text,
        flags=re.DOTALL,
    )
    # Inline code
    text = re.sub(r"`([^`]+)`", lambda m: f"<code>{_escape(m.group(1))}</code>", text)
    # Headers
    text = re.sub(r"^#### (.+)$", r"<h4>\1</h4>", text, flags=re.MULTILINE)
    text = re.sub(r"^### (.+)$", r"<h3>\1</h3>", text, flags=re.MULTILINE)
    text = re.sub(r"^## (.+)$", r"<h2>\1</h2>", text, flags=re.MULTILINE)
    text = re.sub(r"^# (.+)$", r"<h1>\1</h1>", text, flags=re.MULTILINE)
    # Bold / italic
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    # Unordered lists
    text = re.sub(r"^[-*] (.+)$", r"<li>\1</li>", text, flags=re.MULTILINE)
    text = re.sub(r"(<li>.*?</li>(\n|$))+", lambda m: f"<ul>{m.group(0)}</ul>", text, flags=re.DOTALL)
    # Paragraphs (double newline)
    parts = re.split(r"\n{2,}", text.strip())
    wrapped = []
    for part in parts:
        part = part.strip()
        if part and not part.startswith("<"):
            part = f"<p>{part.replace(chr(10), '<br>')}</p>"
        wrapped.append(part)
    return mark_safe("\n".join(wrapped))


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
