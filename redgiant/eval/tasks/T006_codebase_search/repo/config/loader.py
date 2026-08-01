import json


def parse_config(path):
    """Load and validate the app configuration."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if "name" not in data:
        raise ValueError("missing 'name'")
    return data
