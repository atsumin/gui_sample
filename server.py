# server.py
import hmac
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from controller import Controller

controller = Controller()
lock = threading.Lock()

# 環境変数 ACCESS_TOKEN で認証トークンを設定。
# 未設定なら認証なし（誰でも接続可）として動作する。
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def _authorized(self):
        """ACCESS_TOKEN が設定されている場合のみ認証を要求する。
        Authorization: Bearer <token> または X-Access-Token ヘッダを受理。
        比較は hmac.compare_digest で定数時間に行う。"""
        if not ACCESS_TOKEN:
            return True
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[len("Bearer "):].strip()
            if hmac.compare_digest(token, ACCESS_TOKEN):
                return True
        header_token = self.headers.get("X-Access-Token", "").strip()
        if header_token and hmac.compare_digest(header_token, ACCESS_TOKEN):
            return True
        return False

    def _guard(self):
        """認証チェック。失敗時は 401 を返して False。"""
        if not self._authorized():
            self._send(401, {"ok": False, "error": "unauthorized"})
            return False
        return True

    def do_POST(self):
        if not self._guard():
            return
        if self.path == "/join":
            with lock:
                result = controller.join()
            code = 200 if result.get("ok") else 409
            self._send(code, result)
        elif self.path == "/move":
            data = self._read_json()
            with lock:
                result = controller.move(data.get("player"), data.get("pos"))
            code = 200 if result.get("ok") else 400
            self._send(code, result)
        elif self.path == "/reset":
            with lock:
                result = controller.reset()
            self._send(200, result)
        else:
            self._send(404, {"ok": False, "error": "not found"})

    def do_GET(self):
        if not self._guard():
            return
        # /state?player=<token> で自分の部屋の状態を取得
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        if parsed.path == "/state":
            qs = parse_qs(parsed.query)
            token = (qs.get("player", [None])[0]
                     or self.headers.get("X-Player-Token"))
            with lock:
                result = controller.state(token)
            self._send(200, result)
        else:
            self._send(404, {"ok": False, "error": "not found"})

    def log_message(self, fmt, *args):
        pass  # ログ抑制（必要なら有効化）


def main(host="0.0.0.0", port=None):
    # 環境変数 PORT を優先。未設定なら 8000。
    if port is None:
        try:
            port = int(os.environ.get("PORT", "8000"))
        except ValueError:
            print("警告: PORT が不正な値のため 8000 を使用します。")
            port = 8000
    httpd = ThreadingHTTPServer((host, port), Handler)
    mode = "認証あり" if ACCESS_TOKEN else "認証なし（ACCESS_TOKEN 未設定）"
    print(f"Server running at http://{host}:{port}  [{mode}]")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()


if __name__ == "__main__":
    main()
