# controller.py


class Controller:
    """三目並べのゲーム状態とルールを管理する。HTTP には依存しない。"""

    WIN_LINES = [
        (0, 1, 2), (3, 4, 5), (6, 7, 8),   # 横
        (0, 3, 6), (1, 4, 7), (2, 5, 8),   # 縦
        (0, 4, 8), (2, 4, 6),              # 斜め
    ]

    def __init__(self):
        self.reset()

    def reset(self):
        self.board = [" "] * 9
        self.turn = "X"          # 先手は X
        self.winner = None       # "X" / "O" / "draw" / None
        self.players = {}        # token -> "X" or "O"
        return {"ok": True, "message": "reset done"}

    def join(self):
        """プレイヤー登録。最大2人。トークンと割当てマークを返す。"""
        assigned = set(self.players.values())
        if "X" not in assigned:
            mark = "X"
        elif "O" not in assigned:
            mark = "O"
        else:
            return {"ok": False, "error": "game is full"}
        token = f"player-{mark}"
        self.players[token] = mark
        return {"ok": True, "player": token, "mark": mark}

    def move(self, token, pos):
        if not self._ready():
            return {"ok": False, "error": "waiting for players",
                    **self._snapshot()}
        if self.winner is not None:
            return {"ok": False, "error": "game already over",
                    **self._snapshot()}
        mark = self.players.get(token)
        if mark is None:
            return {"ok": False, "error": "unknown player"}
        if mark != self.turn:
            return {"ok": False, "error": "not your turn",
                    **self._snapshot()}
        if not isinstance(pos, int) or not (0 <= pos < 9):
            return {"ok": False, "error": "invalid position"}
        if self.board[pos] != " ":
            return {"ok": False, "error": "cell occupied"}

        self.board[pos] = mark
        self._check_end()
        if self.winner is None:
            self.turn = "O" if self.turn == "X" else "X"
        return {"ok": True, **self._snapshot()}

    def _ready(self):
        """2人揃ったか。"""
        return len(self.players) >= 2

    def _check_end(self):
        for a, b, c in self.WIN_LINES:
            if self.board[a] != " " and \
               self.board[a] == self.board[b] == self.board[c]:
                self.winner = self.board[a]
                return
        if all(cell != " " for cell in self.board):
            self.winner = "draw"

    def _snapshot(self):
        return {
            "board": self.board,
            "turn": self.turn,
            "winner": self.winner,
            "ready": self._ready(),
            "players": len(self.players),
        }

    def state(self):
        return {"ok": True, **self._snapshot()}
