"""RFC 9309 robots.txt matching.

urllib.robotparser ignores `*` and `$` wildcards and uses first-match instead of
longest-match, which gets real-world files (ag.ny.gov, deshaw.com, finra.org) wrong.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from urllib.parse import unquote, urlsplit


@dataclass
class Rules:
    allow: list[str] = field(default_factory=list)
    disallow: list[str] = field(default_factory=list)
    crawl_delay: float | None = None
    # "ok" parsed file, "missing" 4xx (allow all), "error" 5xx/network (disallow all),
    # "challenge" bot wall on robots.txt itself (treat host as blocked)
    state: str = "ok"
    note: str = ""

    def allowed(self, url: str) -> bool:
        if self.state == "missing":
            return True
        if self.state in ("error", "challenge"):
            return False
        parts = urlsplit(url)
        path = unquote(parts.path or "/") + (("?" + parts.query) if parts.query else "")
        if path == "/robots.txt":
            return True
        best_len, best_allow = -1, True
        for pat in self.allow:
            if _match(pat, path) and len(pat) >= best_len:
                best_len, best_allow = len(pat), True
        for pat in self.disallow:
            # ties go to allow (RFC 9309 2.2.2), so disallow must be strictly longer
            if _match(pat, path) and len(pat) > best_len:
                best_len, best_allow = len(pat), False
        return best_allow


MAX_CRAWL_DELAY = 30.0  # a hostile or typo'd Crawl-delay must not stall the whole run


def _delay(val: str) -> float | None:
    """Parse a Crawl-delay value; None for malformed, nan, inf or negative; clamped to MAX_CRAWL_DELAY."""
    try:
        d = float(val)
    except ValueError:
        return None
    if math.isnan(d) or d < 0:
        return None
    return min(d, MAX_CRAWL_DELAY)  # inf clamps to the maximum


_pat_cache: dict[str, re.Pattern] = {}


def _match(pattern: str, path: str) -> bool:
    if pattern == "":
        return False
    rx = _pat_cache.get(pattern)
    if rx is None:
        anchored = pattern.endswith("$")
        body = pattern[:-1] if anchored else pattern
        # split on the literal '*' first: a percent-encoded %2A is a literal asterisk, not a wildcard
        rx = re.compile(".*".join(re.escape(unquote(seg)) for seg in body.split("*")) + ("$" if anchored else ""))
        _pat_cache[pattern] = rx
    return rx.match(path) is not None


def parse(text: str, ua_token: str) -> Rules:
    """Pick the group for our product token if present, else `*`; merge repeated groups."""
    groups: list[tuple[list[str], list[tuple[str, str]]]] = []
    agents: list[str] = []
    lines: list[tuple[str, str]] = []
    last_was_agent = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, val = line.split(":", 1)
        key, val = key.strip().lower(), val.strip()
        if key == "user-agent":
            if not last_was_agent and (agents or lines):
                groups.append((agents, lines))
                agents, lines = [], []
            agents.append(val.lower())
            last_was_agent = True
        else:
            last_was_agent = False
            if key in ("allow", "disallow", "crawl-delay"):
                if not agents:  # rules before any user-agent line apply to everyone
                    agents = ["*"]
                lines.append((key, val))
    if agents or lines:
        groups.append((agents, lines))

    token = ua_token.lower()
    mine = [g for g in groups if any(a != "*" and a in token for a in g[0])]
    chosen = mine or [g for g in groups if "*" in g[0]]
    rules = Rules()
    for _, glines in chosen:
        for key, val in glines:
            if key == "allow":
                rules.allow.append(val)
            elif key == "disallow":
                rules.disallow.append(val)
            elif key == "crawl-delay":
                if (d := _delay(val)) is not None:
                    rules.crawl_delay = max(rules.crawl_delay or 0.0, d)
    # A crawl-delay placed before any user-agent line (citadel.com) still applies to us.
    if rules.crawl_delay is None:
        m = re.search(r"(?im)^\s*crawl-delay\s*:\s*([^\s#]+)", text)
        if m and not re.search(r"(?im)^\s*user-agent", text[: m.start()]):
            rules.crawl_delay = _delay(m.group(1))
    return rules
