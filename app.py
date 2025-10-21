from flask import Flask, jsonify, request
import sqlite3
import pandas as pd
import os
import requests
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_API_URL = os.getenv("AIRTABLE_API_URL")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # folder where app.py is located

DB_FILE = os.path.join(BASE_DIR, "my_database.db")
EXCEL_FILE = os.path.join(BASE_DIR, "database.xlsx")

print("EXCEL_FILE path:", EXCEL_FILE)
print("File exists:", os.path.exists(EXCEL_FILE))



app = Flask(__name__)
CORS(app)

# ------------------- Helper Functions -------------------
def connect_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def query_db(query, args=(), one=False):
    conn = connect_db()
    cur = conn.execute(query, args)
    rows = cur.fetchall()
    conn.close()
    return (rows[0] if rows else None) if one else rows

# ------------------- Airtable Integration -------------------
def push_to_airtable(variant_name, mte_value):
    if not AIRTABLE_API_KEY or not AIRTABLE_API_URL:
        return  # Skip Airtable if keys not set
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {"records":[{"fields":{"Variant":variant_name,"MTE":mte_value}}]}
    try:
        response = requests.post(AIRTABLE_API_URL, headers=headers, json=data, timeout=10)
        if response.ok:
            print(f"Pushed {variant_name} → {mte_value} to Airtable")
        else:
            print(f"Airtable push failed: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Airtable error: {e}")

def fetch_from_airtable_all():
    if not AIRTABLE_API_KEY or not AIRTABLE_API_URL:
        return []
    headers = {"Authorization": f"Bearer {AIRTABLE_API_KEY}"}
    all_records = []
    url = AIRTABLE_API_URL
    while url:
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.ok:
                data = response.json()
                all_records.extend(data.get("records", []))
                offset = data.get("offset")
                url = AIRTABLE_API_URL + "?offset=" + offset if offset else None
            else:
                print("Failed to fetch from Airtable:", response.text)
                break
        except requests.exceptions.RequestException as e:
            print("Error fetching Airtable:", e)
            break
    return all_records

def sync_airtable_to_db():
    records = fetch_from_airtable_all()
    if not records:
        return
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    for rec in records:
        fields = rec.get("fields", {})
        variant = fields.get("Variant") or fields.get("variant") or "Unknown"
        mte = fields.get("MTE") or fields.get("mte") or 0
        try:
            mte = float(mte)
        except ValueError:
            mte = 0
        cursor.execute("""
            INSERT OR REPLACE INTO variants (variant_name, MTE)
            VALUES (?, ?)
        """, (variant, mte))
    conn.commit()
    conn.close()

# ------------------- Setup Database from Excel -------------------
def setup_database():
    if os.path.exists(DB_FILE):
        print("Using existing SQLite database.")
        return

    if not os.path.exists(EXCEL_FILE):
        raise FileNotFoundError(f"{EXCEL_FILE} not found in project folder.")

    print("Creating new SQLite database from Excel...")
    modules_df = pd.read_excel(EXCEL_FILE, sheet_name="modules")
    models_df = pd.read_excel(EXCEL_FILE, sheet_name="models")
    variants_df = pd.read_excel(EXCEL_FILE, sheet_name="variants")

    def clean_string(x):
        if isinstance(x, str):
            return x.strip().replace("\n","").replace("\r","")
        return str(x) if pd.notnull(x) else ""

    modules_df = modules_df.applymap(clean_string)
    models_df = models_df.applymap(clean_string)
    variants_df = variants_df.applymap(clean_string)

    conn = sqlite3.connect(DB_FILE)
    modules_df.to_sql("modules", conn, if_exists="replace", index=False)
    models_df.to_sql("models", conn, if_exists="replace", index=False)
    variants_df.to_sql("variants", conn, if_exists="replace", index=False)
    conn.close()
    print("Database created successfully.")

# ------------------- Flask Endpoints -------------------
@app.route("/")
def home():
    return jsonify({"message":"Flask API is running!"})

@app.route("/modules")
def get_modules():
    rows = query_db("SELECT module_name FROM modules")
    return jsonify([r["module_name"] for r in rows])

@app.route("/models/<module_name>")
def get_models_by_module(module_name):
    rows = query_db("""
        SELECT modules.module_name, models.model_name
        FROM models
        JOIN modules ON models.module_id = modules.module_id
        WHERE LOWER(TRIM(modules.module_name)) = LOWER(TRIM(?))
    """,[module_name])
    return jsonify([{"module_name":r["module_name"],"model_name":r["model_name"]} for r in rows])

@app.route("/variants/<model_name>")
def get_variants_by_model(model_name):
    rows = query_db("""
        SELECT modules.module_name, models.model_name, variants.variant_name, variants.MTE
        FROM variants
        JOIN models ON variants.model_id = models.model_id
        JOIN modules ON models.module_id = modules.module_id
        WHERE LOWER(TRIM(models.model_name)) = LOWER(TRIM(?))
    """,[model_name])
    output = []
    for r in rows:
        try:
            mte_val = float(r["MTE"]) if r["MTE"] else 0.0
        except:
            mte_val = 0.0
        output.append({
            "module_name": r["module_name"],
            "model_name": r["model_name"],
            "variant_name": r["variant_name"],
            "MTE": mte_val
        })
    return jsonify(output)

@app.route("/calculate_mte", methods=["POST"])
def calculate_mte():
    data = request.get_json()
    selected_variants = data.get("variants", [])
    if not selected_variants:
        return jsonify({"overall_mte":0.0, "variants":[]})

    placeholders = ",".join("?"*len(selected_variants))
    query = f"""
        SELECT modules.module_name, models.model_name, variants.variant_name, variants.MTE
        FROM variants
        JOIN models ON variants.model_id = models.model_id
        JOIN modules ON models.module_id = modules.module_id
        WHERE LOWER(TRIM(variants.variant_name)) IN ({placeholders})
    """
    rows = query_db(query, [v.lower().strip() for v in selected_variants])

    total_mte = 0.0
    output = []
    for r in rows:
        try:
            mte_val = float(r["MTE"]) if r["MTE"] else 0.0
        except:
            mte_val = 0.0
        output.append({
            "module_name": r["module_name"],
            "model_name": r["model_name"],
            "variant_name": r["variant_name"],
            "MTE": mte_val
        })
        total_mte += mte_val

        push_to_airtable(r["variant_name"], mte_val)  # optional

    return jsonify({"overall_mte": total_mte, "variants": output})

# ------------------- Run Flask -------------------
if __name__ == "__main__":
    setup_database()
    sync_airtable_to_db()  # optional
    app.run(debug=True)

print("EXCEL_FILE path:", EXCEL_FILE)
print("File exists:", os.path.exists(EXCEL_FILE))