from flask import Flask, request, jsonify, render_template
import google.generativeai as genai
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

app = Flask(__name__)

HISTORY_FILE = "hist.txt"

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

        prompt = f"""
        You are an intelligent farming assistant for Indian farmers.

        Previous conversation:
        {history}

        User's new message:
        {user_msg}

        Reply in a short, friendly, and helpful way.
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


if __name__ == "__main__":
    app.run(debug=True)
