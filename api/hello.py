from flask import Flask, request, jsonify
from flask_cors import CORS
from email.mime.text import MIMEText
import smtplib, random, time, os

app = Flask(__name__)
CORS(app)

# === Config / Secrets ===
EMAIL_ADDRESS = "orignallinks@gmail.com"
EMAIL_PASSWORD = "jtbyfkneamirfgvo"  # Gmail App Password (not real password in prod)

# === Verification Settings ===
codes = {}              # In-memory storage
RATE_LIMIT = {}         # Prevent spamming
CODE_TTL = 300          # 5 minutes
MAX_TRIES = 5
RESEND_INTERVAL = 30    # Seconds between sends

# === Routes ===
@app.route("/api/send-code", methods=["POST"])
def send_code():
    data = request.json
    email = data.get("email")
    if not email:
        return jsonify({"success": False, "message": "Email required"}), 400

    now = time.time()

    # Rate limiting
    if email in RATE_LIMIT and now - RATE_LIMIT[email] < RESEND_INTERVAL:
        return jsonify({"success": False, "message": "Wait before requesting again"}), 429

    # Check resend flag
    is_resend = request.args.get("resend") == "true"

    if not is_resend:
        existing = codes.get(email)
        if existing and now < existing["expires"]:
            return jsonify({
                "success": False,
                "message": "Code already sent",
                "already_sent": True,
                "expires_in": int(existing["expires"] - now)
            })

    # Generate code
    code = str(random.randint(100000, 999999))
    codes[email] = {
        "code": code,
        "expires": now + CODE_TTL,
        "tries": 0
    }
    RATE_LIMIT[email] = now

    # Email Template
    html = f"""
    <html>
      <body>
        <h2>Email Verification</h2>
        <p>Your verification code:</p>
        <div style="font-size:24px; font-weight:bold; color:#007eff;">{code}</div>
        <p>This code expires in 5 minutes.</p>
      </body>
    </html>
    """

    try:
        msg = MIMEText(html, "html")
        msg["Subject"] = "Verify Your Email"
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = email

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()

        return jsonify({"success": True, "message": "Verification code sent"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to send email: {str(e)}"})


@app.route("/api/verify-code", methods=["POST"])
def verify_code():
    data = request.json
    email = data.get("email")
    code = data.get("code")
    now = time.time()

    entry = codes.get(email)
    if not entry:
        return jsonify({"success": False, "message": "No code found"}), 400

    if now > entry["expires"]:
        del codes[email]
        return jsonify({"success": False, "message": "Code expired"}), 400

    if entry["tries"] >= MAX_TRIES:
        del codes[email]
        return jsonify({"success": False, "message": "Too many attempts"}), 400

    if code != entry["code"]:
        codes[email]["tries"] += 1
        return jsonify({"success": False, "message": "Incorrect code"}), 400

    del codes[email]
    return jsonify({"success": True, "message": "Email verified successfully"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
