"""Giudice esterno T041 — NON modificabile dal sistema (fuori writable_globs).

Verifica i comportamenti direttamente: non si fida dei test dell'imputato.
Exit 0 = verified.
"""
import sys


def main() -> int:
    try:
        from stats import mean, median, spread
        from hist import histogram, normalize
        from summary import summarize
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
            print(f"FAIL stats: got {got}, want {want}")
            return 1
    for fn in (mean, median, spread):
        try:
            fn([])
        except ValueError:
            continue
        print(f"FAIL: {fn.__name__}([]) did not raise ValueError")
        return 1
    hist_checks = [
        (histogram([1, 2, 3, 4], 2), [2, 2]),
        (histogram([0, 5, 10], 2), [1, 2]),      # ultimo bin inclusivo
        (normalize([2, 2]), [0.5, 0.5]),
        (normalize([1, 3]), [0.25, 0.75]),
    ]
    for got, want in hist_checks:
        if got != want:
            print(f"FAIL hist: got {got}, want {want}")
            return 1
    for bad_call in (lambda: histogram([], 2), lambda: histogram([1], 0),
                     lambda: normalize([]), lambda: normalize([0, 0])):
        try:
            bad_call()
        except ValueError:
            continue
        print("FAIL hist: invalid input did not raise ValueError")
        return 1
    want = "n=3\nmean=2.00\nmedian=2.00\nspread=2.00"
    got = summarize([1, 2, 3])
    if got != want:
        print(f"FAIL summary: got {got!r}, want {want!r}")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
