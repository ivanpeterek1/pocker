from flask import request
from flask_socketio import emit, join_room


def register_socket_handlers(socketio, table):
    @socketio.on("connect")
    def on_connect():
        emit("table_state", table.get_public_state(request.sid))

    @socketio.on("disconnect")
    def on_disconnect():
        table.remove_player(request.sid)
        table.broadcast_state()

    @socketio.on("join_game")
    def on_join_game(data):
        name = (data or {}).get("name", "Player").strip()[:12] or "Player"
        if not table.add_player(request.sid, name):
            emit("table_state", {"last_message": "Table is full."})
            return
        join_room(request.sid)
        table.last_message = f"{name} joined the table."
        table.broadcast_state()

    @socketio.on("start_game")
    def on_start_game():
        if table.start_game():
            table.broadcast_state()

    @socketio.on("player_action")
    def on_player_action(data):
        action = (data or {}).get("action", "check").lower()
        amount = int((data or {}).get("amount", 0) or 0)
        table.process_action(request.sid, action, amount)
        table.broadcast_state()
