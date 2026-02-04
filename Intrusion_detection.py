import requests
import subprocess
import time
import os
import PIL.Image
import google.generativeai as genai

# ==== CONFIGURATION ====
ESP32_IP = "10.12.171.72"   #  Replace with your ESP32 IP
STATUS_URL = f"http://{ESP32_IP}/status"
STREAM_URL = f"http://{ESP32_IP}/stream"
SAVE_DIR = "recordings"
FRAMES_DIR = "frames"
CHECK_INTERVAL = 2           # Seconds between ESP32 polls
GEMINI_API_KEY = "AIzaSyAH_34B14ctDj_Jn3IzUMol6BVB33-Yy-c"   # Replace with your Gemini API key

# Choose model: e.g., "gemini-2.5-pro" or "gemini-2.5-flash"
GENAI_MODEL_NAME = "gemini-2.5-pro"

# ==== TELEGRAM CONFIG ====
TELEGRAM_BOT_TOKEN = "7714595268:AAGktzNe4mvytZ8Hau2ICJL-muoTBkKcGiY"   # <-- Replace with your Telegram bot token
TELEGRAM_CHAT_ID = "5441262722"              #  Replace with your Telegram chat ID

# ==== SETUP ====
os.makedirs(SAVE_DIR, exist_ok=True)
os.makedirs(FRAMES_DIR, exist_ok=True)
genai.configure(api_key=GEMINI_API_KEY)

ffmpeg_process = None
last_motion_state = False

# ==============================================================
#  Telegram Notification
# ==============================================================
def send_telegram_message(text, video_path=None):
    """Send a text message and optional video to Telegram."""
    try:
        # 1️⃣ Send the summary text
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": text}
        )

        # 2️⃣ Optionally send the video
        if video_path and os.path.exists(video_path):
            with open(video_path, "rb") as video_file:
                requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo",
                    data={"chat_id": TELEGRAM_CHAT_ID},
                    files={"video": video_file}
                )

        print("📨 Telegram notification sent successfully.")

    except Exception as e:
        print(f"⚠️ Failed to send Telegram message: {e}")

# ==============================================================
# 🧩 1. Extract frames from video (every interval seconds)
# ==============================================================
def extract_frames(video_path, output_dir=FRAMES_DIR, interval=0.5):
    """Extract frames from a video every `interval` seconds."""
    try:
        # Clean old frames
        for f in os.listdir(output_dir):
            fp = os.path.join(output_dir, f)
            if os.path.isfile(fp):
                os.remove(fp)

        # Probe for duration
        probe = subprocess.run(
            ["ffprobe", "-v", "error",
             "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1",
             video_path],
            capture_output=True, text=True
        )
        duration = float(probe.stdout.strip() or 0)
        if duration < interval:
            interval = max(0.1, duration / 2)

        print(f"🎬 Extracting frames from {video_path} every {interval}s...")
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", video_path,
                "-vf", f"fps=1/{interval}",
                os.path.join(output_dir, "frame_%03d.jpg"),
                "-hide_banner", "-loglevel", "error"
            ],
            check=True
        )

        frames = [os.path.join(output_dir, f)
                  for f in sorted(os.listdir(output_dir))
                  if f.lower().endswith(".jpg")]
        print(f"✅ Extracted {len(frames)} frame(s)")
        return frames
    except Exception as e:
        print(f"❌ Frame extraction failed: {e}")
        return []

# ==============================================================
# 🧠 2. Summarize frames using Gemini model
# ==============================================================
def summarize_video_frames(frame_paths):
    """Use the Gemini model to summarize a sequence of images."""
    try:
        if not frame_paths:
            return "⚠️ No frames extracted for summarization."

        max_frames = 6
        frame_paths = frame_paths[:max_frames]

        images = []
        for fp in frame_paths:
            img = PIL.Image.open(fp)
            images.append(img.copy())
            img.close()

        model = genai.GenerativeModel(GENAI_MODEL_NAME)

        prompt = (
            "You are a visual scene summarizer. "
            "Describe clearly what happens in these images, "
            "as if summarizing a short motion-detection video. "
            "Keep it under 4 lines."
        )

        print(f"🧠 Sending {len(images)} frames to Gemini model '{GENAI_MODEL_NAME}'...")
        response = model.generate_content(contents=[prompt] + images)
        summary = response.text.strip()
        print("✅ Gemini summary received.")
        return summary
    except Exception as e:
        print(f"❌ Gemini summarization failed: {e}")
        return f"Error: {e}"

# ==============================================================
# 🎞️ 3. Stop recording & summarise
# ==============================================================
def stop_recording_and_summarize():
    """Stop ffmpeg process and summarise the last video."""
    global ffmpeg_process
    if ffmpeg_process:
        print("🛑 No motion → stopping recording...")
        ffmpeg_process.terminate()
        try:
            ffmpeg_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            ffmpeg_process.kill()
            ffmpeg_process.wait()

        ffmpeg_process = None
        print("✅ Recording stopped successfully.")

        recorded_files = [
            os.path.join(SAVE_DIR, f) for f in os.listdir(SAVE_DIR)
            if f.lower().endswith(".mp4")
        ]
        if not recorded_files:
            print("⚠️ No recorded files found.")
            return
        latest_file = max(recorded_files, key=os.path.getctime)

        frames = extract_frames(latest_file)
        summary = summarize_video_frames(frames)

        summary_file = latest_file.replace(".mp4", "_summary.txt")
        with open(summary_file, "w", encoding="utf-8") as f:
            f.write(summary)

        print(f"📝 Summary saved to {summary_file}")
        print("\n=== 🎞 VIDEO SUMMARY ===\n" + summary + "\n=========================\n")

        # 📩 Send Telegram notification
        notification_text = f"📹 Motion detected and processed!\n\nSummary:\n{summary}"
        send_telegram_message(notification_text, latest_file)

# ==============================================================
# 🔁 4. Main monitoring loop
# ==============================================================
print("🚀 Starting ESP32 video monitor + Gemini summarizer…\n")

while True:
    try:
        # --- Get ESP32 status ---
        try:
            r = requests.get(STATUS_URL, timeout=5)
            data = r.json()
        except Exception as e:
            print(f"⚠️ ESP32 communication issue: {e}")
            data = {}

        stream_enabled = data.get("streamEnabled", False)
        print("📡 ESP32 status:", data)

        # --- Detect motion changes ---
        if stream_enabled and not last_motion_state:
            filename = os.path.join(SAVE_DIR, f"recording_{int(time.time())}.mp4")
            print(f"🚀 Motion detected → starting recording to {filename}")
            ffmpeg_process = subprocess.Popen(
                ["ffmpeg", "-y", "-i", STREAM_URL, "-c", "copy", filename],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            last_motion_state = True

        elif (not stream_enabled) and last_motion_state:
            last_motion_state = False
            stop_recording_and_summarize()

    except Exception as e:
        print(f"⚠️ Error in main loop: {e}")
        if ffmpeg_process:
            try:
                ffmpeg_process.terminate()
                ffmpeg_process.wait(timeout=5)
            except Exception:
                pass
            ffmpeg_process = None
            last_motion_state = False

    time.sleep(CHECK_INTERVAL)
