from flask import Flask, jsonify, request, send_from_directory
import sqlite3
import pandas as pd
import os
from flask_cors import CORS
import requests
from dotenv import load_dotenv

# ------------------ Load Environment ------------------
load_dotenv()
AIRTABLE_API_KEY = os.environ.get("AIRTABLE_API_KEY")
AIRTABLE_API_URL = os.environ.get("AIRTABLE_API_URL")

# ------------------ Paths ------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "my_database.db")
EXCEL_FILE = os.path.join(BASE_DIR, "database.xlsx")

# ------------------ Flask App ------------------
app = Flask(__name__, static_folder="static")
CORS(app, origins="*")

# ------------------ DB Helpers ------------------
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

# ------------------ Airtable Sync (optional) ------------------
def push_to_airtable(variant_name, mte_value):
    if not AIRTABLE_API_KEY or not AIRTABLE_API_URL:
        print("⚠️ Airtable credentials not set.")
        return

    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {"records": [{"fields": {"Variant": variant_name, "MTE": mte_value}}]}
    try:
        r = requests.post(AIRTABLE_API_URL, headers=headers, json=data, timeout=10)
        print(f"✅ Pushed to Airtable: {variant_name} = {mte_value} ({r.status_code})")
    except Exception as e:
        print(f"❌ Airtable sync failed: {e}")

# ------------------ Setup DB from Excel ------------------
def setup_database():
    if os.path.exists(DB_FILE):
        print("✅ Using existing database.")
        return
    if not os.path.exists(EXCEL_FILE):
        raise FileNotFoundError("❌ Excel file not found.")

    print("⚙️ Creating DB from Excel...")
    modules_df = pd.read_excel(EXCEL_FILE, sheet_name="modules").fillna("")
    models_df = pd.read_excel(EXCEL_FILE, sheet_name="models").fillna("")
    variants_df = pd.read_excel(EXCEL_FILE, sheet_name="variants").fillna("")

    conn = sqlite3.connect(DB_FILE)
    modules_df.to_sql("modules", conn, if_exists="replace", index=False)
    models_df.to_sql("models", conn, if_exists="replace", index=False)
    variants_df.to_sql("variants", conn, if_exists="replace", index=False)
    conn.close()

    print("✅ Database created successfully from Excel.")

setup_database()

# ------------------ API Endpoints ------------------
@app.route("/modules")
def get_modules():
    rows = query_db("SELECT module_name FROM modules")
    return jsonify([r["module_name"] for r in rows])

@app.route("/models/<module_name>")
def get_models(module_name):
    rows = query_db("""
        SELECT m.model_name
        FROM models m
        JOIN modules mo ON m.module_id = mo.module_id
        WHERE LOWER(TRIM(mo.module_name))=LOWER(TRIM(?))
    """, [module_name])
    return jsonify([r["model_name"] for r in rows])

@app.route("/variants/<model_name>")
def get_variants(model_name):
    rows = query_db("""
        SELECT v.variant_name, v.MTE
        FROM variants v
        JOIN models m ON v.model_id = m.model_id
        WHERE LOWER(TRIM(m.model_name))=LOWER(TRIM(?))
    """, [model_name])
    return jsonify([
        {"variant_name": r["variant_name"], "MTE": float(r["MTE"])} for r in rows
    ])

@app.route("/calculate_mte", methods=["POST"])
def calculate_mte():
    data = request.get_json()
    variants = data.get("variants", [])
    if not variants:
        return jsonify({"overall_mte": 0.0, "variants": []})

    placeholders = ",".join("?" * len(variants))
    rows = query_db(f"""
        SELECT v.variant_name, v.MTE
        FROM variants v
        WHERE LOWER(TRIM(v.variant_name)) IN ({placeholders})
    """, [v.lower() for v in variants])

    total = sum(float(r["MTE"]) for r in rows)
    variant_data = [
        {"variant_name": r["variant_name"], "MTE": float(r["MTE"])} for r in rows
    ]

    # ---- Push each variant to Airtable ----
    for r in rows:
        push_to_airtable(r["variant_name"], float(r["MTE"]))

    # ---- Also push overall MTE as one record ----
    push_to_airtable("Overall MTE", total)

    return jsonify({
        "overall_mte": total,
        "variants": variant_data
    })


@app.route("/test_airtable")
def test_airtable():
    api_key = os.getenv("AIRTABLE_API_KEY")
    api_url = os.getenv("AIRTABLE_API_URL")

    if not api_key or not api_url:
        return jsonify({"status": "error", "message": "Missing API key or URL"}), 500

    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        response = requests.get(api_url, headers=headers)
        if response.status_code == 200:
            return jsonify({"status": "success", "message": "Connected to Airtable!"})
        else:
            return jsonify({
                "status": "error",
                "message": f"Airtable returned {response.status_code}: {response.text}"
            }), response.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500



# ------------------ Serve Frontend ------------------
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    """Serve the frontend (index.html and assets)"""
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, "index.html")


# ------------------ Main ------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

