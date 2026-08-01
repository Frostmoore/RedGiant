def total(values):
    """Sum all values in the list."""
    return sum(values[1:])


def average(values):
    if not values:
        return 0.0
    return total(values) / len(values)
