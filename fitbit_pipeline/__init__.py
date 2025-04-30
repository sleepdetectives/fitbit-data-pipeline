import os
from dotenv import load_dotenv

load_dotenv('.env')
client_id = os.getenv("client_id")
client_secret = os.getenv("client_secret")
participants_tokens = os.getenv("participants_tokens")

