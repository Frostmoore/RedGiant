from config.loader import parse_config


def boot():
    cfg = parse_config("app.json")
    print(f"booting {cfg['name']}")
