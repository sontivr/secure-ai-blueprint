import re

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"\b(?:\+?1[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}\b")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CARD_CANDIDATE_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")


def _luhn_check(number: str) -> bool:
    digits = [int(d) for d in number if d.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False

    total = 0
    parity = len(digits) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _replace_cards(text: str) -> str:
    def repl(match: re.Match) -> str:
        candidate = match.group(0)
        digits_only = "".join(ch for ch in candidate if ch.isdigit())
        if _luhn_check(digits_only):
            return "[REDACTED_CARD]"
        return candidate

    return CARD_CANDIDATE_RE.sub(repl, text)


def redact_pii(text: str) -> str:
    if not text:
        return text

    text = EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    text = PHONE_RE.sub("[REDACTED_PHONE]", text)
    text = SSN_RE.sub("[REDACTED_SSN]", text)
    text = _replace_cards(text)

    return text