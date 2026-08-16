import os
import sys

os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["PYTHONWARNINGS"] = "ignore"
os.environ["ABSL_LOG_LEVEL"] = "3"
os.environ["GLOG_minloglevel"] = "3"

import time
import subprocess
import webbrowser
import urllib.request
import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

class NoCacheHTTPRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, format, *args):
        pass

def start_backend():
    backend_script = os.path.join(BASE_DIR, "backend", "main.py")
    env = os.environ.copy()
    env["TF_ENABLE_ONEDNN_OPTS"] = "0"
    env["TF_CPP_MIN_LOG_LEVEL"] = "3"
    env["PYTHONWARNINGS"] = "ignore"
    env["ABSL_LOG_LEVEL"] = "3"
    env["GLOG_minloglevel"] = "3"
    subprocess.run(
        [sys.executable, backend_script],
        env=env
    )


def start_frontend_server():
    os.chdir(FRONTEND_DIR)
    server_address = ('', 3000)
    httpd = HTTPServer(server_address, NoCacheHTTPRequestHandler)
    httpd.serve_forever()

def check_url(url, timeout=1):
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return resp.read()
    except Exception:
        return None
    return None

if __name__ == "__main__":
    frontend_thread = threading.Thread(target=start_frontend_server, daemon=True)
    frontend_thread.start()

    backend_thread = threading.Thread(target=start_backend, daemon=True)
    backend_thread.start()

    frontend_ready = False
    backend_ready = False
    whisper_ready = False

    while not (frontend_ready and backend_ready and whisper_ready):
        if not frontend_ready:
            res = check_url("http://localhost:3000")
            if res is not None:
                frontend_ready = True
                print("frontend running")

        if not backend_ready or not whisper_ready:
            res = check_url("http://localhost:8000/api/health")
            if res:
                try:
                    data = json.loads(res.decode('utf-8'))
                    if data.get("backend") and not backend_ready:
                        backend_ready = True
                        print("backend running")
                    if data.get("whisper") and not whisper_ready:
                        whisper_ready = True
                        print("whisper running")
                except Exception:
                    pass
        time.sleep(0.5)

    launch_time = int(time.time())
    webbrowser.open(f"http://localhost:3000?fresh_launch={launch_time}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

