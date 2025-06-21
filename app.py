import os
from cs50 import SQL
from flask import Flask, redirect, request, render_template, jsonify, session
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_session import Session
from config import Config
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
from deepgram import DeepgramClient, PrerecordedOptions, FileSource, LiveOptions, LiveTranscriptionEvents
import threading
import time

app = Flask(__name__)
app.config.from_object(Config)
Session(app)
socketio = SocketIO(app)

class KeepAliveManager:
    def __init__(self, interval=8):
        self.interval = interval
        self.timer = None
        self.connection = None
        self.running = False

    def _keep_alive(self):
        if not self.running:
            return
        if self.connection:
            try:
                self.connection.send('{"type": "KeepAlive"}')
                print("Keep-alive sent")
            except Exception as e:
                print(f"keep_alive failed: {e}")
        if self.running:
            self.timer = threading.Timer(self.interval, self._keep_alive)
            self.timer.start()

    def start(self, connection):
        self.connection = connection
        self.running = True
        self._keep_alive()

    def stop(self):
        self.running = False
        if self.timer:
            self.timer.cancel()
            self.timer = None
        self.connection = None

db = SQL(f"sqlite:///{app.config['DATABASE_FILE']}")
save_folder = app.config['UPLOAD_FOLDER']
DEEPGRAM_API_KEY = app.config['DEEPGRAM_API_KEY']

deepgram = DeepgramClient(DEEPGRAM_API_KEY)

user_chanting_sessions = {}

@app.route("/register", methods=["GET", "POST"])
def register():

    # If requested via POST
    if request.method == "POST":
        
        # Take SQL data in variable
        user_data = db.execute("SELECT * FROM users;")
        
        username = request.form.get("username")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        error = None

        # Ensure username was submitted
        if not username:
            error = "Must provide a username"

        # Ensure if username already exists
        for user in user_data:
            if user["username"] == username:
                error = "Username already exists" 

        # Ensure password was submitted
        if not password:
            error = "Please submit the password"

        # Ensure confirmation was submitted
        if not confirm_password:
            error = "Please confirm your password"

        # Ensure confirmation matches the password
        if password != confirm_password:
            error = "Passwords do not match"

        # Ensure there were no errors
        if error == None:
            # Hashing the password            
            hash = generate_password_hash(password)

            # Add user details in database
            db.execute(
                "INSERT INTO users(username, hash) VALUES(?, ?)", username, hash
                )
            
            # Store user id in session
            current_user = db.execute(
                "SELECT * FROM users WHERE username = ?", username
            )
            session["user_id"] = current_user[0]["id"]

            # Redirect to previous page, with user logged in
            return redirect("/")
        
        # Re-render template with error, if any
        return render_template("register.html", error=error)
    
    # if requested via GET
    if request.method == "GET":
        return render_template("register.html")
    
