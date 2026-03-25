import requests
import sys
import io
import os
from collections import defaultdict
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config_loader import load_config

config = load_config()

# Force UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
lang = sys.argv[1] if len(sys.argv) > 1 else 'en'
LANG = lang

TRANSLATIONS = {
    'ky': {
        "Starting payment deduplication...": "Төлөмдөрдү кайталоодон тазалоо башталды...",
        "Fetched {n} records. Last ID: {last_id}. Total so far: {total}": "{n} жазуу жүктөлдү. Акыркы ID: {last_id}. Жалпы: {total}",
        "Loaded {n} payments total.": "Жалпы {n} төлөм жүктөлдү.",
        "Found {n} duplicate groups.": "{n} кайталанган топ табылды.",
        "Done. Found {count} duplicate groups.": "Аякталды. {count} кайталанган топ табылды.",
        "No duplicates found.": "Кайталануулар табылган жок."
    },
    'ru': {
        "Starting payment deduplication...": "Начата дедупликация платежей...",
        "Fetched {n} records. Last ID: {last_id}. Total so far: {total}": "Загружено {n} записей. Последний ID: {last_id}. Всего: {total}",
        "Loaded {n} payments total.": "Всего загружено {n} платежей.",
        "Found {n} duplicate groups.": "Найдено {n} групп дубликатов.",
        "Done. Found {count} duplicate groups.": "Готово. Найдено {count} групп дубликатов.",
        "No duplicates found.": "Дубликаты не найдены."
    }
}

def t(key, **kwargs):
    translation = TRANSLATIONS.get(LANG, {}).get(key, key)
    return translation.format(**kwargs) if kwargs else translation


def fetch_all_payments():
    """Fetch all payment records from Bitrix24."""
    all_items = []
    last_id = 0

    while True:
        response = requests.post(
            f"{config['B24_WEBHOOK_URL']}/crm.item.list",
            json={
                "entityTypeId": config['PAYMENT_ENTITY_TYPE_ID'],
                "order": {"id": "ASC"},
                "filter": {">id": last_id},
                "start": 0
            }
        ).json()

        batch = response.get("result", {}).get("items", [])
        if not batch:
            break

        all_items.extend(batch)
        last_id = batch[-1]["id"]
        print(f"📄 {t('Fetched {n} records. Last ID: {last_id}. Total so far: {total}', n=len(batch), last_id=last_id, total=len(all_items))}")

        if len(batch) < 50:
            break

    return all_items


def build_merge_url(ids):
    base = config["B24_WEBHOOK_URL"].split("/rest/")[0]
    entity_type_id = config["PAYMENT_ENTITY_TYPE_ID"]
    context = config.get("PAYMENT_MERGE_CONTEXT_ID", f"KANBAN_V11_DYNAMIC_{entity_type_id}_JRJ7Q8")
    id_params = "".join([f"&id[]={i}" for i in sorted(ids)])
    return f"{base}/crm/type/{entity_type_id}/merge/?externalContextId={context}{id_params}"


def find_duplicate_groups(all_items):
    """Group payments by national ID + project type, return groups with more than one record."""
    groups = defaultdict(list)

    for item in all_items:
        national_id = item.get(config['NATIONAL_ID_FIELD'])
        project_type = item.get(config['PROJECT_TYPE_FIELD'])

        if not national_id or not project_type:
            continue

        key = (str(national_id).strip(), str(project_type).strip())
        groups[key].append(item["id"])

    return {key: ids for key, ids in groups.items() if len(ids) > 1}


def main():
    print(f"🔍 {t('Starting payment deduplication...')}\n")
    all_items = fetch_all_payments()
    print(f"📦 {t('Loaded {n} payments total.', n=len(all_items))}")

    duplicate_groups = find_duplicate_groups(all_items)
    print(f"⚠️ {t('Found {n} duplicate groups.', n=len(duplicate_groups))}\n")

    if not duplicate_groups:
        print(f"✅ {t('No duplicates found.')}")
        return

    printed = set()
    for (national_id, project_type), ids in duplicate_groups.items():
        group = frozenset(ids)
        if group in printed:
            continue
        printed.add(group)
        url = build_merge_url(ids)
        print(f"⚠️ Duplicate payments for ID {national_id} / {project_type}: {ids}")
        print(f"🔗 {url}")

    print(f"\n✅ {t('Done. Found {count} duplicate groups.', count=len(duplicate_groups))}")


if __name__ == "__main__":
    main()
