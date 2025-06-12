import os
from cs50 import SQL
from flask import Flask, request, render_template, jsonify 
from flask_session import Session
from config import Config
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config.from_object(Config)
Session(app)

db = SQL(f"sqlite:///{app.config['DATABASE_FILE']}")
save_folder = app.config['UPLOAD_FOLDER']

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/mantra")
def mantra(): 
    return render_template("mantra.html")

@app.route("/record")
def record():
    return render_template("record.html")

@app.route("/save_mantra", methods=["POST"])
def save():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file part in the request'}), 400
    file = request.files['audio']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file:
        filename = secure_filename(file.filename)
        file_path = os.path.join(save_folder, filename)
        file.save(file_path)
        return jsonify({'message': f'Audio saved successfully to {file_path}'}), 200
    return jsonify({'error': 'Failed to save audio'}), 500



