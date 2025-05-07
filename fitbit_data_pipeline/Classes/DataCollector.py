import os
import time
import webbrowser
from datetime import datetime
import pandas as pd
from requests_oauthlib import OAuth2Session
from config import FITBIT_AUTH_URL
from .Participant import Participant
from .Participant import Session
from fitbit_data_pipeline.Classes.PManager import ParticipantManager
import config as cfg
import fitbit_data_pipeline.Utility as util

log = util.get_logger()


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

    def ensure_token_valid(self, participant, pm):
        if self.token and 'expires_at' in self.token and datetime.now().timestamp() > self.token['expires_at']:
            log.info(f"Access token expired for {participant.participant_id}, refreshing...")
            #print(f"Access token expired for {participant.participant_id}, refreshing...")
            self.refresh_access_token(participant, pm)

    def refresh_access_token(self, participant, pm):
        extra = {'client_id': self.client_id, 'client_secret': self.client_secret}
        oauth2_session = OAuth2Session(self.client_id, token=self.token)
        self.token = oauth2_session.refresh_token(self.TOKEN_URL, **extra)
        participant.token = self.token
        pm.save_token(participant)

        log.info(f"Access token refreshed for {participant.participant_id}:", self.token)
        print("Access token refreshed:", self.token)

    def get_fitbit_oauth(self, participant: Participant, participant_manager: ParticipantManager):
        # print("part token here", participant.token)
        participant_manager.load_token(participant)
        #print(f"Token expired: {self.is_token_expired(participant.token)}")
        if participant.token and not self.is_token_expired(participant.token):
            log.info(f"Participant {participant.participant_id} already authorized with a valid token.")
            print(f"Participant {participant.participant_id} already authorized with a valid token.")
            participant.is_authorized = True
            return  # No need to re-authorize

        fitbit = OAuth2Session(self.client_id, redirect_uri=self.redirect_uri, scope=self.SCOPES)
        authorization_url, state = fitbit.authorization_url(FITBIT_AUTH_URL)
        #print(f"Please go here and authorize participant {participant.participant_id}: {authorization_url}")
        print(f"Launching the browser to authorise user {participant.participant_id}")

        webbrowser.open("https://www.fitbit.com/logout")
        time.sleep(5)
        print(f"Press log into the fitbit account for user {participant.participant_id}. Then press the enter key")
        input()
        webbrowser.open(authorization_url)
        timeout = 30
        start_time = time.time()
        redirect_response = None
        auth_path = os.path.abspath("auth_code.txt")
        print("Waiting for the redirect URL file to be written")
        while time.time() - start_time < timeout:
            if os.path.exists(auth_path):
                time.sleep(2)
                with open(auth_path, "r") as file:
                    response = file.read()
                    if "code=" in response and "state=" in response:
                        redirect_response = response
                        #print("redirect URL now written!")
                        print(f"redirect URL {redirect_response}")
                        # Fetch token and store it in the participant object
                        token = fitbit.fetch_token(self.TOKEN_URL, authorization_response=redirect_response,
                                                   client_secret=self.client_secret)
                        participant.token = token
                        print(f"Assigned fitbit id: {participant.assigned_fitbit}")
                        print(f"Returned token user id: {token['user_id']}")
                        if participant.assigned_fitbit == token['user_id']:
                            participant.is_authorized = True
                            participant_manager.save_token(participant)
                            log.info(f"Authorization successful for participant {participant.participant_id}")
                            print(f"Authorization successful for participant {participant.participant_id}")
                        else:
                            participant_manager.participants_error.append(participant.participant_id)
                            log.warning(f"Fitbit profile and participant device mis-match for user {participant.participant_id}/nThis user will be skipped")
                            print(f"Fitbit profile and participant device mis-match for user {participant.participant_id}/nThis user will be skipped")
                        break
            time.sleep(2)
        if not redirect_response:
            raise TimeoutError("Timeout: Did not receive auth code within expected time.")


    def collect_intraday_data(self, session: Session, pm: ParticipantManager):
        user_id = session.device.device_id
        #print('user here', user_id)
        if not session.participant.is_authorized:
            log.info(f"User {user_id} is not authorized. Need to authorise user")
            print(f"User {user_id} is not authorized. Need to authorise user")
            self.get_fitbit_oauth(session.participant)

        self.ensure_token_valid(session.participant, pm)  # what if token became invalid at this second????
        fitbit = OAuth2Session(self.client_id, token=session.participant.token)
        steps_df = []
        heart_rate_df = []
        step_counts = None
        heartrate = None
        if "activity" in self.SCOPES:
            for sleep_date in session.participant.collection_days:
                steps_url = self.FITBIT_API_BASE_URL + self.FITBIT_STEPS_ENDPOINT_EACH.format(fitbit_device_id=user_id,
                                                                                              sleep_date=sleep_date)
                response = fitbit.get(steps_url)
                if response.status_code == 403:
                    log.error(f"insufficient permissions for intraday data for {session.participant.participant_id} - activity")
                    raise Exception(f"insufficient permissions for intraday data - activity")
                if response.status_code != 200:
                    log.error(f"Error fetching sleep data for participant {session.participant.participant_id} and date {sleep_date}: {response.status_code} - {response.text}")
                    raise Exception(
                        f"Error fetching sleep data for participant {session.participant.participant_id} and date {sleep_date}: {response.status_code} - {response.text}")
                steps_data = response.json()
                date = steps_data["activities-steps"][0]["dateTime"]
                intraday_data = steps_data["activities-steps-intraday"]["dataset"]
                time_steps = [(entry["time"], entry["value"]) for entry in intraday_data]

                df = pd.DataFrame(time_steps, columns=["time", "activity_steps"])
                df["date"] = date
                df['pid'] = session.participant.participant_id
                df = df[['pid', 'date', 'time', "activity_steps"]]
                steps_df.append(df)
            step_counts = pd.concat(steps_df, ignore_index=True) if len(steps_df) > 0 else None

                ######heart rate ##################
            if "heartrate" in self.SCOPES:
                for sleep_date in session.participant.collection_days:
                    hr_url = self.FITBIT_API_BASE_URL + self.FITBIT_HR_ENDPOINT_EACH.format(fitbit_device_id=user_id,
                                                                                            sleep_date=sleep_date)
                    response = fitbit.get(hr_url)
                    if response.status_code == 403:
                        raise Exception(f"insufficient permissions for intraday data - heartrate")

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
                heartrate = pd.concat(heart_rate_df, ignore_index=True) if len(heart_rate_df) > 0 else None
        return step_counts, heartrate

    def collect_sleep_data(self, session: Session, pm: ParticipantManager):
        user_id = session.device.device_id
        print('user here', user_id)
        if not session.participant.is_authorized:
            log.info(f"User {user_id} is not authorized. Initiating authorization flow...")
            print(f"User {user_id} is not authorized. Initiating authorization flow...")
            self.get_fitbit_oauth(session.participant)

        self.ensure_token_valid(session.participant, pm)
        fitbit = OAuth2Session(self.client_id, token=session.participant.token)
        sleep_data = ''
        if session.participant.is_consecutive_days:
            start_date = session.participant.collection_days[0]
            end_date = session.participant.collection_days[-1]
            #print(f'Data collection days: {start_date} to {end_date}')
            url = self.FITBIT_API_BASE_URL + self.FITBIT_SLEEP_ENDPOINT_RANGE.format(fitbit_device_id=user_id,
                                                                                     start_date=start_date,
                                                                                     end_date=end_date)
            #print('URL', url)
            response = fitbit.get(url)
            #print("response", response.text)
            #print(response.json())
            if response.status_code != 200:
                log.error(f"Error fetching sleep data: {response.status_code} - {response.text}")
                raise Exception(f"Error fetching sleep data: {response.status_code} - {response.text}")
            sleep_data = response.json()['sleep']

            util.dump_data(session.participant.participant_id, start_date, end_date, sleep_data)
        else:
            all_sleep_data = []

            for sleep_date in session.participant.collection_days:
                url = self.FITBIT_API_BASE_URL + self.FITBIT_SLEEP_ENDPOINT_EACH.format(fitbit_device_id=user_id,
                                                                                        sleep_date=sleep_date)
                response = fitbit.get(url)
                #print('Sleep Date ' + sleep_date)
                #print(response.json())
                #print(response.status_code)
                if response.status_code != 200:
                    raise Exception(
                        f"Error fetching sleep data for participant {session.participant.participant_id} and date {sleep_date}: {response.status_code} - {response.text}")
                if len(response.json()['sleep']) > 0:
                    one_sleep_data = response.json()['sleep'][0]
                    all_sleep_data.append(one_sleep_data)
                    sleep_data = all_sleep_data
                else:
                    log.info(f"no sleep data for user {user_id} on {sleep_date}")
                    print(f"no sleep data for user {user_id} on {sleep_date}")
        util.dump_data(session.participant.participant_id, session.participant.collection_days[0],
                       session.participant.collection_days[-1], sleep_data)
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
        return sorted, sleep_stages.sort_values(by=['pid', 'date', 'time'], ascending=[True, True, True])

    def collect_fitbit_data(self, participant_manager: ParticipantManager):
        root_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
        output_path = os.path.join(root_folder, "processed_data")
        os.makedirs(output_path, exist_ok=True)
        active_sessions = participant_manager.get_active_sessions()
        all_participant = []
        all_participant_intraday_steps = []
        all_participant_intraday_hr = []
        all_participant_sleep_stages = []
        for session in active_sessions:
            participant = session.participant
            if participant.participant_id in participant_manager.participants_error:
                log.warning(f"{participant.participant_id} is skipped")
                print(f"{participant.participant_id} is skipped")
                continue
            user_id = session.device.device_id

            print(f"Collecting sleep data for participant {participant.participant_id}")
            try:
                df_sleep, df_sleep_stages = self.collect_sleep_data(session, participant_manager)
                if df_sleep is None:
                    print(f"No sleep data was found for user {user_id}.")
                    continue
                all_participant.append(df_sleep)
                all_participant_sleep_stages.append(df_sleep_stages)
                if "activity" in self.SCOPES or "heartrate" in self.SCOPES:
                    df_steps, df_hr = self.collect_intraday_data(session, participant_manager)
                    if df_steps is not None:
                        all_participant_intraday_steps.append(df_steps)
                    if df_hr is not None:
                        all_participant_intraday_hr.append(df_hr)
            except Exception as ex:
                log.error(f"Error collecting data for participant {participant.participant_id}: {str(ex)}")
                print(f"Error collecting data for participant {participant.participant_id}: {str(ex)}")
                continue
        if not all_participant:
            print(f"No data to process. All participants were skipped/failed")
        else:
            #sleep data and stages
            pd_for_all = pd.concat(all_participant, ignore_index=True)
            pd_ss_all = pd.concat(all_participant_sleep_stages, ignore_index=True)
            pd_for_all.to_csv(os.path.join(output_path, "all_sleep_data.csv"), index=False)
            pd_ss_all.to_csv(os.path.join(output_path," all_fitbit_ss.csv"), index=False)
            #intraday data
            if len(all_participant_intraday_steps) > 0:
                pd_steps_all = pd.concat(all_participant_intraday_steps, ignore_index=True)
                pd_steps_all.to_csv(os.path.join(output_path, "all_step_counts.csv"), index=False)
            if len(all_participant_intraday_hr) > 0:
                pd_hr_all = pd.concat(all_participant_intraday_hr, ignore_index=True)
                pd_hr_all.to_csv(os.path.join(output_path,"all_heart_rate.csv"), index=False)
