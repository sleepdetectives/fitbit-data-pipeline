import logging
import os
import sys

from flask import Flask, request

app = Flask(__name__)

# Flask route to handle the redirect URI after OAuth authorization
os.makedirs("logs", exist_ok=True)

logging.basicConfig(filename=f"logs/oauth.log", level=logging.INFO)
@app.route('/hello/', methods=['GET'])
def callback():
    # Extract the authorization code from the URL

    code = request.args.get('code')
    state = request.args.get('state')
    logging.info(f"Received code: {code}, state: {state}")
    auth_path = os.path.abspath("auth_code.txt")
    with open(auth_path, "w") as file:
        file.write(f"https://localhost:105/hello/?code={code}&state={state}")
        logging.info(f"Auth code written to {auth_path}")
    return f'Authorization successfully received! You may close this tab', 200
    #return request, 200

if __name__ == '__main__':
    app.run(ssl_context='adhoc', port=105)