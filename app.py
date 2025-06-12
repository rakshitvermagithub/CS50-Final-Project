import os
from cs50 import SQL
from flask import Flask, request, render_template, jsonify 
from flask_session import Session
from config import Config
from werkzeug.utils import secure_filename
from deepgram import DeepgramClient, PrerecordedOptions, FileSource

app = Flask(__name__)
app.config.from_object(Config)
Session(app)

db = SQL(f"sqlite:///{app.config['DATABASE_FILE']}")
save_folder = app.config['UPLOAD_FOLDER']
DEEPGRAM_API_KEY = app.config['DEEPGRAM_API_KEY']


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
        try:
            file.save(file_path)
            # Check if file exists?
            if not os.path.exists(file_path):
                return jsonify({'status': 'error', 'message': 'File does not exist'})
            
            saving_message = "File saved, successfully"

            try: 
                deepgram = DeepgramClient(DEEPGRAM_API_KEY)

                with open(file_path, "rb") as file:
                    buffer_data = file.read()

                payload: FileSource = {
                    "buffer": buffer_data,
                }

                options = PrerecordedOptions(
                    model="nova-3",
                    smart_format=True,
                )

                response = deepgram.listen.rest.v("1").transcribe_file(payload, options)

                json_response = response.to_json(indent=4)
                print(json_response)
                return jsonify({'status': 'success', 'message': saving_message, 'deepgram_response': json_response})
            except Exception as e:
                print(f"Deepgram Exception: {e}")
                return jsonify({'status': 'error', 'message': saving_message, 'transcription_error': f'Deepgram transcription failed: {e}'}), 500
        except Exception as e:
            print(f"Error saving audio file: {e}")
            return jsonify({'status': 'error', 'message': f'Error saving audio file: {e}'}), 500
        
    return jsonify({'error': 'Failed to save audio'}), 500



