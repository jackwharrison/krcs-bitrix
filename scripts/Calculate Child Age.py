import requests
import config
from datetime import datetime

def fetch_all_children():
    """Fetch all children from Bitrix."""
    items = []
    start = 0
    while True:
        res = requests.get(
            f"{config.B24_WEBHOOK_URL}/crm.item.list",
            params={"entityTypeId": config.CHILD_ENTITY_TYPE_ID, "start": start}
        ).json()
        batch = res.get("result", {}).get("items", [])
        items.extend(batch)
        if "next" not in res.get("result", {}):
            break
        start = res["result"]["next"]
    return items

def update_child(child_id, fields):
    """Update child record with calculated age."""
    payload = {
        "entityTypeId": config.CHILD_ENTITY_TYPE_ID,
        "id": child_id,
        "fields": fields
    }
    res = requests.post(f"{config.B24_WEBHOOK_URL}/crm.item.update", json=payload)
    if not res.ok or "result" not in res.json():
        print(f"❌ Error updating child {child_id}: {res.text}")
    return res.ok

def calculate_age(dob_str):
    """Calculate age from ISO8601 or common date formats."""
    formats = ["%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S%z"]
    for fmt in formats:
        try:
            dob = datetime.strptime(dob_str, fmt)
            today = datetime.now(dob.tzinfo) if dob.tzinfo else datetime.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            return age
        except ValueError:
            continue
    return None

def main():
    print("👶 Fetching children...")
    children = fetch_all_children()
    updated = 0
    skipped = 0

    for child in children:
        dob_raw = child.get(config.CHILD_DOB_FIELD)
        if not dob_raw:
            continue

        calculated_age = calculate_age(dob_raw)
        if calculated_age is None:
            print(f"⚠️ Could not parse DoB '{dob_raw}' for child {child.get('id')}")
            continue

        current_age = child.get(config.CHILD_AGE_FIELD)

        # Only update if missing or different
        if current_age is None or str(current_age) != str(calculated_age):
            success = update_child(child["id"], {
                config.CHILD_AGE_FIELD: calculated_age
            })
            if success:
                print(f"✅ Updated child {child['id']} with age {calculated_age} (was {current_age})")
                updated += 1
        else:
            skipped += 1

    print(f"\n🎉 Done. Updated {updated} children, skipped {skipped} (already correct).")

if __name__ == "__main__":
    main()
