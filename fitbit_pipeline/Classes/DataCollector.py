import time
from datetime import datetime
import pandas as pd
from requests_oauthlib import OAuth2Session
from config import FITBIT_AUTH_URL
from .Init import Participant
from .Init import Session
from fitbit_pipeline.Classes.PManager import ParticipantManager
import config as cfg
import fitbit_pipeline.Utility as util


class DataCollector:
    FITBIT_API_BASE_URL = cfg.FITBIT_API_BASE_URL
    FITBIT_SLEEP_ENDPOINT_RANGE = cfg.FITBIT_SLEEP_ENDPOINT_RANGE
    FITBIT_SLEEP_ENDPOINT_EACH = cfg.FITBIT_SLEEP_ENDPOINT_EACH
    FITBIT_STEPS_ENDPOINT_EACH = cfg.FITBIT_STEPS_ENDPOINT_EACH
    FITBIT_HR_ENDPOINT_EACH = cfg.FITBIT_HR_ENDPOINT_EACH
    FITBIT_AUTH_URL = cfg.FITBIT_AUTH_URL
    TOKEN_URL = cfg.FITBIT_TOKEN_URL
    SCOPES = cfg.SCOPES

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str, token: dict = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.token = token

    def is_token_expired(self, token: dict) -> bool:
        if 'expires_at' not in token:
            return True

        return time.time() > token['expires_at']

    def ensure_token_valid(self,participant, pm):
        if self.token and 'expires_at' in self.token and datetime.now().timestamp() > self.token['expires_at']:
            print("Access token expired, refreshing...")
            self.refresh_access_token(participant,pm)

    def refresh_access_token(self, participant, pm):
        extra = {'client_id': self.client_id, 'client_secret': self.client_secret}
        oauth2_session = OAuth2Session(self.client_id, token=self.token)
        self.token = oauth2_session.refresh_token(self.TOKEN_URL, **extra)
        participant.token = self.token
        pm.save_token(participant)

        print("Access token refreshed:", self.token)

    def get_fitbit_oauth(self, participant: Participant, participant_manager: ParticipantManager):
        print("part token here", participant.token)
        print("part token exp here", self.is_token_expired(participant.token))
        if participant.token and not self.is_token_expired(participant.token):
            print(f"Participant {participant.participant_id} already authorized with a valid token.")
            return  # No need to re-authorize

        fitbit = OAuth2Session(self.client_id, redirect_uri=self.redirect_uri, scope=self.SCOPES)
        authorization_url, state = fitbit.authorization_url(FITBIT_AUTH_URL)
        print(f"Please go here and authorize participant {participant.participant_id}: {authorization_url}")
        redirect_response = input('Paste the full redirect URL here: ')

        # Fetch token and store it in the participant object
        token = fitbit.fetch_token(self.TOKEN_URL, authorization_response=redirect_response,client_secret=self.client_secret)

        participant.token = token
        participant.is_authorized = True
        participant_manager.save_token(participant)
        print(f"Authorization successful for participant {participant.participant_id}")

    def collect_intraday_data(self, session: Session, pm: ParticipantManager):
        user_id = session.device.device_id
        print('user here',user_id)
        if not session.participant.is_authorized:
            print(f"User {user_id} is not authorized. Need to authorise user")
            self.get_fitbit_oauth(session.participant)

        self.ensure_token_valid(session.participant, pm)  # what if token became invalid at this second????
        fitbit = OAuth2Session(self.client_id, token=session.participant.token)
        steps_df = []
        heart_rate_df = []
        for sleep_date in session.participant.collection_days:
            steps_url = self.FITBIT_API_BASE_URL + self.FITBIT_STEPS_ENDPOINT_EACH.format(fitbit_device_id=user_id,sleep_date=sleep_date)
            response = fitbit.get(steps_url)
            if response.status_code != 200:
                raise Exception(f"Error fetching sleep data for participant {session.participant.participant_id} and date {sleep_date}: {response.status_code} - {response.text}")
            steps_data = response.json()
            date = steps_data["activities-steps"][0]["dateTime"]
            intraday_data = steps_data["activities-steps-intraday"]["dataset"]
            time_steps = [(entry["time"], entry["value"]) for entry in intraday_data]

            df = pd.DataFrame(time_steps, columns=["time", "activity_steps"])
            df["date"] = date
            df['pid'] = session.participant.participant_id
            df = df[['pid','date', 'time', "activity_steps"]]
            steps_df.append(df)

            ######heart rate ##################
            hr_url = self.FITBIT_API_BASE_URL + self.FITBIT_HR_ENDPOINT_EACH.format(fitbit_device_id=user_id,sleep_date=sleep_date)
            response = fitbit.get(hr_url)
            if response.status_code == 403:
                return 2, None, None, response
            if response.status_code != 200:
                raise Exception(
                    f"Error fetching sleep data for participant {session.participant.participant_id} and date {sleep_date}: {response.status_code} - {response.text}")
            hr_data = response.json()
            date = hr_data["activities-heart"][0]["dateTime"]
            # Extract time and steps from activities-steps-intraday
            intraday_data = hr_data["activities-heart-intraday"]["dataset"]
            time_hr = [(entry["time"], entry["value"]) for entry in intraday_data]

            df = pd.DataFrame(time_hr, columns=["time", "heart_rate"])
            df["date"] = date
            df['pid'] = session.participant.participant_id

            df = df[['pid', 'date', 'time', "heart_rate"]]
            heart_rate_df.append(df)

        return 1, pd.concat(steps_df, ignore_index=True), pd.concat(heart_rate_df, ignore_index=True), None

    def collect_sleep_data(self, session: Session, pm: ParticipantManager):
        user_id = session.device.device_id
        print('user here',user_id)
        if not session.participant.is_authorized:
            print(f"User {user_id} is not authorized. Initiating authorization flow...")
            self.get_fitbit_oauth(session.participant)

        self.ensure_token_valid(session.participant, pm)
        fitbit = OAuth2Session(self.client_id, token=session.participant.token)
        sleep_data = ''
        if session.participant.is_consecutive_days:
            start_date = session.participant.collection_days[0]
            end_date = session.participant.collection_days[-1]
            print(f'Data collection days: {start_date} to {end_date}')
            url = self.FITBIT_API_BASE_URL + self.FITBIT_SLEEP_ENDPOINT_RANGE.format(fitbit_device_id=user_id, start_date=start_date, end_date=end_date)
            print('URL', url)
            response = fitbit.get(url)
            print("response",response.text)
            print(response.json())
            if response.status_code != 200:
                raise Exception(f"Error fetching sleep data: {response.status_code} - {response.text}")
            sleep_data = response.json()['sleep']

            util.dump_data(session.participant.participant_id,start_date,end_date,sleep_data)
        else:
            all_sleep_data = []

            for sleep_date in session.participant.collection_days:
                url = self.FITBIT_API_BASE_URL + self.FITBIT_SLEEP_ENDPOINT_EACH.format(fitbit_device_id=user_id,sleep_date=sleep_date)
                response = fitbit.get(url)
                print('Sleep Date '+sleep_date)
                print(response.json())
                print(response.status_code)
                if response.status_code != 200:
                    raise Exception(f"Error fetching sleep data for participant {session.participant.participant_id} and date {sleep_date}: {response.status_code} - {response.text}")
                if len(response.json()['sleep']) > 0:
                    one_sleep_data = response.json()['sleep'][0]
                    all_sleep_data.append(one_sleep_data)
                    sleep_data = all_sleep_data
                else:
                    print(f"no sleep data for user {user_id} on {sleep_date}")
        util.dump_data(session.participant.participant_id,session.participant.collection_days[0],session.participant.collection_days[-1], sleep_data)
        processed_sleep, sleep_stages = util.process_sleep_response(session.participant.participant_id, sleep_data)
        if processed_sleep is None:
            print(f"No sleep data available for user {user_id}.")
            return None, None
        try:
            sorted = processed_sleep.sort_values(by='date')
            print(sorted)
        except KeyError as e:
            print(f"KeyError: {e} - Ensure 'date' column exists in the DataFrame.")
            return None, None
        return sorted, sleep_stages.sort_values(by=['pid','date','time'], ascending=[True, True, True])

    def collect_sleep_all(self, participant_manager: ParticipantManager):
        active_sessions = participant_manager.get_active_sessions()
        all_participant = []
        all_participant_sleep_stages = []
        for session in active_sessions:
            participant = session.participant
            user_id = session.device.device_id
            print(f"Collecting sleep data for participant {participant.participant_id}")
            df_sleep, df_sleep_stages = self.collect_sleep_data(session, participant_manager)
            if df_sleep is None:
                print(f"No sleep data was found for user {user_id}.")
                continue
            all_participant.append(df_sleep)
            all_participant_sleep_stages.append(df_sleep_stages)
        pd_for_all = pd.concat(all_participant, ignore_index=True)
        pd_ss_all = pd.concat(all_participant_sleep_stages, ignore_index=True)
        pd_for_all.to_csv("__all_sleep_data.csv", index=False)
        pd_ss_all.to_csv('__all_fitbit_ss.csv', index=False)

    def collect_intraday_all(self, participant_manager: ParticipantManager):
        active_sessions = participant_manager.get_active_sessions()
        all_participant_intraday_steps = []
        all_participant_intraday_hr = []
        for session in active_sessions:
            df_steps, df_hr = self.collect_intraday_data(session, participant_manager)
            print(df_steps)
            print(df_hr)
            all_participant_intraday_steps.append(df_steps)
            all_participant_intraday_hr.append(df_hr)

        pd_steps_all = pd.concat(all_participant_intraday_steps, ignore_index=True)
        pd_hr_all = pd.concat(all_participant_intraday_hr, ignore_index=True)

        pd_steps_all.to_csv('__all_step_counts.csv', index=False)
        pd_hr_all.to_csv('__all_heart_rate.csv', index=False)
        (pd.merge(pd_steps_all, pd_hr_all, on=['pid', 'date', 'time'], how='outer')).to_csv(
            '__all_intraaday_data_.csv', index=False)
