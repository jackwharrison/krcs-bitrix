import requests
import csv
import io
import smtplib
import json
import os
import sys
import time
import base64
from email.message import EmailMessage

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config_loader import load_config

config = load_config()

lang = sys.argv[1] if len(sys.argv) > 1 else 'en'

TRANSLATIONS = {
    'ky': {
        "Starting Bitrix24 -> Kobo sync...": "Bitrix24 -> Kobo синхрондоштуруу башталды...",
        "Fetching beneficiaries from Bitrix24...": "Bitrix24дан бенефициарларды жүктөө...",
        "Fetched {n} records total.": "Жалпы {n} жазуу жүктөлдү.",
        "Fetched {n} records. Last ID: {last_id}. Total so far: {total}": "{n} жазуу жүктөлдү. Акыркы ID: {last_id}. Жалпы: {total}",
        "Checking for existing Kobo media file...": "Koboдогу медиа файлды текшерүү...",
        "Deleting existing file (uid: {uid})...": "Учурдагы файлды өчүрүү (uid: {uid})...",
        "Uploading new CSV to Kobo...": "Жаңы CSV файлын Koboго жүктөө...",
        "Redeploying Kobo form...": "Kobo формасын кайра жайылтуу...",
        "Sync complete.": "Синхрондоштуруу аяктады.",
        "Sync failed: {error}": "Синхрондоштуруу ишке ашкан жок: {error}",
        "Alert email sent.": "Эскертүү электрондук почтасы жөнөтүлдү.",
        "Failed to send alert email: {error}": "Эскертүү электрондук почтасын жөнөтүү ишке ашкан жок: {error}",
        "KOBO_API_TOKEN not set.": "KOBO_API_TOKEN орнотулган жок.",
        "KOBO_ASSET_UID not set.": "KOBO_ASSET_UID орнотулган жок.",
        "KOBO_FIELD_MAP not configured.": "KOBO_FIELD_MAP конфигурацияланган жок.",
    },
    'ru': {
        "Starting Bitrix24 -> Kobo sync...": "Начало синхронизации Bitrix24 -> Kobo...",
        "Fetching beneficiaries from Bitrix24...": "Получение бенефициаров из Bitrix24...",
        "Fetched {n} records total.": "Всего загружено {n} записей.",
        "Fetched {n} records. Last ID: {last_id}. Total so far: {total}": "Загружено {n} записей. Последний ID: {last_id}. Всего: {total}",
        "Checking for existing Kobo media file...": "Проверка существующего медиафайла в Kobo...",
        "Deleting existing file (uid: {uid})...": "Удаление существующего файла (uid: {uid})...",
        "Uploading new CSV to Kobo...": "Загрузка нового CSV в Kobo...",
        "Redeploying Kobo form...": "Повторное развёртывание формы Kobo...",
        "Sync complete.": "Синхронизация завершена.",
        "Sync failed: {error}": "Синхронизация не удалась: {error}",
        "Alert email sent.": "Письмо с оповещением отправлено.",
        "Failed to send alert email: {error}": "Не удалось отправить письмо с оповещением: {error}",
        "KOBO_API_TOKEN not set.": "KOBO_API_TOKEN не задан.",
        "KOBO_ASSET_UID not set.": "KOBO_ASSET_UID не задан.",
        "KOBO_FIELD_MAP not configured.": "KOBO_FIELD_MAP не настроен.",
    }
}

def t(key, **kwargs):
    template = TRANSLATIONS.get(lang, {}).get(key, key)
    return template.format(**kwargs) if kwargs else template


# --- Config values ---
# Kobo-specific values come from env vars (sensitive) or system_config.json (non-sensitive)
KOBO_TOKEN  = os.environ.get("KOBO_API_TOKEN")  or config.get("KOBO_API_TOKEN", "")
KOBO_ASSET  = os.environ.get("KOBO_ASSET_UID")  or config.get("KOBO_ASSET_UID", "")
FIELD_MAP   = config.get("KOBO_FIELD_MAP", {})   # { "CSV Column Name": "bitrix_field_id" }

ALERT_EMAIL = os.environ.get("ALERT_EMAIL") or config.get("ALERT_EMAIL", "")
SMTP_HOST   = os.environ.get("SMTP_HOST")   or config.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT   = int(os.environ.get("SMTP_PORT") or config.get("SMTP_PORT", 587))
SMTP_USER   = os.environ.get("SMTP_USER")   or config.get("SMTP_USER", "")
SMTP_PASS   = os.environ.get("SMTP_PASS")   or config.get("SMTP_PASS", "")

FILENAME    = "cva_beneficiaries.csv"
KOBO_FILES  = f"https://kobo.ifrc.org/api/v2/assets/{KOBO_ASSET}/files/"
HEADERS     = {"Authorization": f"Token {KOBO_TOKEN}"}


