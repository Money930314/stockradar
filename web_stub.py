"""
web_stub.py
-----------
1. 啟動一個極簡 HTTP 伺服器，對 GET / 與 HEAD / 皆回 200 OK
   → 滿足 Render Web Service 健康檢查
2. 同時匯入並執行 main.run_bot()（你的 long-polling Telegram Bot）
"""

import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import main  # ⬅️ main.py 內要有 run_bot() 函式，見下節

# ---------- Tiny HTTP server ----------
class Ping(BaseHTTPRequestHandler):
    def _ok(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        self._ok()
        self.wfile.write(b"OK")

    def do_HEAD(self):
        self._ok()


def run_http():
    port = int(os.environ.get("PORT", 10000))  # Render 會注入 $PORT
    HTTPServer(("", port), Ping).serve_forever()


threading.Thread(target=run_http, daemon=True).start()

# ---------- Start Telegram Bot ----------
# main.py 中新增 run_bot()，專責 run_polling()
main.run_bot()
