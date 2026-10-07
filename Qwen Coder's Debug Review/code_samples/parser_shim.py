"""Sample: parser shim that ends the selectolax breakage class (Finding 1, fix option 2).

One import site for HTML parsing; prefers the modern Lexbor backend, falls back to the legacy
Modest backend on old installs. Radar modules would switch to `from .htmlparser import parse`.

Run:  python parser_shim.py         (prints the active backend and a extraction demo)
"""
from __future__ import annotations

BACKEND: str

try:  # modern path (selectolax >= 0.3.x also ships lexbor; recommended going forward)
    from selectolax.lexbor import LexborHTMLParser as _Parser
    BACKEND = "lexbor"
except ImportError:  # pragma: no cover
    try:
        from selectolax.parser import HTMLParser as _Parser  # legacy Modest backend (< 1.0 only)
        BACKEND = "modest-legacy"
    except ImportError:
        _Parser = None
        BACKEND = "none"


class Node:
    """Thin normalized wrapper so call sites don't branch on backend quirks."""

    def __init__(self, inner):
        self._n = inner

    @property
    def text(self) -> str:
        raw = self._n.text(separator=" ") or ""
        return " ".join(raw.split())          # same normalization textutil.html_to_text relies on

    def attr(self, name: str, default: str = "") -> str:
        return (self._n.attributes or {}).get(name, default)


def parse(html: str):
    if _Parser is None:
        raise RuntimeError("no HTML parser available; pip install 'selectolax>=0.3.21,<1.0' or migrate to lexbor")
    return _Parser(html)


def iter_css(html: str, selector: str):
    """css() exists on both backends; normalize iteration to Node wrappers."""
    tree = parse(html)
    for n in tree.css(selector):
        yield Node(n)


if __name__ == "__main__":
    html = """<div class="posting">
      <h2>Senior&nbsp;Counsel</h2>
      <p class="pay">$180,000 - $220,000 &nbsp; base</p>
    </div>"""
    print(f"backend: {BACKEND}")
    for sel in ("h2", "p.pay"):
        for node in iter_css(html, sel):
            print(f"{sel:>8} -> {node.text!r}")
    # requirements.txt band-aid until this shim lands everywhere:
    #   selectolax>=0.3.21,<1.0
