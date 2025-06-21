import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY')
    DATABASE_FILE = os.getenv('DATABASE_FILE')  # << Only file path, not full database URI
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER')  

    # OAuth settings
    OAUTH_CLIENT_ID = os.getenv('OAUTH_CLIENT_ID')
    OAUTH_CLIENT_SECRET = os.getenv('OAUTH_CLIENT_SECRET')

    # Session configurations
    SESSION_PERMANENT = False
    SESSION_TYPE = "filesystem"
    SECRET_KEY = os.getenv('SECRET_KEY')

    # Deepgram API
    DEEPGRAM_API_KEY = os.getenv('DEEPGRAM_API_KEY')
