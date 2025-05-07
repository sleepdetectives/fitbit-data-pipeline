import os
from dotenv import load_dotenv
import fitbit_data_pipeline.Utility as util

log = util.get_logger()
load_dotenv('.env')
client_id = os.getenv("client_id")
client_secret = os.getenv("client_secret")

if not client_id or not client_secret:
    log.error("Either client_id or client_secret not found in .env")
    raise ValueError("Either client_id or client_secret not found in .env")

REDIRECT_URI = "https://localhost:105/hello/"
FITBIT_API_BASE_URL = 'https://api.fitbit.com'
FITBIT_SLEEP_ENDPOINT_RANGE = '/1.2/user/{fitbit_device_id}/sleep/date/{start_date}/{end_date}.json'
FITBIT_SLEEP_ENDPOINT_EACH = '/1.2/user/{fitbit_device_id}/sleep/date/{sleep_date}.json'
FITBIT_STEPS_ENDPOINT_EACH = '/1.2/user/{fitbit_device_id}/activities/steps/date/{sleep_date}/1d/1min.json'
FITBIT_HR_ENDPOINT_EACH = '/1.2/user/{fitbit_device_id}/activities/heart/date/{sleep_date}/1d/1min.json'
FITBIT_TOKEN_URL = 'https://api.fitbit.com/oauth2/token'
FITBIT_AUTH_URL = "https://www.fitbit.com/oauth2/authorize"
FITBIT_LOGOUT_URL = "https://www.fitbit.com/logout"
SCOPES = ['activity', 'sleep', 'heartrate', 'profile']
