"""
web_stub.py ─ keep-alive server + Telegram polling bot
"""
import os, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# ---- 1. tiny web server for Render health check ----
class Ping(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_http():
    port = int(os.environ.get("PORT", 10000))  # Render 注入 $PORT
    HTTPServer(("", port), Ping).serve_forever()

threading.Thread(target=run_http, daemon=True).start()

# ---- 2. start your original bot (long-polling) ----
import main  # main.py 內已有 main() 或 run_polling()

# 如果 main.py 一進 import 就跑 polling，這行足夠；
# 否則把 main.main() 抽成函式後在這裡呼叫：
# main.main()
