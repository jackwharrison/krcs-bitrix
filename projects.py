import requests
import config


def fetch_all_projects():
    """Fetch all project items from Bitrix24."""
    items = []
    start = 0

    while True:
        res = requests.get(
            f"{config.B24_WEBHOOK_URL}/crm.item.list",
            params={"entityTypeId": config.BENEFICIARY_ENTITY_TYPE_ID, "start": start}
        ).json()

        batch = res.get("result", {}).get("items", [])
        items.extend(batch)

        if "next" not in res.get("result", {}):
            break
        start = res["result"]["next"]

    return items


def fetch_field_labels(entity_type_id):
    """Fetch enum field labels for a given entity type."""
    res = requests.get(
        f"{config.B24_WEBHOOK_URL}/crm.item.fields",
        params={"entityTypeId": entity_type_id}
    ).json()

    fields = res.get("result", {}).get("fields", {})
    labels = {}

    for code, info in fields.items():
        if info.get("type") == "enumeration":
            items = info.get("items", [])
            if isinstance(items, list):
                labels[code] = {str(i["ID"]): i["VALUE"] for i in items}
            elif isinstance(items, dict):
                labels[code] = items  # fallback
    return labels


def translate_fields(item, field_labels):
    """Replace enum values with human-readable labels where possible."""
    translated = {}
    for key, value in item.items():
        if isinstance(value, list):
            translated[key] = [field_labels.get(key, {}).get(str(v), v) for v in value]
        else:
            translated[key] = field_labels.get(key, {}).get(str(value), value)
    return translated


def main():
    print("🔄 Fetching all projects and translating field values...\n")

    projects = fetch_all_projects()
    field_labels = fetch_field_labels(config.PROJECT_ENTITY_TYPE_ID)

    for project in projects:
        translated = translate_fields(project, field_labels)
        print(f"📦 Project ID: {project['id']}")
        for k, v in translated.items():
            print(f"  - {k}: {v}")
        print("—" * 40)


if __name__ == "__main__":
    main()
