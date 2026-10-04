"""Safe text for Markdown output. Model responses are untrusted: they must not break tables or inject HTML."""
import re

_ENTITIES = {"<": "&lt;", ">": "&gt;"}


def md_text(text: str, limit: int = 300) -> str:
    t = re.sub(r"\s+", " ", text or "").strip()
    if len(t) > limit:
        t = t[:limit] + "…"
    t = "".join(_ENTITIES.get(c, c) for c in t)
    return t.replace("|", "\\|").replace("`", "'")


def md_code(text: str, limit: int = 200) -> str:
    return f"`{md_text(text, limit)}`" if (text or "").strip() else "*(empty)*"


def table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "*(none)*\n"
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out) + "\n"


def pct(x: float | None, digits: int = 1) -> str:
    return "n/a" if x is None else f"{x * 100:.{digits}f}%"


def interval(lo: float | None, hi: float | None) -> str:
    return "n/a" if lo is None or hi is None else f"[{pct(lo)}, {pct(hi)}]"
