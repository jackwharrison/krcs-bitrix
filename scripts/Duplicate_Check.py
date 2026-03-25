import sys
import io
import requests
from collections import defaultdict
from config_loader import load_config

# Load configuration
config = load_config()
LANGUAGE = sys.argv[1] if len(sys.argv) > 1 else config.get("LANGUAGE", "en")

# Ensure UTF-8 output in terminal
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Localized strings
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
    return TRANSLATIONS.get(LANGUAGE, {}).get(key, key).format(**kwargs)

def fetch_all_beneficiaries():
    all_items = []
    last_id = 0
    while True:
        raw = requests.post(
            f"{config['B24_WEBHOOK_URL']}/crm.item.list",
            json={
                "entityTypeId": config['BENEFICIARY_ENTITY_TYPE_ID'],
                "order": {"id": "ASC"},
                "filter": {">id": last_id},
                "start": 0
            }
        )
        if not raw.ok:
            raise RuntimeError(f"API request failed (HTTP {raw.status_code}): {raw.text[:500]}")
        if not raw.text.strip():
            raise RuntimeError(
                f"API returned an empty response. "
                f"Check that B24_WEBHOOK_URL is correct and BENEFICIARY_ENTITY_TYPE_ID={config['BENEFICIARY_ENTITY_TYPE_ID']} is valid."
            )
        try:
            response = raw.json()
        except Exception:
            raise RuntimeError(f"API returned non-JSON response: {raw.text[:500]}")

        if "error" in response:
            raise RuntimeError(f"Bitrix24 API error: {response['error']} — {response.get('error_description', '')}")

        batch = response.get("result", {}).get("items", [])
        if not batch:
            break

        all_items.extend(batch)
        last_id = batch[-1]["id"]
        print(f"📄 Fetched {len(batch)} records. Last ID: {last_id}. Total so far: {len(all_items)}")

        if len(batch) < 50:
            break

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

def build_merge_url(ids):
    base = config["B24_WEBHOOK_URL"].split("/rest/")[0]
    entity_type_id = config["BENEFICIARY_ENTITY_TYPE_ID"]
    context = config.get("MERGE_CONTEXT_ID", f"KANBAN_V11_DYNAMIC_{entity_type_id}_JRJ7Q8")
    id_params = "".join([f"&id[]={i}" for i in sorted(ids)])
    return f"{base}/crm/type/{entity_type_id}/merge/?externalContextId={context}{id_params}"

def main():
    print(t("🔍 Starting duplicate check...\n"))
    all_items = fetch_all_beneficiaries()
    candidates = [
        item for item in all_items
        if item.get("stageId") == config['REGISTRATION_STAGE_ID'] and not item.get(config['DUPLICATE_FLAG_FIELD'])
    ]
    print(t("📦 {n} total beneficiaries loaded.", n=len(all_items)))
    print(t("🎯 {n} items eligible for duplicate checking.\n", n=len(candidates)))

    # Track duplicates for merging
    nid_groups = defaultdict(list)
    name_groups = defaultdict(list)

    for item in all_items:
        if item.get("stageId") != config['REGISTRATION_STAGE_ID']:
            continue
        nid = item.get(config['DUPLICATE_CHECK_NATIONAL_ID_FIELD'])
        name = str(item.get(config['DUPLICATE_CHECK_NAME_FIELD'], "")).strip().lower()
        if nid:
            nid_groups[nid].append(item["id"])
        if name:
            name_groups[name].append(item["id"])

    printed_groups = set()

    for i, item in enumerate(candidates, 1):
        print(t("🔄 Checking item {i}/{total} (ID: {id})", i=i, total=len(candidates), id=item['id']))
        reason = is_duplicate(item, all_items)
        payload = {
            config['DUPLICATE_FLAG_FIELD']: "Duplicate" if reason else "Unique",
            config['DUPLICATE_REASON_FIELD']: reason or ""
        }

        update_beneficiary(item["id"], payload)

        # Print merge URL if duplicate
        if reason:
            nid = item.get(config['DUPLICATE_CHECK_NATIONAL_ID_FIELD'])
            name = str(item.get(config['DUPLICATE_CHECK_NAME_FIELD'], "")).strip().lower()
            ids = []
            if nid and len(nid_groups[nid]) > 1:
                ids = nid_groups[nid]
            elif name and len(name_groups[name]) > 1:
                ids = name_groups[name]
            if ids:
                group = frozenset(ids)
                if group not in printed_groups:
                    printed_groups.add(group)
                    url = build_merge_url(ids)
                    print(f"🔗 {url}")

    print(t("\n✅ Duplicate check complete. All matching records updated.\n"))

if __name__ == "__main__":
    main()
