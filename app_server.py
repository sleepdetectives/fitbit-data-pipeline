from flask import Flask, request

app = Flask(__name__)

# Flask route to handle the redirect URI after OAuth authorization
@app.route('/hello/', methods=['GET'])
def callback():
    # Extract the authorization code from the URL
    code = request.args.get('code')
    state = request.args.get('state')

    # Here you can further process the code, e.g., exchange it for an access token
    return f'Authorization code: {code}, State: {state}', 200

# Run the app on port 106 (to match your redirect URI)
if __name__ == '__main__':
    app.run(ssl_context='adhoc', port=105)