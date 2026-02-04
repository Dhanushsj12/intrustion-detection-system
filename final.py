from flask import Flask, request, Response
import os
import tarfile
import tempfile
import datetime
import cv2
import numpy as np

app = Flask(__name__)
output_dir = "recordings"
os.makedirs(output_dir, exist_ok=True)

@app.route('/upload_tar', methods=['POST'])
def upload_tar():
    # Save incoming body to a temporary tar file
    try:
        tmpdir = tempfile.mkdtemp(prefix="esp_recv_")
        tar_path = os.path.join(tmpdir, "upload.tar")
        with open(tar_path, "wb") as f:
            f.write(request.data)
        # Extract tar
        try:
            with tarfile.open(tar_path, "r:") as tar:
                tar.extractall(path=tmpdir)
        except Exception as e:
            print("❌ Failed to extract tar:", e)
            return Response("Bad tar", status=400)

        # Find all jpeg files extracted (recursively)
        jpeg_files = []
        for root, dirs, files in os.walk(tmpdir):
            for name in files:
                lname = name.lower()
                if lname.endswith('.jpg') or lname.endswith('.jpeg'):
                    jpeg_files.append(os.path.join(root, name))

        if not jpeg_files:
            print("⚠️ No jpeg files found in tar")
            return Response("No frames", status=400)

        # Sort files by filename (assumes frame_xxxxxx.jpg names)
        jpeg_files.sort()

        # Build video filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_fname = os.path.join(output_dir, f"video_{timestamp}.avi")
        frame_size = (320, 240)  # must match ESP32 QVGA
        fps = 8

        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        out = cv2.VideoWriter(out_fname, fourcc, fps, frame_size)

        for jf in jpeg_files:
            img = cv2.imread(jf)
            if img is None:
                print("⚠️ Skipping unreadable frame:", jf)
                continue
            # resize to frame_size to avoid mismatch
            frame = cv2.resize(img, frame_size)
            out.write(frame)

        out.release()
        print(f"✅ Video written: {out_fname}")

        # cleanup tmpdir (optional)
        try:
            # remove extracted files and tar
            import shutil
            shutil.rmtree(tmpdir)
        except Exception as e:
            print("⚠️ Cleanup failed:", e)

        return Response("OK", status=200)
    except Exception as e:
        print("❌ Exception in upload:", e)
        return Response("Server error", status=500)

if __name__ == '__main__':
    # listen on all interfaces
    app.run(host='0.0.0.0', port=8000)