@app.route("/login", methods=["GET", "POST"])
def login():
    # Forget any user_id
    session.clear()

    # If user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return render_template("login.html", error="Must provide username")

        # Ensure password was submitted
        elif not request.form.get("password"):
            return render_template("login.html", error="Must provide password")

        # Query database for username
        rows = db.execute("SELECT id, hash FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return render_template("login.html", error="Invalid username and/or password")

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout", methods=["GET"])
def logout():
    # Forget the user
    session.clear()

    # Go back to homepage
    return redirect("/")

@app.route("/")
def index():
    if "user_id" in session:
        return render_template("index.html", logged_in=True)
    else:
        return render_template("index.html", logged_in=False)

@app.route("/mantra")
def mantra():
    # If user is logged_in 
    if "user_id" in session:
        mantras = db.execute("SELECT mantra FROM mantras WHERE id = ?", session["user_id"])
        return render_template("mantra.html", logged_in=True, mantras=mantras)
    else:
        return render_template("mantra.html", logged_in=False)

@app.route("/record")
def record():
    if "user_id" in session:
        return render_template("record.html")
    else:
        return redirect("/register") 

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

            # Deepgram speech-to-text API usage
            try: 
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
                print(f"Raw Deepgram Response Object: {response}")

                # Show transcription in backend
                print(response.to_json(indent=4))

                # Get the transcribed mantra
                mantra = (response["results"]["channels"][0]["alternatives"][0]["transcript"])

                # Only store mantra, if it got heard
                if not mantra == " ":
                    # Store mantra in mantras table
                    db.execute(
                        "INSERT INTO mantras(id, mantra) VALUES(?, ?)", session["user_id"], mantra 
                        )
                return jsonify({'status': 'success', 'message': saving_message, 'deepgram_response': response})
            except Exception as e:
                print(f"Deepgram Exception: {e}")
                return jsonify({'status': 'error', 'message': saving_message, 'transcription_error': f'Deepgram transcription failed: {e}'}), 500
        except Exception as e:
            print(f"Error saving audio file: {e}")
            return jsonify({'status': 'error', 'message': f'Error saving audio file: {e}'}), 500    
    return jsonify({'error': 'Failed to save audio'}), 500

@app.route("/chanting", methods=["GET", "POST"])
def chanting():
    # If user reached route via POST (with a chosen chanting mantra)
    if request.method == "POST":
        # Get the mantra in text form
        selected_mantra = request.form.get("selected_mantra")
        return render_template("automatic_chanting.html", mantra=selected_mantra, logged_in=True)
    
    # If user reached route via GET (for manual chanting)
    if request.method == "GET":
        return render_template("manual_chanting.html", logged_in=True)

@socketio.on('connect')
def connect():
    print(f'Client connected: {request.sid}')

def on_open(connection):
    print('Deepgram WebSocket connection opened.')

def on_transcript(result, request_sid, mantra, user_chanting_sessions):
    print("on_transcript called!", result)
    try:
        # Handle both dict and object for compatibility
        if isinstance(result, dict):
            transcript = result["channel"]["alternatives"][0]["transcript"]
            words = result["channel"]["alternatives"][0].get("words", [])
        else:
            transcript = result.channel.alternatives[0].transcript
            words = getattr(result.channel.alternatives[0], "words", [])
        print("Transcript:", transcript)
        session_data = user_chanting_sessions.get(request_sid)
        mantra_text = mantra.lower().strip()
        if mantra_text:
            cleaned_mantra = mantra_text.replace(',', '').replace('.', '').replace('!', '')
            mantra_words = cleaned_mantra.split()
            mantra_word_count = len(mantra_words)
        else:
            print(f"Mantra not found")
            return

        for word_data in words:
            transcribed_word = word_data["word"] if isinstance(word_data, dict) else word_data.word
            current_word_index = session_data.get("next_mantra_word_index", 0)
            target_word = mantra_words[current_word_index]
            if transcribed_word == target_word:
                new_index = current_word_index + 1
                print(f"works")
                if new_index == mantra_word_count:
                    session_data["count"] += 1
                    emit('update_count', {'count': session_data["count"]}, to=request_sid)
                    session_data["next_mantra_word_index"] = 0
                    print(f"SID {request_sid}: MANTRA COMPLETE! New count: {session_data['count']}")
                else:
                    session_data["next_mantra_word_index"] = new_index
                    print(f"SID {request_sid}: Found '{target_word}', now looking for '{mantra_words[new_index]}'")
    except Exception as e:
        print(f"Transcription error: {e}")
        emit('chanting_error', {'message': 'Transcription processing failed'}, room=request_sid)

def on_error(error, request_sid):
    print(f'Deepgram WebSocket error: {error}')
    emit('chanting_error', {'message': f'Deepgram error: {error}'}, room=request_sid)

def on_close(code, reason, request_sid, user_chanting_sessions):
    print(f'Deepgram WebSocket connection closed with code {code}, reason: {reason}')
    user_chanting_sessions.pop(request_sid, None)

@socketio.on('start_chanting')
def start_chanting(mantra):
    user_id = session["user_id"]
    sid = request.sid  # <--- CAPTURE SID HERE
    print(f'User {user_id} started chanting: {mantra}')
    user_chanting_sessions[sid] = {
        'count': 0,
        'next_mantra_word_index': 0,
        'dg_connection': None,
        'user_id': user_id,
        'keep_alive_manager': None
    }

    try:
        dg_live_connection = deepgram.listen.websocket.v("1")
        user_chanting_sessions[sid]['dg_connection'] = dg_live_connection

        keep_alive_manager = KeepAliveManager(interval=8)
        user_chanting_sessions[sid]['keep_alive_manager'] = keep_alive_manager
        keep_alive_manager.start(dg_live_connection)

        print("before handlers")
        dg_live_connection.on('open', on_open)

        # Transcript handler: pass sid and mantra as closure variables
        def transcript_handler(self, **kwargs):
            result = kwargs.get('result')
            if not result:
                print("No result found in transcript handler kwargs")
                return
            on_transcript(result, sid, mantra, user_chanting_sessions)  # Use captured sid, not request.sid

        dg_live_connection.on(LiveTranscriptionEvents.Transcript, transcript_handler)

        print("after transcript")

        # Error handler: must accept self, error
        def error_handler(self, error):
            on_error(error, sid)

        dg_live_connection.on(LiveTranscriptionEvents.Error, error_handler)

        def close_handler(*args, **kwargs):
            # Handle different possible signatures
            if len(args) >= 3:
                self, code, reason = args[0], args[1], args[2]
            elif len(args) == 2:
                self, code = args[0], args[1]
                reason = "Unknown"
            else:
                code, reason = 1000, "Unknown"
    
            on_close(code, reason, sid, user_chanting_sessions)


        dg_live_connection.on(LiveTranscriptionEvents.Close, close_handler)

        dg_live_connection.start(LiveOptions(
            model="nova-3",
            language="en-US",
            interim_results=True,
            punctuate=False,
            encoding="opus",
            sample_rate=48000,
            endpointing=300,  # Reduce endpointing for better responsiveness
            utterance_end_ms="1000"  # Optimize for real-time processing
        ))


    except Exception as e:
        emit('chanting_error', {'message': f'Could not connect to Deepgram: {e}'}, room=sid)


@socketio.on('audio_chunk')
def audio_chunk(data):
    session_data = user_chanting_sessions.get(request.sid)
    if session_data and session_data['dg_connection']:
        try:
            print("Data is being sent")
            session_data['dg_connection'].send(data)
        except Exception as e:
            print(f"Audio send error: {e}")
            emit('chanting_error', {'message': 'Audio transmission failed'}, room=request.sid)

@socketio.on('stop_chanting')
def handle_stop_chanting():
    session_data = user_chanting_sessions.get(request.sid)
    if session_data:
        if session_data.get('keep_alive_manager'):
            session_data['keep_alive_manager'].stop()
        if session_data.get('dg_connection'):
            session_data['dg_connection'].finish()
        user_chanting_sessions.pop(request.sid, None)

@socketio.on('disconnect')
def handle_disconnect():
    print(f'Client disconnected: {request.sid}')
    session_data = user_chanting_sessions.get(request.sid)
    if session_data:
        if session_data.get('keep_alive_manager'):
            session_data['keep_alive_manager'].stop()
        if session_data.get('dg_connection'):
            session_data['dg_connection'].finish()
        user_chanting_sessions.pop(request.sid, None)

if __name__ == '__main__':
    socketio.run(app, debug=True)