import requests
import sys
import io
import time
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config_loader import load_config

config = load_config()

# Force UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
lang = sys.argv[1] if len(sys.argv) > 1 else 'en'
# Simple language switcher (uses app.py-style structure)
LANG = lang  # use the command-line language argument passed from app.py

TRANSLATIONS = {
    'ky': {
        "Starting payment deduplication...": "Төлөмдөрдү кайталоодон тазалоо башталды...",
        "Deleted duplicate payment ID": "Кайталап киргизилген төлөм өчүрүлдү. ID",
        "Failed to delete payment ID": "Төлөмдү өчүрүү ишке ашкан жок. ID",
        "Done. Deleted {count} duplicates: {ids}": "Аякталды. {count} кайталоо өчүрүлдү: {ids}"
    },
    'ru': {
        "Starting payment deduplication...": "Начато удаление дублирующихся платежей...",
        "Deleted duplicate payment ID": "Удалён дублирующийся платёж ID",
        "Failed to delete payment ID": "Не удалось удалить платёж ID",
        "Done. Deleted {count} duplicates: {ids}": "Готово. Удалено {count} дубликатов: {ids}"
    }
}

def t(key, **kwargs):
    """Translation wrapper."""
    translation = TRANSLATIONS.get(LANG, {}).get(key, key)
    return translation.format(**kwargs) if kwargs else translation


def fetch_all_payments():
    """Fetch all payment records from Bitrix24."""
    all_items = []
    start = 0

    while True:
        response = requests.get(
            f"{config['B24_WEBHOOK_URL']}/crm.item.list",
            params={
                "entityTypeId": config['PAYMENT_ENTITY_TYPE_ID'],
                "start": start
            }
        ).json()

        items = response.get("result", {}).get("items", [])
        all_items.extend(items)

        if "next" not in response.get("result", {}):
            break

        start = response["result"]["next"]

    return all_items


def delete_payment(item_id):
    """Delete a payment record from Bitrix24."""
    response = requests.post(
        f"{config['B24_WEBHOOK_URL']}/crm.item.delete",
        params={
            "entityTypeId": config['PAYMENT_ENTITY_TYPE_ID'],
            "id": item_id,
        }
    )
    return response.ok


def dedupe_payments(all_items):
    """Deduplicate payments based on National ID + Project Type."""
    seen = {}
    deleted = []

    for item in all_items:
        national_id = item.get(config['NATIONAL_ID_FIELD'])
        project_type = item.get(config['PROJECT_TYPE_FIELD'])

        if not national_id or not project_type:
            continue

        key = (str(national_id).strip(), str(project_type).strip())

        if key in seen:
            if delete_payment(item["id"]):
                deleted.append(item["id"])
                print(f"🗑️ {t('Deleted duplicate payment ID')} {item['id']}")
            else:
                print(f"❌ {t('Failed to delete payment ID')} {item['id']}")
        else:
            seen[key] = item["id"]

    return deleted


def main():
    print(f"🔍 {t('Starting payment deduplication...')}\n")
    all_items = fetch_all_payments()
    deleted = dedupe_payments(all_items)
    print(f"\n✅ {t('Done. Deleted {count} duplicates: {ids}', count=len(deleted), ids=deleted)}")


if __name__ == "__main__":
    main()
