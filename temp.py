from flask import Flask, request, jsonify
import os
import datetime

app = Flask(__name__)

# Create uploads directory if not exists
UPLOAD_FOLDER = "uploads"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route("/")
def home():
    return "✅ ESP32-CAM Flask Server is Running!"

@app.route("/upload", methods=["POST"])
def upload_file():
    try:
        # Generate unique filename with timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"photo_{timestamp}.jpg"
        filepath = os.path.join(UPLOAD_FOLDER, filename)

        # Save uploaded image
        with open(filepath, "wb") as f:
            f.write(request.data)

        print(f"[INFO] Saved: {filepath}")
        return jsonify({"status": "success", "filename": filename}), 200

    except Exception as e:
        print(f"[ERROR] {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    # Run server on all available IPs, port 5000
    app.run(host="0.0.0.0", port=5000, debug=True)
