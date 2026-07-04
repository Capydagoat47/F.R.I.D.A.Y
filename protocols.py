import json
from pathlib import Path

PROTOCOL_FILE = Path(__file__).with_name("protocols.json")

_current_protocol = "core"


def load_protocols():
    with open(PROTOCOL_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


PROTOCOLS = load_protocols()


def get_protocol(name: str):
    return PROTOCOLS.get(name.lower())


def get_all_protocols():
    return PROTOCOLS


def current_protocol():
    return _current_protocol


def set_protocol(name: str):
    global _current_protocol

    name = name.lower()

    if name not in PROTOCOLS:
        return False

    _current_protocol = name
    return True


def protocol_prompt():
    return PROTOCOLS[_current_protocol].get("prompt", "")


def protocol_status():
    return PROTOCOLS[_current_protocol].get("status", "")


def protocol_voice():
    return PROTOCOLS[_current_protocol].get("voice", "")


def protocol_colors():
    return PROTOCOLS[_current_protocol].get("colors", {})


def protocol_boot():
    return PROTOCOLS[_current_protocol].get("boot", [])


def protocol_name():
    return PROTOCOLS[_current_protocol].get("name", "Core")