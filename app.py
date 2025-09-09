from flask import Flask, render_template, request, redirect, url_for, flash, send_file
import subprocess
import os
import json
from config_loader import load_config, save_config
import pandas as pd
import requests
from openpyxl import Workbook
import io
import math
from werkzeug.utils import secure_filename
from assign_beneficiaries import assign_beneficiaries_from_excel





app = Flask(__name__)
app.secret_key = "super-secret-key"

# Translation dictionary
translations = {
    'ky': {
        "System Configuration": "Системаны жөндөө",
        "Run": "Ишке киргизүү",
        "Result": "Натыйжа",
        "Check for duplicated households": "Үй-бүлөлөрдү кайталануу үчүн текшерүү",
        "Check Eligibility": "Татыктуулукту текшерүү",
        "Remove Payment Duplicates": "Төлөм кайталанууларын алып салуу",
        "Check Duplicate IDs": "ID кайталануусун текшерүү",
        "Reset Beneficiaries": "Бенефициарларды баштапкы абалга келтирүү",
        "System Configuration": "Системанын жөндөөлөрү",
        "121 API URL": "121 API дареги",
        "121 API Username": "121 API колдонуучу аты",
        "121 API Password": "121 API сырсөзү",
        "Matching fields": "Тең келген талаалар",
        "Beneficiary field": "Бенефициардын талаасы",
        "Project field": "Долбоор талаасы",
        "Duplicate enum values": "Дубликат энум маанилери",
        "Unique": "Өзгөрүлмө",
        "Duplicate": "Кайталанган",
        "Save Configuration": "Жөндөөлөрдү сактоо",
        "B24 Settings": "B24 Settings",
        'fetching_children': '👶 Бардык балдарды жүктөө...',
        'found_beneficiaries_with_children': '👥 {count} бала бар бенефициар табылды.',
        'detecting_duplicates': '🔍 Баланын аты жана туулган датасы боюнча дубликаттарды табуу...',
        'found_duplicates': '⚠️ {count} мүмкүн болгон дубликаттар табылды.',
        'fetching_beneficiaries': '📦 Бардык бенефициарларды жүктөө...',
        'duplicate_household': '⚠️ Дубликат үй-бүлө: {name} → дал келет: {match_name}',
        "Starting payment deduplication...": "Төлөмдөрдү кайталоодон тазалоо башталды...",
        "Deleted duplicate payment ID": "Кайталап киргизилген төлөм өчүрүлдү. ID",
        "Failed to delete payment ID": "Төлөмдү өчүрүү ишке ашкан жок. ID",
        "Done. Deleted {count} duplicates: {ids}": "Аякталды. {count} кайталоо өчүрүлдү: {ids}",
        "Developed by 510 @ Netherlands Red Cross. Maintained by Kyrgyzstan Red Crescent": "Разработано 510 при Нидерландском Красном Кресте. Поддерживается Красным Полумесяцем Кыргызстана.",
        "For any support, contact sh.abdiseitov@redcrescent.kg": "Көмөк керек болсо, sh.abdiseitov@redcrescent.kg дарегине кайрылыңыз.",
        "Go to System Configuration": "Системанын жөндөөлөрүнө өтүү",
        "Run Scripts": "Скрипттерди иштетүү",
        "Import from Excel": "Excel файлынан импорттоо",
        "Step 1: Download Template": "1-кадам: Шаблонду жүктөп алуу",
        "Step 2: Import Excel File": "2-кадам: Excel файлды импорттоо",        
        "Step 3: Assign Beneficiaries to Project from Government List": "3-кадам: Бенефициарларды мамлекеттик тизмеден долбоорго дайындоо",
        "Select Entity": "Субъектини тандаңыз",
        "Download Template": "Шаблонду жүктөө",
        "Import Excel": "Excel импорттоо",
        "Upload Excel File": "Excel файлын жүктөө",
        "Assign to Project": "Долбоорго дайындоо",
        "All rights reserved.": "Бардык укуктар корголгон.",
        "Make sure you upload an Excel file with the following columns:": "Excel файлын төмөнкү колонкалар менен жүктөгөнүңүзгө ынаныңыз:",
        "| First Name | Last Name | Patronymic | ID Number | Region | Project Name |": "| Аты | Фамилиясы | Атасынын аты | Жеке ID номери | Регион | Долбоордун аталышы |",
        "The Project Name must be exactly the same as the project in Bitrix24.": "Долбоордун аталышы Bitrix24төгү долбоор менен так бирдей болушу керек.",
        "Successfully imported {n} records.": "{n} жазуу ийгиликтүү импорттолду.",
        "Home": "Башкы бет",
        "Welcome": "Кош келиңиз",
        "Choose an action below.": "Төмөндөн аракетти тандаңыз.",
        "Go to Scripts": "Скрипттерге өтүү",
        "Go to Excel Import": "Excel импортко өтүү"
    },
    'ru': {
        "System Configuration": "Системная конфигурация",
        "Run": "Запустить",
        "Result": "Результат",
        "Check for duplicated households": "Проверка дубликатов домохозяйств",
        "Check Eligibility": "Проверка соответствия",
        "Remove Payment Duplicates": "Удалить дубликаты платежей",
        "Check Duplicate IDs": "Проверка дубликатов ID",
        "Reset Beneficiaries": "Сбросить бенефициаров",
        "System Configuration": "Системная конфигурация",
        "121 API URL": "121 API ссылка",
        "121 API Username": "Имя пользователя 121 API",
        "121 API Password": "Пароль от 121 API",
        "Matching fields": "Поля для сопоставления",
        "Beneficiary field": "Поле бенефициара",
        "Project field": "Поле проекта",
        "Duplicate enum values": "Значения enum для дубликатов",
        "Unique": "Уникальный",
        "Duplicate": "Дубликат",
        "Save Configuration": "Сохранить настройки",
        "B24 Settings": "B24 Settings",
        'fetching_children': '👶 Получение всех детей...',
        'found_beneficiaries_with_children': '👥 Найдено {count} бенефициаров с детьми.',
        'detecting_duplicates': '🔍 Поиск дубликатов по имени ребенка и дате рождения...',
        'found_duplicates': '⚠️ Найдено {count} потенциальных дубликатов.',
        'fetching_beneficiaries': '📦 Получение всех бенефициаров...',
        'duplicate_household': '⚠️ Обнаружено совпадение: {name} → совпадает с: {match_name}',
        "Starting payment deduplication...": "Начато удаление дублирующихся платежей...",
        "Deleted duplicate payment ID": "Удалён дублирующийся платёж ID",
        "Failed to delete payment ID": "Не удалось удалить платёж ID",
        "Done. Deleted {count} duplicates: {ids}": "Готово. Удалено {count} дубликатов: {ids}",
        "Developed by 510 @ Netherlands Red Cross. Maintained by Kyrgyzstan Red Crescent": "Разработано 510 при Нидерландском Красном Кресте. Поддерживается Красным Полумесяцем Кыргызстана.",
        "For any support, contact sh.abdiseitov@redcrescent.kg": "По вопросам поддержки обращайтесь: sh.abdiseitov@redcrescent.kg",
        "Go to System Configuration": "Перейти к настройкам системы",
        "Run Scripts": "Запустить скрипты",
        "Import from Excel": "Импорт из Excel",
        "Step 1: Download Template": "Шаг 1: Скачать шаблон",
        "Step 2: Import Excel File": "Шаг 2: Импортировать Excel файл",
        "Step 3: Assign Beneficiaries to Project from Government List": "Шаг 3: Назначить бенефициаров на проект из государственного списка",
        "Select Entity": "Выберите сущность",
        "Download Template": "Скачать шаблон",
        "Import Excel": "Импорт Excel",
        "Upload Excel File": "Загрузить Excel файл",
        "Assign to Project": "Назначить на проект",
        "All rights reserved.": "Все права защищены.",
        "Make sure you upload an Excel file with the following columns:": "Убедитесь, что вы загружаете Excel-файл со следующими колонками:",
        "| First Name | Last Name | Patronymic | ID Number | Region | Project Name |": "| Имя | Фамилия | Отчество | Номер удостоверения личности | Регион | Название проекта |",
        "The Project Name must be exactly the same as the project in Bitrix24.": "Название проекта должно в точности совпадать с проектом в Bitrix24.",
        "Successfully imported {n} records.": "Успешно импортировано {n} записей.",
        "Home": "Главная",
        "Welcome": "Добро пожаловать",
        "Choose an action below.": "Выберите действие ниже.",
        "Go to Scripts": "Перейти к скриптам",
        "Go to Excel Import": "Перейти к импорту из Excel"
        }
}

