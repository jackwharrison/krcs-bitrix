import json
import os

def load_config():
    # Always resolve path relative to project root, not current working directory
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    path = os.path.join(base_dir, 'system_config.json')
    with open(path, encoding='utf-8') as f:
        return json.load(f)

config = load_config()
