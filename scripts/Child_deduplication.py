import requests
import json
import io
import sys
import os
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Load config from system_config.json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config_loader import load_config

config = load_config()
# Dynamic parent field
PARENT_FIELD = f"parentId{config['BENEFICIARY_ENTITY_TYPE_ID']}"

# Optional: set this to 'en', 'ru', or 'ky' later when integrating
lang = sys.argv[1] if len(sys.argv) > 1 else 'en'


# Optional translations (expand as needed)
translations = {
    'Fetching all children...': {
        'ru': 'Получение всех детей...',
        'ky': 'Бардык балдарды жүктөө...'
    },
    'Found {n} beneficiaries with children.': {
        'ru': 'Найдено {n} бенефициаров с детьми.',
        'ky': '{n} балалу бенефициар табылды.'
    },
    'Detecting duplicates by child name + DoB...': {
        'ru': 'Поиск дубликатов по имени ребенка и дате рождения...',
        'ky': 'Бала аты жана туулган датасы боюнча көчүрмөлөрдү издөө...'
    },
    'Found {n} potential duplicates.': {
        'ru': 'Найдено {n} возможных дубликатов.',
        'ky': '{n} мүмкүн болгон көчүрмө табылды.'
    },
    'Fetching all beneficiaries...': {
        'ru': 'Загрузка всех бенефициаров...',
        'ky': 'Бардык бенефициарларды жүктөө...'
    },
    'Duplicate household warning: {name} → matches with: {others}': {
        'ru': '⚠️ Предупреждение о дублирующемся домохозяйстве: {name} → совпадает с: {others}',
        'ky': '⚠️ Кайталанган үй-бүлө: {name} → окшош: {others}'
    },
    'Failed to update {name}': {
        'ru': '❌ Ошибка обновления: {name}',
        'ky': '❌ Жаңыртуу ишке ашкан жок: {name}'
    }
}

def t(message_key, **kwargs):
    """Translate message with fallback."""
    template = translations.get(message_key, {}).get(lang, message_key)
    return template.format(**kwargs)

def print_message(icon, message_key, **kwargs):
    """Print with emoji icon and translated message."""
    print(f"{icon} {t(message_key, **kwargs)}")

def fetch_all_children():
    items = []
    start = 0
    while True:
        res = requests.get(
            f"{config['B24_WEBHOOK_URL']}/crm.item.list",
            params={"entityTypeId": config["CHILD_ENTITY_TYPE_ID"], "start": start}
        ).json()
        batch = res.get("result", {}).get("items", [])
        items.extend(batch)
        if "next" not in res.get("result", {}):
            break
        start = res["result"]["next"]
    return items

def fetch_all_beneficiaries():
    items = []
    start = 0
    while True:
        res = requests.get(
            f"{config['B24_WEBHOOK_URL']}/crm.item.list",
            params={"entityTypeId": config["BENEFICIARY_ENTITY_TYPE_ID"], "start": start}
        ).json()
        batch = res.get("result", {}).get("items", [])
        items.extend(batch)
        if "next" not in res.get("result", {}):
            break
        start = res["result"]["next"]
    return items

def update_beneficiary(ben_id, fields):
    payload = {
        "entityTypeId": config["BENEFICIARY_ENTITY_TYPE_ID"],
        "id": ben_id,
        "fields": fields
    }
    res = requests.post(f"{config['B24_WEBHOOK_URL']}/crm.item.update", json=payload)
    return res.ok

def normalize_children(children):
    norm = []
    for child in children:
        name = str(child.get("title", "")).strip().lower()
        dob = str(child.get(config["CHILD_DOB_FIELD"], "")).strip()
        norm.append((name, dob))
    return sorted(norm)

def main():
    print_message("👶", "Fetching all children...")
    children = fetch_all_children()

    grouped_children = defaultdict(list)
    for child in children:
        parent_id = child.get(PARENT_FIELD)
        if parent_id:
            grouped_children[parent_id].append(child)

    print_message("👥", "Found {n} beneficiaries with children.", n=len(grouped_children))

    # Create signature per parent
    signature_to_parents = defaultdict(list)
    for parent_id, child_list in grouped_children.items():
        signature = json.dumps(normalize_children(child_list))
        signature_to_parents[signature].append(parent_id)

    print_message("🔍", "Detecting duplicates by child name + DoB...")

    duplicate_map = {}
    for parent_ids in signature_to_parents.values():
        if len(parent_ids) > 1:
            for pid in parent_ids:
                others = [i for i in parent_ids if i != pid]
                duplicate_map[pid] = {
                    "flag": config["CHILD_DEDUPLICATION_ENUM"]["potential_duplicate"],
                    "duplicate_of": others
                }
        else:
            pid = parent_ids[0]
            duplicate_map[pid] = {
                "flag": config["CHILD_DEDUPLICATION_ENUM"]["unique"],
                "duplicate_of": []
            }

    potential_count = sum(1 for v in duplicate_map.values() if v['flag'] == config['CHILD_DEDUPLICATION_ENUM']['potential_duplicate'])
    print_message("⚠️", "Found {n} potential duplicates.", n=potential_count)

    print_message("📦", "Fetching all beneficiaries...")
    all_beneficiaries = fetch_all_beneficiaries()
    ben_lookup = {ben["id"]: ben for ben in all_beneficiaries}

    for ben_id, result in duplicate_map.items():
        ben = ben_lookup.get(ben_id)
        if not ben:
            continue

        if ben.get("stageId") != config["VERIFIED_STAGE_ID"]:
            continue

        other_names = [
            ben_lookup[i].get("title", "").strip()
            for i in result["duplicate_of"]
            if i in ben_lookup and ben_lookup[i].get("stageId") != config["REGISTRATION_STAGE_ID"]
        ]

        other_name_str = ", ".join(other_names)
        ben_name = ben.get("title", f"{ben_id}")

        fields_to_update = {
            config["CHILD_DEDUPLICATION_FIELD"]: result["flag"],
            config["CHILD_DUPLICATE_NAME_FIELD"]: other_name_str
        }

        success = update_beneficiary(ben_id, fields_to_update)
        if success and result["flag"] == config["CHILD_DEDUPLICATION_ENUM"]["potential_duplicate"]:
            print_message("⚠️", "Duplicate household warning: {name} → matches with: {others}", name=ben_name, others=other_name_str)
        elif not success:
            print_message("❌", "Failed to update {name}", name=ben_name)

if __name__ == "__main__":
    main()
