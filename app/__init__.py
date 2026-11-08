from flask import Flask, render_template
from flask_socketio import SocketIO

from .game import PokerTable
from .socket_handlers import register_socket_handlers

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = "poker-secret-key"

socketio = SocketIO(app, cors_allowed_origins="*")

table = PokerTable(socketio)

register_socket_handlers(socketio, table)


@app.route("/")
def index():
    return render_template("index.html")
