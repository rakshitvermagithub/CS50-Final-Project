import os
from cs50 import SQL
from flask import Flask,redirect, request, render_template, jsonify, session
from flask_session import Session
from config import Config
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
from deepgram import DeepgramClient, PrerecordedOptions, FileSource

app = Flask(__name__)
app.config.from_object(Config)
Session(app)

db = SQL(f"sqlite:///{app.config['DATABASE_FILE']}")
save_folder = app.config['UPLOAD_FOLDER']
DEEPGRAM_API_KEY = app.config['DEEPGRAM_API_KEY']


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
        id = session["user_id"]
        return render_template("mantra.html", logged_in=True)
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
                print(f"Raw Deepgram Response Object: {response}")

                # Show transcription in backend
                print(response.to_json(indent=4))

                # Get the transcribed mantra
                mantra = (response["results"]["channels"][0]["alternatives"][0]["transcript"])

                # Only store mantra, if it got heard
                if not mantra == '':
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



