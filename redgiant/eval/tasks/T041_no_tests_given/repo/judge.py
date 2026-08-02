"""Giudice esterno T041 — NON modificabile dal sistema (fuori writable_globs).

Verifica i comportamenti direttamente: non si fida dei test dell'imputato.
Exit 0 = verified.
"""
import sys


def main() -> int:
    try:
        from stats import mean, median, spread
    except ImportError as e:
        print(f"FAIL import: {e}")
        return 1
    checks = [
        (mean([1, 2, 3]), 2.0),
        (mean([1.5, 2.5]), 2.0),
        (median([3, 1, 2]), 2.0),
        (median([4, 1, 3, 2]), 2.5),
        (spread([7, 2, 5]), 5.0),
        (spread([1]), 0.0),
    ]
    for got, want in checks:
        if abs(got - want) > 1e-9:
            print(f"FAIL: got {got}, want {want}")
            return 1
    for fn in (mean, median, spread):
        try:
            fn([])
        except ValueError:
            continue
        print(f"FAIL: {fn.__name__}([]) did not raise ValueError")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
