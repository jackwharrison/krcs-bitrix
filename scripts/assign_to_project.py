import json
import requests
import pandas as pd
import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "..", "system_config.json")
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

# Excel file (in the same folder as the script)
EXCEL_FILE = os.path.join(BASE_DIR, "beneficiaries_to_projects.xlsx")
df = pd.read_excel(EXCEL_FILE)
WEBHOOK = config["B24_WEBHOOK_URL"]
BENEFICIARY_ENTITY_TYPE_ID = config["BENEFICIARY_ENTITY_TYPE_ID"]
PROJECT_ENTITY_TYPE_ID = config["PROJECT_ENTITY_TYPE_ID"]
NATIONAL_ID_FIELD = config["DUPLICATE_CHECK_NATIONAL_ID_FIELD"]
FULL_NAME_FIELD = config["DUPLICATE_CHECK_NAME_FIELD"]


# Excel file path (must be in the same folder as this script)

# Load Excel
df = pd.read_excel(EXCEL_FILE)

success = 0
failures = []

def search_project_by_name(project_name):
    url = f"{WEBHOOK}/crm.item.list"
    params = {
        "entityTypeId": PROJECT_ENTITY_TYPE_ID,
        "filter": { "title": project_name }
    }
    r = requests.post(url, json=params)
    result = r.json()
    if result.get("result", {}).get("items"):
        return result["result"]["items"][0]["id"]
    return None

def search_beneficiary(full_name, national_id):
    url = f"{WEBHOOK}/crm.item.list"
    params = {
        "entityTypeId": BENEFICIARY_ENTITY_TYPE_ID,
        "filter": {
            FULL_NAME_FIELD: full_name,
            NATIONAL_ID_FIELD: national_id
        }
    }
    r = requests.post(url, json=params)
    result = r.json()
    if result.get("result", {}).get("items"):
        return result["result"]["items"][0]["id"]
    return None

def update_beneficiary_parent(beneficiary_id, project_id):
    url = f"{WEBHOOK}/crm.item.update"
    params = {
        "entityTypeId": BENEFICIARY_ENTITY_TYPE_ID,
        "id": beneficiary_id,
        "fields": {
            f"parentId{PROJECT_ENTITY_TYPE_ID}": project_id
        }
    }
    r = requests.post(url, json=params)
    response = r.json()

    # ✅ Check for 'item' in result instead of just boolean true
    if response.get("result") and isinstance(response["result"].get("item"), dict):
        return True
    else:
        print(f"❌ Failed to update beneficiary ID {beneficiary_id} with project ID {project_id}")
        print("Bitrix24 response:", json.dumps(response, indent=2))
        return False

# Process each row
for i, row in df.iterrows():
    first = str(row.get("First Name", "")).strip()
    last = str(row.get("Last Name", "")).strip()
    patr = str(row.get("Patronymic", "")).strip()
    nid = str(row.get("National ID", "")).strip()
    proj = str(row.get("Project Name", "")).strip()

    if not (first and last and nid and proj):
        failures.append((i+2, "Missing required data"))
        continue

    full_name_parts = [first]
    if patr:
        full_name_parts.append(patr)
    full_name_parts.append(last)
    full_name = " ".join(full_name_parts).strip()



    project_id = search_project_by_name(proj)
    if not project_id:
        failures.append((i+2, f"Project '{proj}' not found"))
        continue

    beneficiary_id = search_beneficiary(full_name, nid)
    if not beneficiary_id:
        failures.append((i+2, f"Beneficiary '{full_name}' with ID '{nid}' not found"))
        continue
    url = f"{WEBHOOK}/crm.item.get"
    params = {
        "entityTypeId": BENEFICIARY_ENTITY_TYPE_ID,
        "id": beneficiary_id
    }
    r = requests.post(url, json=params)
    result = r.json()
    current_project = result.get("result", {}).get("item", {}).get(f"parentId{PROJECT_ENTITY_TYPE_ID}")

    if current_project == project_id:
        failures.append((i+2, f"{full_name} is already assigned to project '{proj}'"))
        continue
    success_flag = update_beneficiary_parent(beneficiary_id, project_id)
    if success_flag:
        success += 1
    else:
        failures.append((i+2, "Failed to update beneficiary"))

# Output summary
print(f"\n✅ Successfully linked {success} beneficiaries to projects.")
if failures:
    print("\n❌ Failures:")
    for row_num, reason in failures:
        print(f"  Row {row_num}: {reason}")
else:
    print("\n🎉 No failures.")
