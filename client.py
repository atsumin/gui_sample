# client.py
import json
import threading
import tkinter as tk
from tkinter import messagebox, ttk
import urllib.error
import urllib.request


class ApiClient:
    """サーバとの HTTP 通信を担当する。"""

    def __init__(self, base_url, token=None):
        self.base_url = base_url.rstrip("/")
        self.token = token or None

    def _headers(self):
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
            h["X-Access-Token"] = self.token
        return h

    def _request(self, path, method, payload=None):
        data = (json.dumps(payload).encode("utf-8")
                if payload is not None else None)
        req = urllib.request.Request(
            self.base_url + path, data=data,
            headers=self._headers(), method=method)
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                return json.loads(e.read().decode("utf-8"))
            except Exception:
                return {"ok": False, "error": f"HTTP {e.code}"}
        except urllib.error.URLError as e:
            return {"ok": False, "error": f"connection failed: {e.reason}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def join(self):
        return self._request("/join", "POST", {})

    def move(self, token, pos):
        return self._request("/move", "POST", {"player": token, "pos": pos})

    def state(self):
        return self._request("/state", "GET")


class TicTacToeGUI:
    POLL_MS = 1000

    def __init__(self, root):
        self.root = root
        self.root.title("三目並べ クライアント")
        self.api = None
        self.token = None
        self.mark = None
        self.polling = False

        self._build_setup_frame()
        self._build_game_frame()
        self._show_setup()

    # ---------- 初期設定画面 ----------
    def _build_setup_frame(self):
        self.setup = ttk.Frame(self.root, padding=16)

        ttk.Label(self.setup, text="接続先 URL:").grid(
            row=0, column=0, sticky="w", pady=4)
        self.url_var = tk.StringVar(value="http://127.0.0.1:8000")
        ttk.Entry(self.setup, textvariable=self.url_var, width=32).grid(
            row=0, column=1, pady=4)

        ttk.Label(self.setup, text="Access Token:").grid(
            row=1, column=0, sticky="w", pady=4)
        self.token_var = tk.StringVar(value="")
        ttk.Entry(self.setup, textvariable=self.token_var, width=32,
                  show="*").grid(row=1, column=1, pady=4)

        ttk.Button(self.setup, text="接続して参加",
                   command=self.on_connect).grid(
            row=2, column=0, columnspan=2, pady=(12, 0))

    # ---------- ゲーム画面 ----------
    def _build_game_frame(self):
        self.game = ttk.Frame(self.root, padding=16)

        self.status = tk.StringVar(value="")
        ttk.Label(self.game, textvariable=self.status,
                  font=("", 12, "bold")).grid(
            row=0, column=0, columnspan=3, pady=(0, 10))

        self.cells = []
        for i in range(9):
            b = tk.Button(self.game, text=" ", width=4, height=2,
                          font=("", 24),
                          command=lambda p=i: self.on_cell(p))
            b.grid(row=1 + i // 3, column=i % 3, padx=2, pady=2)
            self.cells.append(b)

        ttk.Button(self.game, text="切断して設定に戻る",
                   command=self.on_disconnect).grid(
            row=4, column=0, columnspan=3, pady=(12, 0))

    def _show_setup(self):
        self.game.pack_forget()
        self.setup.pack()

    def _show_game(self):
        self.setup.pack_forget()
        self.game.pack()

    # ---------- イベント ----------
    def on_connect(self):
        url = self.url_var.get().strip()
        token = self.token_var.get().strip()
        if not url:
            messagebox.showerror("エラー", "URL を入力してください。")
            return
        self.api = ApiClient(url, token)
        res = self.api.join()
        if not res.get("ok"):
            messagebox.showerror("接続失敗", res.get("error", "unknown"))
            self.api = None
            return
        self.token = res["player"]
        self.mark = res["mark"]
        self._show_game()
        self.status.set(f"あなたのマークは [{self.mark}] です。")
        self.polling = True
        self.refresh()

    def on_disconnect(self):
        self.polling = False
        self.api = None
        self.token = None
        self.mark = None
        for b in self.cells:
            b["text"] = " "
            b["state"] = "normal"
        self._show_setup()

    def on_cell(self, pos):
        if not self.api:
            return
        res = self.api.move(self.token, pos)
        if not res.get("ok"):
            self.status.set("エラー: " + res.get("error", ""))
        self.refresh_once()

    # ---------- 状態更新 ----------
    def refresh(self):
        """定期ポーリング。"""
        if not self.polling:
            return
        self.refresh_once()
        self.root.after(self.POLL_MS, self.refresh)

    def refresh_once(self):
        if not self.api:
            return
        # ネットワーク処理は別スレッドで行い UI をブロックしない
        threading.Thread(target=self._fetch_and_update, daemon=True).start()

    def _fetch_and_update(self):
        st = self.api.state()
        self.root.after(0, lambda: self._apply_state(st))

    def _apply_state(self, st):
        if not st.get("ok"):
            self.status.set("エラー: " + st.get("error", ""))
            return

        board = st["board"]
        ready = st.get("ready", False)
        winner = st["winner"]

        # 盤面の表示は常に更新
        for i, c in enumerate(board):
            self.cells[i]["text"] = c if c != " " else " "

        # 2人揃っていない間は全マスを無効化して待機
        if not ready:
            self._disable_all()
            count = st.get("players", 0)
            self.status.set(
                f"対戦相手の参加を待っています...（{count}/2 人接続中）")
            return

        # ここから先は2人揃っている状態
        if winner == "draw":
            self.status.set("引き分けです。")
            self._disable_all()
            return
        if winner:
            won = (winner == self.mark)
            self.status.set(
                f"勝者: {winner} "
                + ("（あなたの勝ち！）" if won else "（あなたの負け）"))
            self._disable_all()
            return

        # 対局中：自分の手番なら空きマスのみ有効化
        my_turn = (st["turn"] == self.mark)
        for i, c in enumerate(board):
            self.cells[i]["state"] = (
                "normal" if (my_turn and c == " ") else "disabled")

        if my_turn:
            self.status.set(f"あなた [{self.mark}] の手番です。")
        else:
            self.status.set(f"相手 [{st['turn']}] の手番を待っています...")

    def _disable_all(self):
        for b in self.cells:
            b["state"] = "disabled"


def main():
    root = tk.Tk()
    TicTacToeGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
