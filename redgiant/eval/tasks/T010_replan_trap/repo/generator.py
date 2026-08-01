"""Genera il report. NOTA: questo modulo e' corretto — il prompt del task
punta qui, ma la verita' sta nei test."""

from formatter import money


def report(items):
    total = sum(v for _, v in items)
    lines = [f"{name}: {money(value)}" for name, value in items]
    lines.append(f"TOTAL: {money(total)}")
    return "\n".join(lines)
