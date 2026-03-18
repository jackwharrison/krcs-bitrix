import requests
import os
import csv
import io
import smtplib
from email.message import EmailMessage

WEBHOOK_URL = os.environ["B24_WEBHOOK_URL"]
KOBO_TOKEN  = os.environ["KOBO_API_TOKEN"]
KOBO_ASSET  = os.environ["KOBO_ASSET_UID"]
ALERT_EMAIL = os.environ["ALERT_EMAIL"]
SMTP_HOST   = os.environ["SMTP_HOST"]
SMTP_PORT   = int(os.environ.get("SMTP_PORT", 587))
SMTP_USER   = os.environ["SMTP_USER"]
SMTP_PASS   = os.environ["SMTP_PASS"]

FILENAME    = "cva_beneficiaries.csv"
KOBO_FILES  = f"https://kobotoolbox.org/api/v2/assets/{KOBO_ASSET}/files/"
HEADERS     = {"Authorization": f"Token {KOBO_TOKEN}"}


def alert(reason):
    try:
        msg = EmailMessage()
        msg["Subject"] = "Kobo CSV sync failed"
        msg["From"]    = SMTP_USER
        msg["To"]      = ALERT_EMAIL
        msg.set_content(
            f"The scheduled Bitrix24 → Kobo sync failed.\n\n"
            f"Reason: {reason}\n\n"
            f"Please upload cva_beneficiaries.csv manually to Kobo.\n"
            f"Project: https://kobotoolbox.org/api/v2/assets/{KOBO_ASSET}/"
        )
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
    except Exception as e:
        print(f"Failed to send alert email: {e}")


def fetch_beneficiaries():
    items = []
    start = 0
    while True:
        r = requests.post(
            f"{WEBHOOK_URL}/crm.item.list",
            json={
                "entityTypeId": 1036,
                "select": ["id", "title", "ufCrm5_1756874615326"],
                "start": start
            }
        )
        r.raise_for_status()
        result = r.json().get("result", {})
        items.extend(result.get("items", []))
        if "next" not in result:
            break
        start = result["next"]
    return items


def build_csv(items):
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)
    writer.writerow(["national_id", "bitrix_id", "name"])
    for item in items:
        writer.writerow([
            item.get("ufCrm5_1756874615326", ""),
            item.get("id", ""),
            item.get("title", "")
        ])
    return output.getvalue()


def get_existing_file_uid():
    r = requests.get(KOBO_FILES, headers=HEADERS)
    r.raise_for_status()
    for f in r.json().get("results", []):
        if f.get("metadata", {}).get("filename") == FILENAME:
            return f["uid"]
    return None


def delete_file(uid):
    r = requests.delete(f"{KOBO_FILES}{uid}/", headers=HEADERS)
    r.raise_for_status()


def upload_csv(csv_content):
    boundary = "----SyncBoundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file_type"\r\n\r\n'
        f"form_media\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="content"; filename="{FILENAME}"\r\n'
        f"Content-Type: text/csv\r\n\r\n"
        f"{csv_content}\r\n"
        f"--{boundary}--\r\n"
    )
    upload_headers = {
        **HEADERS,
        "Content-Type": f"multipart/form-data; boundary={boundary}"
    }
    r = requests.post(KOBO_FILES, headers=upload_headers, data=body.encode("utf-8"))
    if r.status_code != 201:
        raise Exception(f"Upload failed: {r.status_code} {r.text}")


def main():
    print("Starting Bitrix24 → Kobo sync...")
    try:
        print("Fetching beneficiaries from Bitrix24...")
        items = fetch_beneficiaries()
        print(f"Fetched {len(items)} records.")

        csv_content = build_csv(items)

        print("Checking for existing Kobo media file...")
        uid = get_existing_file_uid()
        if uid:
            print(f"Deleting existing file (uid: {uid})...")
            delete_file(uid)

        print("Uploading new CSV to Kobo...")
        upload_csv(csv_content)
        print("Sync complete.")

    except Exception as e:
        print(f"Sync failed: {e}")
        alert(str(e))
        raise


if __name__ == "__main__":
    main()