def translate(key, lang):
    return translations.get(lang, {}).get(key, key)

# Script configuration
SCRIPT_CONFIG = {
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
    "check_duplicate_ids": {
        "filename": "scripts/Duplicate_Check.py",
        "label_key": "Check Duplicate IDs"
    },
    "reset_beneficiaries": {
        "filename": "scripts/resetting_beneficiaries.py",
        "label_key": "Reset Beneficiaries"
    }
}


@app.route("/", methods=["GET"])
def home():
    lang = request.args.get("lang", "en")

    # Your existing translate function
    t = lambda key: translate(key, lang)

    # Render the home page template
    return render_template("home.html", t=t, lang=lang)



@app.route('/system-config', methods=['GET', 'POST'])
def system_config():
    lang = request.args.get('lang', 'en')
    t = lambda key: translate(key, lang)

    config = load_config()

    if request.method == 'POST':
        updated_config = dict(config)

        # Update simple text/integer fields
        simple_fields = [
            "B24_WEBHOOK_URL",
            "PROJECT_ENTITY_TYPE_ID",
            "BENEFICIARY_ENTITY_TYPE_ID",
            "PAYMENT_ENTITY_TYPE_ID",
            "CHILD_ENTITY_TYPE_ID",
            "REGISTRATION_STAGE_ID",
            "VERIFIED_STAGE_ID",
            "ELIGIBLE_STAGE_ID",
            "COMPLETED_STAGE_ID",
            "STAGE_ID",
            "ELIGIBILITY_FIELD_ID",
            "PROGRAM_COUNT_FIELD_ID",
            "PROGRAM_NAMES_FIELD_ID",
            "DUPLICATE_CHECK_NATIONAL_ID_FIELD",
            "DUPLICATE_CHECK_NAME_FIELD",
            "DUPLICATE_FLAG_FIELD",
            "DUPLICATE_REASON_FIELD",
            "NATIONAL_ID_FIELD",
            "PROJECT_TYPE_FIELD",
            "CHILD_DOB_FIELD",
            "CHILD_AGE_FIELD",
            "CHILD_DEDUPLICATION_FIELD",
            "CHILD_DUPLICATE_NAME_FIELD",
            "PREVIOUS_PROJECTS_FIELD",
            "First Name"
        ]

        for field in simple_fields:
            if field in request.form:
                val = request.form.get(field)
                if isinstance(config.get(field), int):
                    try:
                        val = int(val)
                    except ValueError:
                        val = config.get(field)
                updated_config[field] = val

        # Handle MATCHING_FIELDS as a list of dictionaries (three-column structure)
        try:
            count = int(request.form.get('match_field_count', 0))
        except ValueError:
            count = 0

        matching_fields = []
        for i in range(count):
            opt = request.form.get(f'optional_name_{i}', '').strip()
            ben = request.form.get(f'beneficiary_field_{i}', '').strip()
            proj = request.form.get(f'project_field_{i}', '').strip()
            if ben and proj:
                matching_fields.append({
                    "optional_name": opt,
                    "beneficiary_field": ben,
                    "project_field": proj
                })
        updated_config["MATCHING_FIELDS"] = matching_fields
        import_fields = {}
        for key in request.form:
            if key.startswith("IMPORT_FIELDS[") and key.endswith("]"):
                display_name = key[len("IMPORT_FIELDS["):-1]
                internal_field = request.form.get(key)
                import_fields[display_name] = internal_field
        if import_fields:
            updated_config["IMPORT_FIELDS"] = import_fields        
        save_config(updated_config)
        return redirect(url_for('system_config', lang=lang, saved='true'))

    return render_template(
        'system_config.html',
        config=config,
        lang=lang,
        t=t,
        saved=request.args.get('saved', 'false')
    )




