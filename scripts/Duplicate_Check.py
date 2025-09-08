import requests
from config_loader import config
import io
import sys

# Ensure console prints in UTF-8 (especially for Windows)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Language setup
lang_arg = sys.argv[1] if len(sys.argv) > 1 else None
LANG = lang_arg or config.get("LANGUAGE", "en")

TRANSLATIONS = {
    "ky": {
        "🔍 Starting duplicate check...\n": "🔍 Дубликаттарды текшерүү башталды...\n",
        "📦 {n} total beneficiaries loaded.": "📦 Жалпы {n} жаран жүктөлдү.",
        "🎯 {n} items eligible for duplicate checking.\n": "🎯 {n} жаран дубликат текшерүүсүнө ылайыктуу.\n",
        "🔄 Checking item {i}/{total} (ID: {id})": "🔄 Текшерилип жатат {i}/{total} (ID: {id})",
        "✅ Updated {id} - {payload}": "✅ Жаңыртылды {id} - {payload}",
        "❌ Failed to update {id}: {msg}": "❌ Жаңыртуу ишке ашкан жок {id}: {msg}",
        "\n✅ Duplicate check complete. All matching records updated.\n": "\n✅ Текшерүү аяктады. Бардык дал келген жазуулар жаңыртылды.\n"
    },
    "ru": {
        "🔍 Starting duplicate check...\n": "🔍 Начата проверка на дубликаты...\n",
        "📦 {n} total beneficiaries loaded.": "📦 Всего загружено {n} бенефициаров.",
        "🎯 {n} items eligible for duplicate checking.\n": "🎯 {n} записей подлежат проверке на дубликаты.\n",
        "🔄 Checking item {i}/{total} (ID: {id})": "🔄 Проверяется {i}/{total} (ID: {id})",
        "✅ Updated {id} - {payload}": "✅ Обновлено {id} - {payload}",
        "❌ Failed to update {id}: {msg}": "❌ Ошибка обновления {id}: {msg}",
        "\n✅ Duplicate check complete. All matching records updated.\n": "\n✅ Проверка завершена. Все совпадающие записи обновлены.\n"
    }
}

def t(key, **kwargs):
    """Simple translation function."""
    return TRANSLATIONS.get(LANG, {}).get(key, key).format(**kwargs)


def fetch_all_beneficiaries():
    all_items = []
    start = 0

    while True:
        response = requests.get(
            f"{config['B24_WEBHOOK_URL']}/crm.item.list",
            params={
                "entityTypeId": config['BENEFICIARY_ENTITY_TYPE_ID'],
                "start": start
            }
        ).json()

        items = response.get("result", {}).get("items", [])
        all_items.extend(items)

        if "next" not in response.get("result", {}):
            break

        start = response["result"]["next"]

    return all_items


def update_beneficiary(item_id, payload):
    res = requests.post(
        f"{config['B24_WEBHOOK_URL']}/crm.item.update",
        params={
            "entityTypeId": config['BENEFICIARY_ENTITY_TYPE_ID'],
            "id": item_id,
        },
        json={"fields": payload}
    )

    if res.ok:
        print(t("✅ Updated {id} - {payload}", id=item_id, payload=payload))
    else:
        print(t("❌ Failed to update {id}: {msg}", id=item_id, msg=res.text))


def is_duplicate(item, all_items):
    national_id = item.get(config['DUPLICATE_CHECK_NATIONAL_ID_FIELD'])
    name = item.get(config['DUPLICATE_CHECK_NAME_FIELD'])
    reasons = []

    for other in all_items:
        if other["id"] == item["id"]:
            continue
        if other.get("stageId") != config['REGISTRATION_STAGE_ID']:
            continue

        if national_id and national_id == other.get(config['DUPLICATE_CHECK_NATIONAL_ID_FIELD']):
            reasons.append("Duplicate National ID")

        other_name = str(other.get(config['DUPLICATE_CHECK_NAME_FIELD'], "")).strip().lower()
        if name and name.strip().lower() == other_name:
            reasons.append("Duplicate Name")

    return ", ".join(set(reasons)) if reasons else None


def main():
    print(t("🔍 Starting duplicate check...\n"))
    all_items = fetch_all_beneficiaries()
    candidates = [
        item for item in all_items
        if item.get("stageId") == config['REGISTRATION_STAGE_ID'] and not item.get(config['DUPLICATE_FLAG_FIELD'])
    ]

    print(t("📦 {n} total beneficiaries loaded.", n=len(all_items)))
    print(t("🎯 {n} items eligible for duplicate checking.\n", n=len(candidates)))

    for i, item in enumerate(candidates, 1):
        print(t("🔄 Checking item {i}/{total} (ID: {id})", i=i, total=len(candidates), id=item['id']))
        reason = is_duplicate(item, all_items)
        payload = {
            config['DUPLICATE_FLAG_FIELD']: (
                config['DUPLICATE_FLAG_ENUM']["duplicate"] if reason else config['DUPLICATE_FLAG_ENUM']["unique"]
            ),
            config['DUPLICATE_REASON_FIELD']: reason or ""
        }
        update_beneficiary(item["id"], payload)

    print(t("\n✅ Duplicate check complete. All matching records updated.\n"))


if __name__ == "__main__":
    main()
