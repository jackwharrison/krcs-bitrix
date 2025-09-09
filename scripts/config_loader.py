import os
import json
import pathlib

# Optional: set this in Render to redirect config file to persistent disk
CONFIG_DIR = os.getenv("CONFIG_DIR", ".")
CONFIG_PATH = os.path.join(CONFIG_DIR, "system_config.json")
DEFAULT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "system_config.default.json"))


def load_config():
    if not os.path.exists(CONFIG_PATH):
        if os.path.exists(DEFAULT_PATH):
            print(f"[config_loader] Bootstrapping config from default at {DEFAULT_PATH}")
            with open(DEFAULT_PATH, 'r', encoding='utf-8') as f:
                default_config = json.load(f)
            save_config(default_config)
        else:
            raise FileNotFoundError(f"Missing both {CONFIG_PATH} and {DEFAULT_PATH}")

    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # Override the sensitive webhook field
    secret = os.getenv("B24_WEBHOOK_URL")
    if not secret:
        raise RuntimeError("Missing environment variable: B24_WEBHOOK_URL")
    config["B24_WEBHOOK_URL"] = secret

    return config

def save_config(data):
    # Never persist the secret value to disk
    data = dict(data)
    data.pop("B24_WEBHOOK_URL", None)

    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
