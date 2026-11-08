import random
from collections import Counter


def card_value(card):
    rank = card[0]
    if rank in "TJQKA":
        return {"T": 10, "J": 11, "Q": 12, "K": 13, "A": 14}[rank]
    return int(rank)


def rank_key(hand):
    values = sorted([card_value(c) for c in hand], reverse=True)
    counts = Counter(values)
    counts_sorted = sorted(counts.items(), key=lambda x: (x[1], x[0]), reverse=True)
    rank = 0
    if len(hand) == 5:
        is_flush = len({c[1] for c in hand}) == 1
        straight_values = sorted(set(values))
        is_straight = len(straight_values) == 5 and (
            straight_values[-1] - straight_values[0] == 4
            or set([14, 5, 4, 3, 2]) <= set(straight_values)
        )

        if is_flush and is_straight:
            rank = 8
            if straight_values[-1] == 14 and set([14, 5, 4, 3, 2]) <= set(straight_values):
                top = 5
            else:
                top = max(straight_values)
            return (rank, top)

        if counts_sorted[0][1] == 4:
            rank = 7
            quadruple = counts_sorted[0][0]
            kicker = counts_sorted[1][0]
            return (rank, quadruple, kicker)

        if counts_sorted[0][1] == 3 and counts_sorted[1][1] == 2:
            rank = 6
            return (rank, counts_sorted[0][0], counts_sorted[1][0])

        if is_flush:
            rank = 5
            return (rank, *values)

        if is_straight:
            rank = 4
            if set([14, 5, 4, 3, 2]) <= set(straight_values):
                top = 5
            else:
                top = max(straight_values)
            return (rank, top)

        if counts_sorted[0][1] == 3:
            rank = 3
            return (rank, counts_sorted[0][0], *sorted([v for v in values if v != counts_sorted[0][0]], reverse=True))

        if counts_sorted[0][1] == 2 and counts_sorted[1][1] == 2:
            rank = 2
            pairs = [x[0] for x in counts_sorted[:2]]
            kicker = max(v for v in values if v not in pairs)
            return (rank, *sorted(pairs, reverse=True), kicker)

        if counts_sorted[0][1] == 2:
            rank = 1
            pair = counts_sorted[0][0]
            kickers = sorted([v for v in values if v != pair], reverse=True)
            return (rank, pair, *kickers)

        return (rank, *values)
    return (0, *sorted(values, reverse=True))


def evaluate_hand(cards):
    best = None
    for i in range(len(cards) - 4):
        for j in range(i + 1, len(cards) - 3):
            for k in range(j + 1, len(cards) - 2):
                for l in range(k + 1, len(cards) - 1):
                    for m in range(l + 1, len(cards)):
                        combo = [cards[i], cards[j], cards[k], cards[l], cards[m]]
                        score = rank_key(combo)
                        if best is None or score > best:
                            best = score
    return best if best is not None else rank_key(cards[:5])