@app.route('/scripts', methods=['GET', 'POST'])
def scripts_page():
    lang = request.args.get('lang', 'en')
    result = None
    selected_script = None
    t = lambda key: translate(key, lang)

    if request.method == 'POST':
        selected_script = request.form.get('script')
        lang = request.form.get('lang', 'en')
        t = lambda key: translate(key, lang)

        if selected_script in SCRIPT_CONFIG:
            script_path = SCRIPT_CONFIG[selected_script]['filename']
            if os.path.exists(script_path):
                try:
                    result = subprocess.check_output(
                        ["python", script_path, lang],
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding='utf-8'
                    )
                except subprocess.CalledProcessError as e:
                    result = f"Error running script:\n{e.output}"
            else:
                result = f"Script not found at path: {script_path}"

    return render_template(
        'scripts.html',
        scripts=SCRIPT_CONFIG,
        lang=lang,
        t=t,
        result=result,
        selected_script=selected_script
    )

if __name__ == '__main__':
    app.run(debug=True)


@app.route('/import-excel', methods=['GET', 'POST'])
def import_excel():
    config = load_config()

    lang = request.args.get('lang', 'en')
    t = lambda key: translate(key, lang)

    if request.method == 'POST':
        lang = request.form.get('lang', lang)
        t = lambda key: translate(key, lang)

        entity = request.form.get('entity')
        file = request.files.get('file')

        if not entity or not file:
            flash(t("Entity or file not provided."), "error")
            return redirect(url_for('import_excel', lang=lang))

        entity_ids = {
            "beneficiaries": config["BENEFICIARY_ENTITY_TYPE_ID"],
            "projects": config["PROJECT_ENTITY_TYPE_ID"],
            "payments": config["PAYMENT_ENTITY_TYPE_ID"],
            "children": config["CHILD_ENTITY_TYPE_ID"]
        }

        entity_type_id = entity_ids.get(entity)
        if not entity_type_id:
            flash(t("Invalid entity selected."), "error")
            return redirect(url_for('import_excel', lang=lang))

        try:
            df = pd.read_excel(file)

            # Fetch field codes from Bitrix to map titles to field codes
            field_response = requests.get(
                f"{config['B24_WEBHOOK_URL']}/crm.item.fields",
                params={"entityTypeId": entity_type_id}
            )
            field_response.raise_for_status()
            field_data = field_response.json()["result"]["fields"]

            # Map Excel column headers to Bitrix field codes
            title_to_code = {
                field["title"]: code
                for code, field in field_data.items()
                if not field.get("isReadOnly", True) and field.get("title")
            }

            import math
            def clean_value(val):
                if pd.isna(val) or (isinstance(val, float) and not math.isfinite(val)):
                    return None
                if isinstance(val, str) and val.strip() == '':
                    return None
                return val

            results = []
            for _, row in df.iterrows():
                data_fields = {}

                for column in df.columns:
                    b24_code = title_to_code.get(column)
                    if b24_code:
                        value = clean_value(row.get(column))
                        if value is not None:
                            data_fields[b24_code] = value

                response = requests.post(
                    f"{config['B24_WEBHOOK_URL']}/crm.item.add.json",
                    json={
                        'entityTypeId': entity_type_id,
                        'fields': data_fields
                    }
                )
                results.append(response.json())

            flash(t("Successfully imported {n} records.").format(n=len(results)), "success")
        except Exception as e:
            flash(t(f"Error: {str(e)}"), "error")

    return render_template('import_excel.html', t=t, lang=lang)


