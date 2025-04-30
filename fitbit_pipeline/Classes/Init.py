from datetime import datetime
import pandas as pd
from pandas import to_datetime


class Participant:
    def __init__(self, participant_id: str, age: int, study_period: tuple, collection_days: list):
        self.participant_id = participant_id
        self.age = age
        self.study_period = study_period  # (start_date, end_date)
        self.collection_days = collection_days
        self.is_consecutive_days = self.check_consecutive()
        self.token = None  # Fitbit authorisation token
        self.is_authorized = False  # Authorization status

    def check_consecutive(self):
        study_start = to_datetime(self.study_period[0])
        study_end = to_datetime(self.study_period[1])
        collection_dates = sorted(pd.to_datetime(self.collection_days))
        self.collection_days = [date.strftime('%Y-%m-%d') for date in collection_dates]
        print('Sorted Collection Days', collection_dates)
        within_range = all(study_start <= date <= study_end for date in collection_dates)
        if not within_range:
            print(f"One or more of Collection dates out of range for  {self.participant_id}. Please check!")
            return False
        for i in range(1, len(collection_dates)):
            if (collection_dates[i] - collection_dates[i - 1]).days != 1:
                return False #not consecutive days
        return True #consecutive days


class Device:
    def __init__(self, fitbit_user_id: str, model: str):
        self.device_id = fitbit_user_id
        self.model = model
        self.current_session = None  # The current session (assigned participant) for the device

    def assign_to_participant(self, session):
        self.current_session = session

    def release_device(self):
        self.current_session = None


class Session:
    def __init__(self, participant: Participant, device: Device, start_time: datetime, end_time: datetime = None):
        self.participant = participant
        self.device = device
        self.start_time = start_time
        self.end_time = end_time

    def end_session(self, end_time: datetime):
        self.end_time = end_time