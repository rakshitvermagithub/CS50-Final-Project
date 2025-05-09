from cs50 import SQL
from flask import Flask, request, render_template
from flask_session import Session
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
Session(app)

db = SQL(f"sqlite:///{app.config['DATABASE_FILE']}")

@app.route("/")
def index():
    return render_template("index.html")