@app.route('/download-template', methods=['GET'])
def download_template():
    import io
    from openpyxl import Workbook

    config = load_config()
    lang = request.args.get('lang', 'en')
    entity = request.args.get('entity')

    # Validate entity
    entity_map = {
        "beneficiaries": config.get("BENEFICIARY_ENTITY_TYPE_ID"),
        "projects": config.get("PROJECT_ENTITY_TYPE_ID"),
        "payments": config.get("PAYMENT_ENTITY_TYPE_ID"),
        "children": config.get("CHILD_ENTITY_TYPE_ID")
    }
    entity_id = entity_map.get(entity)
    if not entity_id:
        flash("Invalid entity selected", "error")
        return redirect(url_for('import_excel', lang=lang))

    # Fetch fields from Bitrix
    try:
        response = requests.get(
            f"{config['B24_WEBHOOK_URL']}/crm.item.fields",
            params={"entityTypeId": entity_id}
        )
        response.raise_for_status()
        fields = response.json().get("result", {}).get("fields", {})
    except Exception as e:
        flash(f"Failed to fetch fields: {str(e)}", "error")
        return redirect(url_for('import_excel', lang=lang))

    # Get import fields dictionary (label → field ID)
    import_fields_dict = config.get("IMPORT_FIELDS", {})
    if not import_fields_dict:
        flash(f"No import fields specified for entity '{entity}'.", "error")
        return redirect(url_for('import_excel', lang=lang))

    # Build headers based on Bitrix field titles or fallback to config label
    headers = []
    for label, field_id in import_fields_dict.items():
        field_data = fields.get(field_id)
        title = field_data.get("title") if field_data else None
        headers.append(title or label or field_id)

    if not headers:
        flash("No valid fields found to include in template.", "error")
        return redirect(url_for('import_excel', lang=lang))

    # Create Excel file
    output = io.BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = f"{entity.title()} Template"
    ws.append(headers)
    wb.save(output)
    output.seek(0)

    filename = f"{entity}_template.xlsx"
    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.route('/assign-to-project', methods=['POST'])
