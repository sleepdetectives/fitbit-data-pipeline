import fitbit_data_pipeline.Utility as util
import os
import sys

from flask import Flask, request

app = Flask(__name__)

# Flask route to handle the redirect URI after OAuth authorization
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
auth_path = os.path.join(project_root, 'auth_code.txt')
log = util.get_logger()

@app.route('/hello/', methods=['GET'])
def callback():
    # Extract the authorization code from the URL

    code = request.args.get('code')
    state = request.args.get('state')
    log.info(f"Received code: {code}, state: {state}")
    #auth_path = os.path.abspath("../../auth_code.txt")
    print(auth_path)
    log.info(auth_path)
    with open(auth_path, "w") as file:
        log.info("Got here...")
        file.write(f"https://localhost:105/hello/?code={code}&state={state}")
        log.info(f"Auth code written to {auth_path}")
    return f'Authorization successfully received! You may close this tab', 200
    #return request, 200

if __name__ == '__main__':
    app.run(ssl_context='adhoc', port=105)