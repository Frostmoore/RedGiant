import re


def slugify(text):
    """Lowercase, replace runs of non-alphanumerics with single hyphens."""
    text = text.lower().strip()
    # BUG: spaces are removed instead of hyphenated; other separators work
    text = text.replace(" ", "")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def truncate(text, n):
    if len(text) <= n:
        return text
    return text[: n - 1] + "…"


def initials(name):
    return "".join(w[0].upper() for w in name.split() if w)
