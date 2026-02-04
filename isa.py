
from flask import Flask, request, Response
import cv2
import numpy as np
import datetime
import os

app = Flask(__name__)

out = None
recording = False
frame_size = (320, 240)   # must match ESP32 frame size
fps = 8                   # matches Arduino delay

output_dir = "recordings"
os.makedirs(output_dir, exist_ok=True)

@app.route('/upload', methods=['POST'])
def upload_frame():
    global out, recording

    nparr = np.frombuffer(request.data, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if frame is None:
        return Response("Invalid frame", status=400)

    if not recording:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(output_dir, f"video_{timestamp}.avi")
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        out = cv2.VideoWriter(filename, fourcc, fps, frame_size)
        recording = True
        print(f"🎥 Started new recording: {filename}")

    if out is not None:
        frame_resized = cv2.resize(frame, frame_size)
        out.write(frame_resized)

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

