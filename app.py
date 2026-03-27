from flask import Flask, render_template, request
import subprocess
import os
from config_loader import load_config

app = Flask(__name__)
app.secret_key = "super-secret-key"

# Translation dictionary
translations = {
    'ky': {
        "Run Scripts": "Скрипттерди иштетүү",
        "Run": "Ишке киргизүү",
        "Sync to Kobo": "Koboго синхрондоштуруу",
        "Check Duplicate IDs and Names": "ID жана толук аттарды кайталануу үчүн текшерүү",
        "Check for duplicated households": "Үй-бүлөлөрдү кайталануу үчүн текшерүү",
        "Check Eligibility": "Татыктуулукту текшерүү",
        "Remove Payment Duplicates": "Төлөм кайталанууларын алып салуу",
        "Reset Beneficiaries": "Бенефициарларды баштапкы абалга келтирүү",
        "Developed by 510 @ Netherlands Red Cross. Maintained by Kyrgyzstan Red Crescent": "Разработано 510 при Нидерландском Красном Кресте. Поддерживается Красным Полумесяцем Кыргызстана.",
        "For any support, contact sh.abdiseitov@redcrescent.kg": "Көмөк керек болсо, sh.abdiseitov@redcrescent.kg дарегине кайрылыңыз.",
    },
    'ru': {
        "Run Scripts": "Запустить скрипты",
        "Run": "Запустить",
        "Sync to Kobo": "Синхронизация с Kobo",
        "Check Duplicate IDs and Names": "Проверка дубликатов ID и полных имён",
        "Check for duplicated households": "Проверка дубликатов домохозяйств",
        "Check Eligibility": "Проверка соответствия",
        "Remove Payment Duplicates": "Удалить дубликаты платежей",
        "Reset Beneficiaries": "Сбросить бенефициаров",
        "Developed by 510 @ Netherlands Red Cross. Maintained by Kyrgyzstan Red Crescent": "Разработано 510 при Нидерландском Красном Кресте. Поддерживается Красным Полумесяцем Кыргызстана.",
        "For any support, contact sh.abdiseitov@redcrescent.kg": "По вопросам поддержки обращайтесь: sh.abdiseitov@redcrescent.kg",
    }
}

def translate(key, lang):
    return translations.get(lang, {}).get(key, key)

SCRIPT_CONFIG = {
    "sync_to_kobo": {
        "filename": "scripts/sync_to_kobo.py",
        "label_key": "Sync to Kobo"
    },
    "check_duplicate_ids": {
        "filename": "scripts/Duplicate_Check.py",
        "label_key": "Check Duplicate IDs and Names"
    },
    "deduplicate": {
        "filename": "scripts/Child_deduplication.py",
        "label_key": "Check for duplicated households"
    },
    "check_eligibility": {
        "filename": "scripts/Eligibility_Check.py",
        "label_key": "Check Eligibility"
    },
    "remove_payment_duplicates": {
        "filename": "scripts/Deduplicate_Payments.py",
        "label_key": "Remove Payment Duplicates"
    },
    "reset_beneficiaries": {
        "filename": "scripts/resetting_beneficiaries.py",
        "label_key": "Reset Beneficiaries"
    }
}


@app.route("/", methods=["GET", "POST"])
def home():
    lang = request.args.get("lang", "en")
    result = None
    selected_script = None
    t = lambda key: translate(key, lang)

    if request.method == "POST":
        selected_script = request.form.get("script")
        lang = request.form.get("lang", "en")
        t = lambda key: translate(key, lang)

        if selected_script in SCRIPT_CONFIG:
            script_path = SCRIPT_CONFIG[selected_script]["filename"]
            if os.path.exists(script_path):
                try:
                    result = subprocess.check_output(
                        ["python", script_path, lang],
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding="utf-8"
                    )
                except subprocess.CalledProcessError as e:
                    result = f"Error running script:\n{e.output}"
            else:
                result = f"Script not found at path: {script_path}"

    return render_template(
        "scripts.html",
        scripts=SCRIPT_CONFIG,
        lang=lang,
        t=t,
        result=result,
        selected_script=selected_script
    )


if __name__ == "__main__":
    app.run(debug=True)