def assign_to_project():
    lang = request.form.get('lang', 'en')
    t = lambda key: translate(key, lang)

    file = request.files.get('govListFile')
    if not file or file.filename == '':
        flash("❌ No file selected", "danger")
        return redirect(url_for('import_excel', lang=lang))

    os.makedirs("uploads", exist_ok=True)
    path = os.path.join("uploads", secure_filename(file.filename))
    file.save(path)

    try:
        results = assign_beneficiaries_from_excel(path)

        # Handle dict output with "successes", "warnings", "errors"
        for msg in results.get("successes", []):
            flash(msg, "success")
        for msg in results.get("warnings", []):
            flash(msg, "warning")
        for msg in results.get("errors", []):
            flash(msg, "danger")

    except Exception as e:
        flash(f"❌ Error: {str(e)}", "danger")

    return redirect(url_for('import_excel', lang=lang))


@app.route('/generate-fsp-report', methods=['POST'])
def generate_fsp_report_route():
    from generate_fsp_report import generate_report  # we'll refactor script into a function

    lang = request.args.get('lang', 'en')
    project_name = request.form.get('project_name')

    if not project_name:
        flash("❌ No project name provided", "danger")
        return redirect(url_for('import_excel', lang=lang))

    try:
        # Call refactored function (see next step)
        output = io.BytesIO()
        generate_report(project_name, output)
        output.seek(0)

        filename = f"FSP_Report_{project_name}.xlsx"
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        flash(f"❌ Error generating report: {str(e)}", "danger")
        return redirect(url_for('import_excel', lang=lang))
