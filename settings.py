import os
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

# Where Spotify sends the user after login: the URL of this Streamlit app.
# Locally that's the default below; when deployed, set REDIRECT_URI to your app's URL.
# Whatever you use must also be registered in the Spotify developer dashboard.
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://127.0.0.1:8501")
