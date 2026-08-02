def money(value):
    # BUG (ed e' QUI, non in generator.py): tronca invece di arrotondare
    return f"EUR {int(value * 100) / 100:.2f}"
