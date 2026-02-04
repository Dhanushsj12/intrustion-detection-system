from flask import Flask, request, Response
import cv2
import numpy as np
import datetime
import os

app = Flask(__name__)

# Globals
out = None
recording = False
frame_size = (640, 480)   # Adjust if you change ESP32 resolution
fps = 10                  # Assumed FPS (ESP32 sends ~10fps)

output_dir = "recordings"
os.makedirs(output_dir, exist_ok=True)

@app.route('/upload', methods=['POST'])
def upload_frame():
    global out, recording

    # Read frame
    nparr = np.frombuffer(request.data, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if frame is None:
        return Response("Invalid frame", status=400)

    # Start new recording if not already
    if not recording:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(output_dir, f"video_{timestamp}.avi")
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        out = cv2.VideoWriter(filename, fourcc, fps, frame_size)
        recording = True
        print(f"🎥 Started new recording: {filename}")

    # Write frame
    if out is not None:
        out.write(frame)

    return Response("OK", status=200)


@app.route('/stop', methods=['GET'])
def stop_recording():
    global out, recording

    if recording and out is not None:
        out.release()
        out = None
        recording = False
        print("✅ Recording stopped & file saved.")

    return Response("Stopped", status=200)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
