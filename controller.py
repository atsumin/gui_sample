# controller.py
import secrets


class Game:
    """1つの対戦（2人）の盤面とルールを管理する。"""

    WIN_LINES = [
        (0, 1, 2), (3, 4, 5), (6, 7, 8),   # 横
        (0, 3, 6), (1, 4, 7), (2, 5, 8),   # 縦
        (0, 4, 8), (2, 4, 6),              # 斜め
    ]

    def __init__(self, game_id):
        self.id = game_id
        self.board = [" "] * 9
        self.turn = "X"          # 先手は X
        self.winner = None       # "X" / "O" / "draw" / None
        self.players = {}        # token -> "X" or "O"

    def add_player(self, token):
        """空いているマークを割当てる。満員なら None。"""
        assigned = set(self.players.values())
        if "X" not in assigned:
            mark = "X"
        elif "O" not in assigned:
            mark = "O"
        else:
            return None
        self.players[token] = mark
        return mark

    def is_full(self):
        return len(self.players) >= 2

    def ready(self):
        return len(self.players) >= 2

    def move(self, token, pos):
        if not self.ready():
            return {"ok": False, "error": "waiting for players",
                    **self.snapshot()}
        if self.winner is not None:
            return {"ok": False, "error": "game already over",
                    **self.snapshot()}
        mark = self.players.get(token)
        if mark is None:
            return {"ok": False, "error": "unknown player"}
        if mark != self.turn:
            return {"ok": False, "error": "not your turn",
                    **self.snapshot()}
        if not isinstance(pos, int) or not (0 <= pos < 9):
            return {"ok": False, "error": "invalid position"}
        if self.board[pos] != " ":
            return {"ok": False, "error": "cell occupied"}

        self.board[pos] = mark
        self._check_end()
        if self.winner is None:
            self.turn = "O" if self.turn == "X" else "X"
        return {"ok": True, **self.snapshot()}

    def _check_end(self):
        for a, b, c in self.WIN_LINES:
            if self.board[a] != " " and \
               self.board[a] == self.board[b] == self.board[c]:
                self.winner = self.board[a]
                return
        if all(cell != " " for cell in self.board):
            self.winner = "draw"

    def reset(self):
        self.board = [" "] * 9
        self.turn = "X"
        self.winner = None

    def snapshot(self):
        return {
            "game_id": self.id,
            "board": self.board,
            "turn": self.turn,
            "winner": self.winner,
            "ready": self.ready(),
            "players": len(self.players),
        }


class Controller:
    """複数の対戦（部屋）を管理する。2人ずつ自動でペアにする。"""

    def __init__(self):
        self.reset()

    def reset(self):
        self.games = {}          # game_id -> Game
        self.token_to_game = {}  # player token -> game_id
        self._next_id = 1
        return {"ok": True, "message": "reset done"}

    def _find_or_create_game(self):
        """空きのある部屋を探し、なければ新規作成する。"""
        for game in self.games.values():
            if not game.is_full():
                return game
        game_id = self._next_id
        self._next_id += 1
        game = Game(game_id)
        self.games[game_id] = game
        return game

    def join(self):
        """プレイヤーを登録。ランダムトークンと所属部屋・マークを返す。"""
        game = self._find_or_create_game()
        token = secrets.token_urlsafe(16)
        mark = game.add_player(token)
        if mark is None:  # 通常は起こらない
            return {"ok": False, "error": "failed to join"}
        self.token_to_game[token] = game.id
        return {"ok": True, "player": token, "mark": mark,
                "game_id": game.id}

    def move(self, token, pos):
        game = self._game_of(token)
        if game is None:
            return {"ok": False, "error": "unknown player"}
        return game.move(token, pos)

    def state(self, token=None):
        """トークン指定時はその部屋の状態。無指定なら全体サマリ。"""
        if token is not None:
            game = self._game_of(token)
            if game is None:
                return {"ok": False, "error": "unknown player"}
            return {"ok": True, **game.snapshot()}
        return {
            "ok": True,
            "games": [g.snapshot() for g in self.games.values()],
            "total_games": len(self.games),
            "total_players": len(self.token_to_game),
        }

    def _game_of(self, token):
        game_id = self.token_to_game.get(token)
        if game_id is None:
            return None
        return self.games.get(game_id)
