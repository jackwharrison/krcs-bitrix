import requests
import time
import io
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config_loader import load_config
config = load_config()

# Ensure UTF-8 output (important on Windows)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Language setup
lang_arg = sys.argv[1] if len(sys.argv) > 1 else None
LANG = lang_arg or config.get("LANGUAGE", "en")

TRANSLATIONS = {
    "ky": {
        "🔍 Fetching all completed beneficiaries...": "🔍 Бардык аяктаган жарандар жүктөлүүдө...",
        "👥 Found {n} in completed stage.\n": "👥 Аяктаган стадияда {n} жаран табылды.\n",
        "✅ Updated beneficiary {id}": "✅ Жаран жаңыртылды {id}",
        "❌ Error updating {id}: {msg}": "❌ Жаңыртуу катасы {id}: {msg}",
        "⏩ Skipping {id}, no linked project.": "⏩ Өткөрүлдү {id}, байланышкан долбоор жок.",
        "⚠️ Could not fetch project title for {id}": "⚠️ Долбоордун аталышы табылган жок {id}"
    },
    "ru": {
        "🔍 Fetching all completed beneficiaries...": "🔍 Получение всех завершённых бенефициаров...",
        "👥 Found {n} in completed stage.\n": "👥 Найдено {n} в стадии 'Завершено'.\n",
        "✅ Updated beneficiary {id}": "✅ Бенефициар обновлён {id}",
        "❌ Error updating {id}: {msg}": "❌ Ошибка при обновлении {id}: {msg}",
        "⏩ Skipping {id}, no linked project.": "⏩ Пропущено {id}, нет связанного проекта.",
        "⚠️ Could not fetch project title for {id}": "⚠️ Не удалось получить название проекта для {id}"
    }
}

def t(key, **kwargs):
    """Simple translation helper."""
    return TRANSLATIONS.get(LANG, {}).get(key, key).format(**kwargs)


def get_project_name(project_id):
    url = f"{config['B24_WEBHOOK_URL']}/crm.item.get"
    res = requests.get(url, params={
        "entityTypeId": config['PROJECT_ENTITY_TYPE_ID'],
        "id": project_id
    }).json()
    return res.get("result", {}).get("item", {}).get("title")


def update_beneficiary(beneficiary_id, fields):
    url = f"{config['B24_WEBHOOK_URL']}/crm.item.update"
    payload = {
        "entityTypeId": config['BENEFICIARY_ENTITY_TYPE_ID'],
        "id": beneficiary_id,
        "fields": fields
    }
    res = requests.post(url, json=payload).json()
    if "error" in res:
        print(t("❌ Error updating {id}: {msg}", id=beneficiary_id, msg=res.get('error_description', 'Unknown error')))
    else:
        print(t("✅ Updated beneficiary {id}", id=beneficiary_id))


def process_beneficiary(item):
    beneficiary_id = item["id"]
    parent_project_id = item.get("parentId1080")

    if not parent_project_id:
        print(t("⏩ Skipping {id}, no linked project.", id=beneficiary_id))
        return

    project_name = get_project_name(parent_project_id)
    if not project_name:
        print(t("⚠️ Could not fetch project title for {id}", id=parent_project_id))
        return

    prev_projects = item.get(config['PREVIOUS_PROJECTS_FIELD'], "")
    updated_projects = f"{prev_projects}, {project_name}" if prev_projects else project_name

    update_fields = {
        config['PREVIOUS_PROJECTS_FIELD']: updated_projects,
        "parentId1080": None,
        "ufCrm5_1756889079": None,
        "stageId": config['VERIFIED_STAGE_ID']
    }

    update_beneficiary(beneficiary_id, update_fields)


def get_all_completed_beneficiaries():
    all_items = []
    last_id = 0

    while True:
        res = requests.post(
            f"{config['B24_WEBHOOK_URL']}/crm.item.list",
            json={
                "entityTypeId": config['BENEFICIARY_ENTITY_TYPE_ID'],
                "order": {"id": "ASC"},
                "filter": {
                    "stageId": config['COMPLETED_STAGE_ID'],
                    ">id": last_id
                },
                "start": 0
            }
        ).json()

        items = res.get("result", {}).get("items", [])
        if not items:
            break

        all_items.extend(items)
        last_id = items[-1]["id"]
        time.sleep(0.2)

        if len(items) < 50:
            break

    return all_items


if __name__ == "__main__":
    print(t("🔍 Fetching all completed beneficiaries..."))
    beneficiaries = get_all_completed_beneficiaries()
    print(t("👥 Found {n} in completed stage.\n", n=len(beneficiaries)))

    for b in beneficiaries:
        process_beneficiary(b)
