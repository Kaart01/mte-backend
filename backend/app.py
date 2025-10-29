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
DB_FILE = os.path.join(BASE_DIR, "mte_data.db")
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

# ------------------ Airtable Sync ------------------
def push_to_airtable(variants, overall_mte):
    """Push all variants + overall MTE to Airtable"""
    if not AIRTABLE_API_KEY or not AIRTABLE_API_URL:
        print("❌ Missing Airtable API key or URL.")
        return False

    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }

    # prepare records
    records = [{"fields": {"Variant": v["variant_name"], "MTE": v["MTE"]}} for v in variants]

    # ✅ Optionally also push total MTE as a special record
    records.append({"fields": {"Variant": "Overall MTE", "MTE": overall_mte}})

    payload = {"records": records}
    print(f"📤 Sending data to Airtable: {AIRTABLE_API_URL}")

    try:
        response = requests.post(AIRTABLE_API_URL, headers=headers, json=payload, timeout=10)
        print(f"📥 Airtable Response: {response.status_code} {response.text}")
        return response.status_code in [200, 201]
    except Exception as e:
        print(f"❌ Airtable sync error: {e}")
        return False

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
@app.route("/mte-calculate", methods=["POST"])
def calculate_mte():
    data = request.get_json()
    variants = data.get("variants", [])

    if not variants:
        return jsonify({"error": "No variants provided"}), 400

    variant_names = [v.get("variant_name") for v in variants]
    placeholders = ",".join("?" * len(variant_names))
    rows = query_db(f"SELECT variant_name, MTE FROM variants WHERE variant_name IN ({placeholders})", variant_names)

    total_mte = sum(float(r["MTE"]) for r in rows)
    results = [{"variant_name": r["variant_name"], "MTE": float(r["MTE"])} for r in rows]
    overall_mte = round(total_mte, 3)

    # Push automatically to Airtable (only Variant + MTE)
    success = push_to_airtable(results, overall_mte)

    return jsonify({
        "overall_mte": overall_mte,
        "variants": results,
        "airtable_sync": "✅ Success" if success else "⚠️ Failed"
    })

# ------------------ Serve Frontend ------------------
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, "index.html")

# ------------------ Main ------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)








