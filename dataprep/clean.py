from __future__ import annotations

import hashlib
import html
import math
import re

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_MONEY = re.compile(r"[-+]?\d[\d,]*\.?\d*")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?<![\w])(?:\+\d{1,3}[\s().-]?)?(?:\(?\d{2,4}\)?[\s.-]?)?\d{3,4}[\s.-]?\d{4}(?!\w)")
_DATE = re.compile(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}")


def clean_text(s: str | None) -> str:
    if not s:
        return ""
    s = html.unescape(str(s)).replace("\xa0", " ")
    s = _TAG.sub(" ", s)
    return _WS.sub(" ", s).strip()


def redact_contacts(s: str) -> str:
    """Mask obvious email/phone contacts without removing ordinary dates or amounts."""
    s = _EMAIL.sub("[email]", s)

    def redact_phone(match: re.Match[str]) -> str:
        value = match.group(0)
        digits = re.sub(r"\D", "", value)
        if _DATE.fullmatch(value) or not 8 <= len(digits) <= 15:
            return value
        return "[phone]"

    return _PHONE.sub(redact_phone, s)


EN_STOP = frozenset("""the and to of a an in for with we is are you on will be our this that it as at by or from your
need have has looking want should can must who what which their they i my me us if not but more all any also very than then so
into about using use able etc per each every over under new work project job please""".split())


def content_tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9][a-z0-9+#.]*", text.lower()) if t.strip(".") not in EN_STOP]


def norm_key(title: str, description: str) -> str:
    """Near-duplicate key: the SET of content words of the title + first 60 words of the description.
    Ignores punctuation, stop words, word order and repeats. Heuristic: two different posts with an identical
    bag of content words collide (documented limitation); true fuzzy dedupe (MinHash) is not implemented."""
    toks = sorted({t.strip(".") for t in content_tokens(title) + content_tokens(" ".join(description.split()[:60]))})
    return hashlib.sha1(" ".join(toks).encode()).hexdigest()


def looks_english(text: str, min_share: float = 0.12) -> bool:
    """Share of tokens that are very common English words; Spanish/German etc. score far lower. Cheap and imperfect."""
    toks = re.findall(r"[a-z']+", text.lower())
    return bool(toks) and sum(t in EN_STOP for t in toks) / len(toks) >= min_share


def parse_money(x) -> float | None:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        v = float(x)
    else:
        m = _MONEY.search(str(x).replace(" ", ""))
        if not m:
            return None
        try:
            v = float(m.group(0).replace(",", ""))
        except ValueError:
            return None
    return v if v > 0 and not math.isnan(v) else None


def ascii_ratio(s: str) -> float:
    return sum(c.isascii() for c in s) / len(s) if s else 0.0


def truthy(x) -> bool | None:
    s = str(x).strip().lower()
    if s in {"1", "true", "yes", "y", "hourly"}:
        return True
    if s in {"0", "false", "no", "n", "fixed", "fixed-price", "fixed price"}:
        return False
    return None
