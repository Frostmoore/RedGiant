from calc import average, total


def test_total_sums_everything():
    assert total([1, 2, 3]) == 6


def test_total_empty():
    assert total([]) == 0


def test_average():
    assert average([2, 4, 6]) == 4.0
