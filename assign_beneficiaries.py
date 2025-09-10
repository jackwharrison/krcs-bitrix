import requests
import pandas as pd
from config_loader import load_config


def assign_beneficiaries_from_excel(file_path):
    # Load config through config_loader so B24_WEBHOOK_URL is injected from env
    config = load_config()

    WEBHOOK = config["B24_WEBHOOK_URL"]
    BENEFICIARY_ENTITY_TYPE_ID = config["BENEFICIARY_ENTITY_TYPE_ID"]
    PROJECT_ENTITY_TYPE_ID = config["PROJECT_ENTITY_TYPE_ID"]
    NATIONAL_ID_FIELD = config["DUPLICATE_CHECK_NATIONAL_ID_FIELD"]
    FULL_NAME_FIELD = config["DUPLICATE_CHECK_NAME_FIELD"]

    df = pd.read_excel(file_path)
    success = 0
    failures = []

    def search_project_by_name(project_name):
        url = f"{WEBHOOK}/crm.item.list"
        params = {
            "entityTypeId": PROJECT_ENTITY_TYPE_ID,
            "filter": {"title": project_name}
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
        return response.get("result") and isinstance(response["result"].get("item"), dict)

    for i, row in df.iterrows():
        first = str(row.get("First Name", "")).strip()
        last = str(row.get("Last Name", "")).strip()
        patr_raw = row.get("Patronymic", "")
        patr = str(patr_raw).strip() if pd.notna(patr_raw) else ""
        nid = str(row.get("National ID", "")).strip()
        proj = str(row.get("Project Name", "")).strip()

        if not (first and last and nid and proj):
            failures.append(f"Row {i+2}: Missing required data")
            continue

        full_name_parts = [first]
        if patr:
            full_name_parts.append(patr)
        full_name_parts.append(last)
        full_name = " ".join(full_name_parts).strip()

        project_id = search_project_by_name(proj)
        if not project_id:
            failures.append(f"Row {i+2}: Project '{proj}' not found")
            continue

        beneficiary_id = search_beneficiary(full_name, nid)
        if not beneficiary_id:
            failures.append(f"Row {i+2}: Beneficiary '{full_name}' with ID '{nid}' not found")
            continue

        url = f"{WEBHOOK}/crm.item.get"
        params = {
            "entityTypeId": BENEFICIARY_ENTITY_TYPE_ID,
            "id": beneficiary_id
        }
        r = requests.post(url, json=params)
        current_project = r.json().get("result", {}).get("item", {}).get(f"parentId{PROJECT_ENTITY_TYPE_ID}")

        if current_project == project_id:
            failures.append(f"Row {i+2}: {full_name} is already assigned to project '{proj}'")
            continue

        if update_beneficiary_parent(beneficiary_id, project_id):
            success += 1
        else:
            failures.append(f"Row {i+2}: Failed to update {full_name}")

    results = {
        "successes": [f"✅ Successfully linked {success} beneficiaries."] if success else [],
        "warnings": [],
        "errors": []
    }

    for failure in failures:
        if "already assigned to project" in failure:
            results["warnings"].append(failure)
        else:
            results["errors"].append(failure)

    return results
