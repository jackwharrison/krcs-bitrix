import sys
import requests
from collections import defaultdict
from config_loader import load_config

# Load configuration
config = load_config()
LANGUAGE = sys.argv[1] if len(sys.argv) > 1 else config.get("LANGUAGE", "en")

# Localized strings
STRINGS = {
    "checking_duplicates": {
        "en": "Checking for duplicates...",
        "ru": "Проверка на дубликаты...",
        "ky": "Кайталанган жазууларды текшерүү..."
    },
    "duplicate_group": {
        "en": "Duplicate group detected:",
        "ru": "Обнаружена группа дубликатов:",
        "ky": "Кайталанган жазуулар тобу табылды:"
    },
    "done": {
        "en": "Duplicate check completed.",
        "ru": "Проверка на дубликаты завершена.",
        "ky": "Кайталанган жазууларды текшерүү аяктады."
    }
}

def t(key):
    return STRINGS[key].get(LANGUAGE, STRINGS[key]["en"])

print(t("checking_duplicates"))

# Config values
URL = config["B24_WEBHOOK_URL"]
ENTITY_TYPE_ID = config["CHILD_ENTITY_TYPE_ID"]
STAGE_ID = config["CHILD_STAGE_ID"]
NID_FIELD = config["CHILD_NID_FIELD"]
NAME_FIELD = config["CHILD_NAME_FIELD"]
PARENT_FIELD = config["CHILD_PARENT_FIELD"]

# Get all child items
def fetch_all_items():
    all_items = []
    start = 0
    while True:
        res = requests.post(URL + "/crm.item.list", json={
            "entityTypeId": ENTITY_TYPE_ID,
            "filter": {"stageId": STAGE_ID},
            "start": start
        })
        res.raise_for_status()
        data = res.json()
        all_items.extend(data["result"]["items"])
        if "next" not in data["result"]:
            break
        start = data["result"]["next"]
    return all_items

items = fetch_all_items()

# Build grouped duplicates
dups = defaultdict(list)

for item in items:
    name = (item.get("fields", {}).get(NAME_FIELD) or "").strip().lower()
    nid = (item.get("fields", {}).get(NID_FIELD) or "").strip()
    parent = item.get("fields", {}).get(PARENT_FIELD)
    key = (name, nid, parent)
    if name and nid and parent:
        dups[key].append(item["id"])

# Set for deduplicated sets
dup_sets = set()

for ids in dups.values():
    if len(ids) > 1:
        dup_sets.add(frozenset(ids))

# Print merge links
BASE_URL = config["B24_WEBHOOK_URL"].split("/rest/")[0]
CONTEXT = config.get("CHILD_MERGE_CONTEXT_ID", f"KANBAN_V11_DYNAMIC_{ENTITY_TYPE_ID}_JRJ7Q8")

printed = set()

for group in dup_sets:
    ids = sorted(group)
    group_key = tuple(ids)
    if group_key in printed:
        continue
    printed.add(group_key)
    id_params = "".join([f"&id[]={i}" for i in ids])
    merge_url = f"{BASE_URL}/crm/type/{ENTITY_TYPE_ID}/merge/?externalContextId={CONTEXT}{id_params}"
    print(f"🔗 {merge_url}")

print("\n" + t("done"))
