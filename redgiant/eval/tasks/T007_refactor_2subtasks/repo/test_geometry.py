import math

from geometry import circle_area, circle_perimeter, square_area


def test_circle_area():
    assert abs(circle_area(2) - 4 * math.pi) < 1e-9


def test_circle_perimeter():
    assert abs(circle_perimeter(1) - 2 * math.pi) < 1e-9


def test_square():
    assert square_area(3) == 9


def test_circle_module_exists():
    from circle import circle_area as ca, circle_perimeter as cp
    assert ca(1) == circle_area(1)
    assert cp(1) == circle_perimeter(1)


def test_geometry_delegates_to_circle():
    import inspect

    import geometry
    src = inspect.getsource(geometry)
    assert "from circle import" in src or "import circle" in src
