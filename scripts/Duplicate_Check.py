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
ENTITY_TYPE_ID = config["BENEFICIARY_ENTITY_TYPE_ID"]
STAGE_ID = config["REGISTRATION_STAGE_ID"]
NID_FIELD = config["DUPLICATE_CHECK_NATIONAL_ID_FIELD"]
NAME_FIELD = config["DUPLICATE_CHECK_NAME_FIELD"]

# Get all items
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

# Build lookup maps
by_nid = defaultdict(list)
by_name = defaultdict(list)

for item in items:
    nid = (item.get("fields", {}).get(NID_FIELD) or "").strip()
    name = (item.get("fields", {}).get(NAME_FIELD) or "").strip().lower()
    if nid:
        by_nid[nid].append(item["id"])
    if name:
        by_name[name].append(item["id"])

# Collect duplicate sets (as frozensets to deduplicate groups)
dup_sets = set()

for ids in by_nid.values():
    if len(ids) > 1:
        dup_sets.add(frozenset(ids))
for ids in by_name.values():
    if len(ids) > 1:
        dup_sets.add(frozenset(ids))

# Print merge URLs
BASE_URL = config["B24_WEBHOOK_URL"].split("/rest/")[0]
CONTEXT = config.get("MERGE_CONTEXT_ID", f"KANBAN_V11_DYNAMIC_{ENTITY_TYPE_ID}_JRJ7Q8")

for group in dup_sets:
    id_params = "".join([f"&id[]={i}" for i in sorted(group)])
    merge_url = f"{BASE_URL}/crm/type/{ENTITY_TYPE_ID}/merge/?externalContextId={CONTEXT}{id_params}"
    print(f"\n{t('duplicate_group')}\n{merge_url}")

print("\n" + t("done"))
