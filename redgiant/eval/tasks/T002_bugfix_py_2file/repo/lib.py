def apply_discount(price, pct):
    """Return price after removing pct percent (pct is 0-100)."""
    return round(price * (1 - pct / 100), 2)
