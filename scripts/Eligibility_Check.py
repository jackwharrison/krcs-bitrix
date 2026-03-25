import requests
from collections import defaultdict
import json
import io
import sys
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Load config from system_config.json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config_loader import load_config

config = load_config()
# ---- Language + translations ----
# Read language from argv (fallback to English)
lang = sys.argv[1] if len(sys.argv) > 1 else 'en'

translations = {
    # Searching / loading
    "\n🔎 Searching for projects in selection stage": {
        "ru": "\n🔎 Поиск проектов на стадии отбора",
        "ky": "\n🔎 Тандоо баскычындагы долбоорлорду издөө"
    },
    "📦 Found {n} project(s).\n": {
        "ru": "📦 Найдено проектов: {n}.\n",
        "ky": "📦 Табылган долбоорлор: {n}.\n"
    },
    "👥 Loaded {n} beneficiaries total.": {
        "ru": "👥 Загружено бенефициаров всего: {n}.",
        "ky": "👥 Жүктөлгөн бенефициарлар: {n}."
    },
    "✅ Filtered to {n} eligible-stage beneficiaries.\n": {
        "ru": "✅ Отфильтровано до бенефициаров на целевых стадиях: {n}.\n",
        "ky": "✅ Максаттуу стадиядагы бенефициарлар: {n}.\n"
    },

    # Per project
    "📄 Processing project {id}: {title}": {
        "ru": "📄 Обработка проекта {id}: {title}",
        "ky": "📄 Долбоор иштетилүүдө {id}: {title}"
    },
    "🎯 Found {n} eligible beneficiaries\n": {
        "ru": "🎯 Найдено подходящих бенефициаров: {n}\n",
        "ky": "🎯 Туура келген бенефициарлар: {n}\n"
    },

    # Updates
    "✅ Updated beneficiary {id}{stage_note} ({n} programs)": {
        "ru": "✅ Бенефициар {id} жаңыртылды{stage_note} ({n} программ)",
        "ky": "✅ Бенефициар {id} жаңыртылды{stage_note} ({n} программа)"
    },
    "🧹 Cleared beneficiary {id}{stage_note} (0 programs)": {
        "ru": "🧹 Бенефициар {id} тазаланды{stage_note} (0 программ)",
        "ky": "🧹 Бенефициар {id} тазаланды{stage_note} (0 программа)"
    },
    " (moved to VERIFIED)": {
        "ru": " (переведён в VERIFIED)",
        "ky": " (VERIFIED стадиясына кайтарылды)"
    },
    "❌ Failed to update beneficiary {id}: {error}": {
        "ru": "❌ Не удалось обновить бенефициара {id}: {error}",
        "ky": "❌ Бенефициар {id} жаңыртылган жок: {error}"
    }
}

def t(msg_key, **kwargs):
    """Translate with fallback to English string (the key itself)."""
    template = translations.get(msg_key, {}).get(lang, msg_key)
    try:
        return template.format(**kwargs)
    except Exception:
        # In case placeholders don't line up for some reason
        return template

# ---- Existing helpers (unchanged logic) ----

def fetch_field_labels(entity_type_id):
    url = f"{config['B24_WEBHOOK_URL']}/crm.item.fields"
    res = requests.get(url, params={"entityTypeId": entity_type_id}).json()
    if "result" not in res:
        raise Exception(f"Error fetching fields: {res}")

    labels = {}
    for field_code, field_info in res["result"]["fields"].items():
        if field_info.get("type") == "enumeration":
            items = field_info.get("items", [])
            if isinstance(items, dict):
                labels[field_code] = items
            elif isinstance(items, list):
                labels[field_code] = {i["ID"]: i["VALUE"] for i in items}
    return labels

def fetch_all_items(entity_type_id):
    items = []
    last_id = 0
    while True:
        res = requests.post(
            f"{config['B24_WEBHOOK_URL']}/crm.item.list",
            json={
                "entityTypeId": entity_type_id,
                "order": {"id": "ASC"},
                "filter": {">id": last_id},
                "start": 0
            }
        ).json()

        batch = res.get("result", {}).get("items", [])
        if not batch:
            break

        items.extend(batch)
        last_id = batch[-1]["id"]
        print(f"📄 Fetched {len(batch)} records. Last ID: {last_id}. Total so far: {len(items)}")

        if len(batch) < 50:
            break

    return items

