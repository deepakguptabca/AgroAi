from flask import Flask, request, jsonify, render_template
import requests
import google.generativeai as genai
from dotenv import load_dotenv
import os
import json
import csv
from datetime import datetime, timezone, timedelta

# Load environment variables
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

app = Flask(__name__)

HISTORY_FILE = "hist.txt"
ESP_IP = os.getenv("ESP_IP")
DATA_CSV = "esp_data.csv"
LAST_PUMP = None
IST = timezone(timedelta(hours=5, minutes=30))


# ------------------------
# Helper Functions
# ------------------------
def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def save_to_history(user_msg, ai_reply):
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"User: {user_msg}\n")
        f.write(f"AI: {ai_reply}\n\n")


def clear_history():
    open(HISTORY_FILE, "w").close()


# ------------------------
# Routes
# ------------------------
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        user_msg = data.get("message")

        if not user_msg:
            return jsonify({"error": "Message required"}), 400

        history = load_history()

        # --- fetch current field data from ESP (handle missing scheme/IP) ---
        field_data = {}
        try:
            if ESP_IP:
                esp_url = ESP_IP if ESP_IP.startswith("http") else f"http://{ESP_IP}"
                resp = requests.get(esp_url, timeout=2)
                field_data = resp.json()
        except Exception:
            field_data = {"error": "ESP not reachable"}

        # include JSON-formatted field data in the prompt
        prompt = f"""
        You are an intelligent farming assistant for Indian farmers.

        Previous conversation:
        {history}

        User's new message:
        {user_msg}

        User's field data:
        {json.dumps(field_data)}

        Reply in a short, friendly, and helpful way.
        only If user asks for about field status, provide suggestions based on the field data.

        IMPORTANT: Return the reply as plain text without any Markdown, asterisks (*), backticks (`), underscores (_), or other formatting tokens.
        """

        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        ai_reply = response.text

        save_to_history(user_msg, ai_reply)
        return jsonify({"reply": ai_reply})

    except Exception as e:
        print("Error:", e)
        return jsonify({"error": "AI request failed", "details": str(e)}), 500


@app.route("/clear", methods=["POST"])
def clear():
    clear_history()
    return jsonify({"status": "Chat cleared"})


@app.route("/getdata")
def get_data():
    try:
        if not ESP_IP:
            return jsonify({"error": "ESP_IP not configured"}), 400

        esp_url = ESP_IP if ESP_IP.startswith("http") else f"http://{ESP_IP}"
        r = requests.get(esp_url, timeout=2)
        field_data = r.json()

        # Save received field data to CSV only when pump reports 'on' or 'off',
        # and only when pump state changes from last logged state.
        try:
            pump_val = field_data.get("pump")
            pump_str = str(pump_val).lower() if pump_val is not None else None
            if pump_str in ("on", "off"):
                global LAST_PUMP
                if pump_str != LAST_PUMP:
                    row = {
                        "timestamp": datetime.now(IST).isoformat(),
                        "soil": field_data.get("soil"),
                        "humidity": field_data.get("humidity"),
                        "temperature": field_data.get("temperature"),
                        "pump": pump_str,
                    }

                    file_exists = os.path.exists(DATA_CSV)
                    with open(DATA_CSV, "a", newline="", encoding="utf-8") as csvfile:
                        writer = csv.DictWriter(
                            csvfile,
                            fieldnames=[
                                "timestamp",
                                "soil",
                                "humidity",
                                "temperature",
                                "pump",
                            ],
                        )
                        if not file_exists:
                            writer.writeheader()
                        writer.writerow(row)

                    LAST_PUMP = pump_str
        except Exception:
            pass

        return jsonify(field_data)
    except:
        return jsonify({"error": "ESP not reachable"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