def alert(reason):
    if not ALERT_EMAIL or not SMTP_USER or not SMTP_PASS:
        return
    try:
        msg = EmailMessage()
        msg["Subject"] = "Kobo CSV sync failed"
        msg["From"]    = SMTP_USER
        msg["To"]      = ALERT_EMAIL
        msg.set_content(
            f"The scheduled Bitrix24 -> Kobo sync failed.\n\n"
            f"Reason: {reason}\n\n"
            f"Please upload cva_beneficiaries.csv manually to Kobo.\n"
            f"Project: https://kobo.ifrc.org/api/v2/assets/{KOBO_ASSET}/"
        )
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
        print(t("Alert email sent."))
    except Exception as e:
        print(t("Failed to send alert email: {error}", error=e))


def fetch_beneficiaries():
    items = []
    last_id = 0
    while True:
        r = requests.post(
            f"{config['B24_WEBHOOK_URL']}/crm.item.list",
            json={
                "entityTypeId": config['BENEFICIARY_ENTITY_TYPE_ID'],
                "order": {"id": "ASC"},
                "filter": {">id": last_id},
                "start": 0
            }
        )
        r.raise_for_status()
        batch = r.json().get("result", {}).get("items", [])

        if not batch:
            break

        items.extend(batch)
        last_id = batch[-1]["id"]
        print(t("Fetched {n} records. Last ID: {last_id}. Total so far: {total}",
                n=len(batch), last_id=last_id, total=len(items)))
        time.sleep(0.6)

        if len(batch) < 50:
            break

    return items


def build_csv(items):
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)
    writer.writerow(list(FIELD_MAP.keys()))
    for item in items:
        row = [item.get(bitrix_field, "") for bitrix_field in FIELD_MAP.values()]
        writer.writerow(row)
    return output.getvalue()


def get_existing_file_id():
    r = requests.get(KOBO_FILES, headers=HEADERS, params={"file_type": "form_media"})
    r.raise_for_status()
    for each in r.json().get("results", []):
        if each.get("metadata", {}).get("filename") == FILENAME:
            return each["uid"]
    return None


def delete_file(file_id):
    r = requests.delete(f"{KOBO_FILES}{file_id}/", headers=HEADERS)
    if r.status_code != 204:
        raise Exception(f"Delete failed: {r.status_code} {r.text}")


def upload_csv(csv_content):
    base64_encoded = base64.b64encode(csv_content.encode("utf-8")).decode("utf-8")
    metadata = json.dumps({"filename": FILENAME})
    payload = {
        "description": "default",
        "file_type": "form_media",
        "metadata": metadata,
        "base64Encoded": f"data:text/csv;base64,{base64_encoded}",
    }
    upload_headers = {**HEADERS, "Content-Type": "application/x-www-form-urlencoded"}
    r = requests.post(KOBO_FILES, headers=upload_headers, data=payload)
    if r.status_code != 201:
        raise Exception(f"Upload failed: {r.status_code} {r.text}")


def redeploy_form():
    asset_r = requests.get(
        f"https://kobo.ifrc.org/api/v2/assets/{KOBO_ASSET}/",
        headers=HEADERS
    )
    asset_r.raise_for_status()
    version_id = asset_r.json().get("version_id")

    r = requests.patch(
        f"https://kobo.ifrc.org/api/v2/assets/{KOBO_ASSET}/deployment/",
        headers={**HEADERS, "Content-Type": "application/json"},
        json={"active": True, "version_id": version_id}
    )
    if r.status_code != 200:
        raise Exception(f"Redeploy failed: {r.status_code} {r.text}")


def main():
    # Validate required Kobo config
    if not KOBO_TOKEN:
        print(f"❌ {t('KOBO_API_TOKEN not set.')}")
        sys.exit(1)
    if not KOBO_ASSET:
        print(f"❌ {t('KOBO_ASSET_UID not set.')}")
        sys.exit(1)
    if not FIELD_MAP:
        print(f"❌ {t('KOBO_FIELD_MAP not configured.')}")
        sys.exit(1)

    print(f"🔄 {t('Starting Bitrix24 -> Kobo sync...')}")
    try:
        print(f"📦 {t('Fetching beneficiaries from Bitrix24...')}")
        items = fetch_beneficiaries()
        print(f"✅ {t('Fetched {n} records total.', n=len(items))}")

        csv_content = build_csv(items)

        print(f"🔍 {t('Checking for existing Kobo media file...')}")
        file_id = get_existing_file_id()
        if file_id:
            print(f"🗑️ {t('Deleting existing file (uid: {uid})...', uid=file_id)}")
            delete_file(file_id)

        print(f"⬆️ {t('Uploading new CSV to Kobo...')}")
        upload_csv(csv_content)

        print(f"🚀 {t('Redeploying Kobo form...')}")
        redeploy_form()

        print(f"✅ {t('Sync complete.')}")

    except Exception as e:
        print(f"❌ {t('Sync failed: {error}', error=e)}")
        alert(str(e))
        raise


if __name__ == "__main__":
    main()