def fetch_projects_by_stage(stage_id):
    project_fields = [f["project_field"] for f in config["MATCHING_FIELDS"]]
    select_fields = ["id", "title"] + project_fields

    projects = []
    last_id = 0
    while True:
        res = requests.post(
            f"{config['B24_WEBHOOK_URL']}/crm.item.list",
            json={
                "entityTypeId": config["PROJECT_ENTITY_TYPE_ID"],
                "order": {"id": "ASC"},
                "filter": {
                    "stageId": stage_id,
                    ">id": last_id
                },
                "select": select_fields,
                "start": 0
            }
        ).json()

        batch = res.get("result", {}).get("items", [])
        if not batch:
            break

        projects.extend(batch)
        last_id = batch[-1]["id"]

        if len(batch) < 50:
            break

    return projects

def get_matching_beneficiaries(project, beneficiaries, matching_fields, field_labels):
    matches = []

    for ben in beneficiaries:
        match = True
        for field_map in matching_fields:
            ben_field = field_map["beneficiary_field"]
            proj_field = field_map["project_field"]

            ben_val = str(ben.get(ben_field, ""))
            proj_val = str(project.get(proj_field, ""))

            ben_label = field_labels.get(ben_field, {}).get(ben_val, "").strip().lower()
            proj_label = field_labels.get(proj_field, {}).get(proj_val, "").strip().lower()

            if proj_label == "yes" and ben_label != "yes":
                match = False
                break

        if match:
            matches.append(ben)

    return matches

def update_beneficiary(ben, is_eligible, project_names=None):
    ben_id = ben["id"]
    fields = {
        config["ELIGIBILITY_FIELD_ID"]: 'Y' if is_eligible else 'N',
        config["PROGRAM_COUNT_FIELD_ID"]: len(project_names) if is_eligible else 0,
        config["PROGRAM_NAMES_FIELD_ID"]: ", ".join(project_names) if is_eligible else ""
    }

    # Move back to VERIFIED_STAGE_ID if they are currently in ELIGIBLE_STAGE_ID but are not eligible
    moved_back = False
    if not is_eligible and ben.get("stageId") == config["ELIGIBLE_STAGE_ID"]:
        fields["stageId"] = config["VERIFIED_STAGE_ID"]
        moved_back = True

    url = f"{config['B24_WEBHOOK_URL']}/crm.item.update"
    payload = {
        "entityTypeId": config["BENEFICIARY_ENTITY_TYPE_ID"],
        "id": ben_id,
        "fields": fields
    }

    response = requests.post(url, json=payload)
    result = response.json()

    if response.ok and "result" in result:
        stage_note = t(" (moved to VERIFIED)") if moved_back else ""
        if is_eligible:
            print(t("✅ Updated beneficiary {id}{stage_note} ({n} programs)",
                    id=ben_id, stage_note=stage_note, n=len(project_names) if project_names else 0))
        else:
            print(t("🧹 Cleared beneficiary {id}{stage_note} (0 programs)",
                    id=ben_id, stage_note=stage_note))
    else:
        print(t("❌ Failed to update beneficiary {id}: {error}",
                id=ben_id, error=result))

def main():
    print(t("\n🔎 Searching for projects in selection stage"))
    projects = fetch_projects_by_stage(config["STAGE_ID"])
    print(t("📦 Found {n} project(s).\n", n=len(projects)))

    beneficiaries_all = fetch_all_items(config["BENEFICIARY_ENTITY_TYPE_ID"])
    print(t("👥 Loaded {n} beneficiaries total.", n=len(beneficiaries_all)))

    # 🔍 Filter beneficiaries by stageId
    valid_stages = [config["ELIGIBLE_STAGE_ID"], config["VERIFIED_STAGE_ID"]]
    beneficiaries = [
        ben for ben in beneficiaries_all
        if ben.get("stageId") in valid_stages
    ]
    print(t("✅ Filtered to {n} eligible-stage beneficiaries.\n", n=len(beneficiaries)))

    project_labels = fetch_field_labels(config["PROJECT_ENTITY_TYPE_ID"])
    ben_labels = fetch_field_labels(config["BENEFICIARY_ENTITY_TYPE_ID"])
    field_labels = {**project_labels, **ben_labels}

    eligible_map = defaultdict(list)

    for project in projects:
        title = project.get("title", f"Project {project['id']}")
        print(t("📄 Processing project {id}: {title}", id=project["id"], title=title))

        matched_beneficiaries = get_matching_beneficiaries(
            project, beneficiaries, config["MATCHING_FIELDS"], field_labels
        )

        print(t("🎯 Found {n} eligible beneficiaries\n", n=len(matched_beneficiaries)))
        for ben in matched_beneficiaries:
            eligible_map[ben["id"]].append(title)

    for ben in beneficiaries:
        ben_id = ben["id"]
        if ben_id in eligible_map:
            update_beneficiary(ben, True, eligible_map[ben_id])
        else:
            update_beneficiary(ben, False)

if __name__ == "__main__":
    main()