class PokerTable:
    def __init__(self, socketio):
        self.socketio = socketio
        self.players = {}
        self.deck = []
        self.community = []
        self.pot = 0
        self.current_bet = 0
        self.dealer_index = 0
        self.turn_index = 0
        self.turn_order = []
        self.stage = "waiting"
        self.stage_index = 0
        self.game_started = False
        self.last_message = "No active game"

    def deck_builder(self):
        suits = ["H", "D", "C", "S"]
        ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"]
        return [f"{rank}{suit}" for suit in suits for rank in ranks]

    def shuffle_deck(self):
        self.deck = self.deck_builder()
        random.shuffle(self.deck)

    def add_player(self, sid, name):
        if sid in self.players:
            self.players[sid]["name"] = name
            return True
        if len(self.players) >= 8:
            return False
        self.players[sid] = {
            "sid": sid,
            "name": name,
            "chips": 1000,
            "hand": [],
            "folded": False,
            "all_in": False,
            "bet": 0,
            "active": True,
            "seat": len(self.players),
        }
        return True

    def remove_player(self, sid):
        if sid not in self.players:
            return
        del self.players[sid]
        if self.game_started and len(self.players) < 1:
            self.game_started = False
            self.stage = "waiting"
            self.last_message = "Not enough players to continue."

    def get_public_state(self, for_sid=None):
        player_data = []
        for sid, p in sorted(self.players.items(), key=lambda item: item[1]["seat"]):
            player_data.append(
                {
                    "sid": sid,
                    "name": p["name"],
                    "chips": p["chips"],
                    "bet": p["bet"],
                    "folded": p["folded"],
                    "all_in": p["all_in"],
                    "seat": p["seat"],
                    "active": p["active"],
                    "hand": p["hand"] if for_sid == sid else [],
                }
            )
        return {
            "players": player_data,
            "pot": self.pot,
            "current_bet": self.current_bet,
            "community": self.community,
            "stage": self.stage,
            "game_started": self.game_started,
            "dealer_index": self.dealer_index,
            "turn_index": self.turn_index,
            "turn_order": self.turn_order,
            "last_message": self.last_message,
        }

    def start_game(self):
        if len(self.players) < 1:
            self.last_message = "At least 1 player is required to start."
            return False

        self.shuffle_deck()
        self.community = []
        self.pot = 0
        self.current_bet = 0
        self.stage_index = 0
        self.stage = "preflop"
        self.game_started = True
        self.last_message = "Game started. Place your bets."
        self.dealer_index = self.dealer_index % len(self.players) if self.players else 0

        for p in self.players.values():
            p["hand"] = []
            p["folded"] = False
            p["all_in"] = False
            p["bet"] = 0
            p["active"] = True

        for _ in range(2):
            for p in sorted(self.players.values(), key=lambda p: p["seat"]):
                p["hand"].append(self.deck.pop())

        self.turn_order = [p["sid"] for p in sorted(self.players.values(), key=lambda p: p["seat"])]
        self.turn_index = self.get_next_turn_index(self.dealer_index)
        self.send_action_prompt()
        self.broadcast_state()
        return True

    def get_next_turn_index(self, start_index):
        candidates = [p["sid"] for p in sorted(self.players.values(), key=lambda p: p["seat"])]
        if not candidates:
            return 0
        start = start_index % len(candidates)
        for offset in range(len(candidates)):
            idx = (start + offset) % len(candidates)
            sid = candidates[idx]
            if self.players[sid]["active"] and not self.players[sid]["folded"]:
                return idx
        return start

    def send_action_prompt(self):
        if not self.game_started:
            return
        player_ids = self.turn_order
        if not player_ids:
            return
        current_index = self.turn_index % len(player_ids)
        sid = player_ids[current_index]
        player = self.players[sid]
        options = ["check", "bet", "fold"] if self.current_bet == 0 else ["call", "raise", "fold"]
        if player["all_in"]:
            options = ["fold"]
        self.socketio.emit(
            "request_action",
            {
                "stage": self.stage,
                "current_bet": self.current_bet,
                "pot": self.pot,
                "community": self.community,
                "options": options,
                "hand": player["hand"],
                "chips": player["chips"],
                "message": f"{player['name']}, it's your turn.",
            },
            room=sid,
        )

    def advance_turn(self):
        if not self.game_started:
            return
        remaining = [p["sid"] for p in sorted(self.players.values(), key=lambda p: p["seat"]) if p["active"] and not p["folded"]]
        if len(remaining) <= 1:
            self.finish_hand()
            return

        candidates = self.turn_order
        if not candidates:
            self.last_message = "No player to act."
            return

        self.turn_index = (self.turn_index + 1) % len(candidates)
        while True:
            sid = candidates[self.turn_index]
            p = self.players[sid]
            if p["active"] and not p["folded"]:
                break
            self.turn_index = (self.turn_index + 1) % len(candidates)
            if self.turn_index == 0:
                break

        if self.turn_index == 0:
            self.next_stage()
            return

        self.send_action_prompt()
        self.broadcast_state()

    def process_action(self, sid, action, amount=0):
        if not self.game_started or sid not in self.players:
            return

        player = self.players[sid]
        if player["folded"]:
            return

        if self.turn_order and self.turn_order[self.turn_index % len(self.turn_order)] != sid:
            return

        if action == "fold":
            player["folded"] = True
            self.last_message = f"{player['name']} folded."
            self.advance_turn()
            return

        if action == "check":
            if self.current_bet > 0:
                self.last_message = "You can't check when there is a bet on the table."
                return
            self.last_message = f"{player['name']} checked."
            self.advance_turn()
            return

        if action == "bet":
            needed = max(1, self.current_bet)
            amount = max(0, int(amount or needed))
            if amount <= 0:
                return
            if amount > player["chips"]:
                amount = player["chips"]
            player["chips"] -= amount
            player["bet"] += amount
            self.pot += amount
            self.current_bet = max(self.current_bet, amount)
            self.last_message = f"{player['name']} bet {amount}."
            self.advance_turn()
            return

        if action == "call":
            amount = self.current_bet - player["bet"]
            if amount <= 0:
                self.last_message = f"{player['name']} called."
                self.advance_turn()
                return
            if amount > player["chips"]:
                amount = player["chips"]
            player["chips"] -= amount
            player["bet"] += amount
            self.pot += amount
            self.last_message = f"{player['name']} called {amount}."
            self.advance_turn()
            return

        if action == "raise":
            amount = max(0, int(amount or self.current_bet))
            if amount <= self.current_bet:
                self.last_message = "Raise amount must be higher than the current bet."
                return
            if amount > player["chips"]:
                amount = player["chips"]
            extra = amount - player["bet"]
            if extra < 0:
                extra = 0
            player["chips"] -= extra
            player["bet"] += extra
            self.pot += extra
            self.current_bet = max(self.current_bet, amount)
            self.last_message = f"{player['name']} raised to {amount}."
            self.advance_turn()
            return

        self.last_message = "Unknown action."

    def next_stage(self):
        if self.stage == "preflop":
            self.stage = "flop"
            self.community = self.deck[:3]
            self.deck = self.deck[3:]
        elif self.stage == "flop":
            self.stage = "turn"
            self.community.append(self.deck.pop(0))
        elif self.stage == "turn":
            self.stage = "river"
            self.community.append(self.deck.pop(0))
        elif self.stage == "river":
            self.finish_hand()
            return
        self.current_bet = 0
        for p in self.players.values():
            p["bet"] = 0
        self.turn_index = self.get_next_turn_index(self.dealer_index)
        self.turn_order = [p["sid"] for p in sorted(self.players.values(), key=lambda p: p["seat"]) if p["active"] and not p["folded"]]
        self.last_message = f"Stage changed to {self.stage}."
        self.send_action_prompt()
        self.broadcast_state()

    def finish_hand(self):
        active_players = [p for p in self.players.values() if p["active"] and not p["folded"]]
        if len(active_players) == 1:
            winner = active_players[0]
            winner["chips"] += self.pot
            self.last_message = f"{winner['name']} wins the pot by default."
        else:
            best_rank = None
            winner_ids = []
            for p in active_players:
                cards = p["hand"] + self.community
                score = evaluate_hand(cards)
                if best_rank is None or score > best_rank:
                    best_rank = score
                    winner_ids = [p["sid"]]
                elif score == best_rank:
                    winner_ids.append(p["sid"])
            split = self.pot // len(winner_ids)
            extra = self.pot % len(winner_ids)
            for idx, sid in enumerate(winner_ids):
                self.players[sid]["chips"] += split + (1 if idx < extra else 0)
            self.last_message = "Showdown! " + ", ".join(self.players[sid]["name"] for sid in winner_ids) + " win(s) the pot."

        self.pot = 0
        self.current_bet = 0
        self.community = []
        self.stage = "waiting"
        self.game_started = False
        for p in self.players.values():
            p["hand"] = []
            p["bet"] = 0
            p["folded"] = False
            p["active"] = True
            p["all_in"] = False
        self.broadcast_state()

    def broadcast_state(self):
        for sid in self.players:
            state = self.get_public_state(sid)
            self.socketio.emit("table_state", state, room=sid)
