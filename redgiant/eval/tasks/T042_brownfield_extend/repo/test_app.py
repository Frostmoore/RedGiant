from app import dispatch


def _seed():
    notes = []
    dispatch(notes, "add", ["Spesa", "latte e pane"])
    dispatch(notes, "add", ["Idee", "regalo per L."])
    dispatch(notes, "add", ["Spesa 2", "uova"])
    return notes


def test_add_and_list():
    notes = _seed()
    titles = dispatch(notes, "list", [])
    assert len(titles) == 3 and titles[0] == "1: Spesa"


def test_search():
    notes = _seed()
    hits = dispatch(notes, "search", ["spesa"])
    assert [n["id"] for n in hits] == [1, 3]


def test_delete():
    notes = _seed()
    assert dispatch(notes, "delete", ["2"]) is True
    assert len(notes) == 2
    assert dispatch(notes, "delete", ["99"]) is False
