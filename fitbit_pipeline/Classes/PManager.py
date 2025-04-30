import json
from datetime import datetime
from fitbit_pipeline.Classes.Init import Device
from fitbit_pipeline.Classes.Init import Participant
from fitbit_pipeline.Classes.Init import Session
from dotenv import set_key
import os

env_file = ('');os.path.join(os.path.dirname(os.path.dirname(__file__)), '.')

class ParticipantManager:
    def __init__(self):
        self.participants = {}
        self.devices = {}
        self.sessions = []

    def add_participant(self, participant: Participant):
        self.participants[participant.participant_id] = participant
        self.load_token(participant)

    def add_device(self, device: Device):
        self.devices[device.device_id] = device

    def assign_device_to_participant(self, participant_id: str, device_id: str):
        participant = self.participants.get(participant_id)
        device = self.devices.get(device_id)

        if participant is None:
            raise ValueError(f"Participant with ID {participant_id} does not exist.")
        if device is None:
            raise ValueError(f"Device with Fitbit ID {device_id} does not exist.")
        if device.current_session is not None:
            raise ValueError(f"Device {device_id} is currently in use by another participant.")

        # Check if the participant already has an active session
        existing_sessions = self.get_participant_session(participant_id)
        if existing_sessions:
            raise ValueError(f"There is an active session for {participant_id}")

        session_start_time = participant.study_period[0]

        session = Session(participant, device, session_start_time) #new session created for a new participant
        self.sessions.append(session)
        device.assign_to_participant(session)

        print(f"User {participant_id} has been assigned to {device_id} for session starting at {session_start_time}")

    def end_session(self, session: Session, end_time: datetime):
        session.end_session(end_time)
        session.device.release_device()

    def get_active_sessions(self):
        return [s for s in self.sessions if s.end_time is None]

    def get_participant_session(self, participant_id: str):
        for session in self.sessions:
            if session.participant.participant_id == participant_id:
                return session
        return None

    @staticmethod
    def save_token(participant: Participant):
        token_data = {
            'participant_id': participant.participant_id,
            'token': participant.token
        }

        # Load existing tokens from the file
        p_tokens_str = os.getenv("participants_tokens","{}")
        token_json = json.loads(p_tokens_str)

        # Update token for the current participant
        token_json[participant.participant_id] = token_data

        updated_tokens = json.dumps(token_json)
        set_key('.env',"participants_tokens",updated_tokens)
        print(f"Token for participant {participant.participant_id} saved.")

    @staticmethod
    def load_token(participant: Participant):
        try:
            tokens_str = os.getenv("participants_tokens","{}")
            print("Token string", tokens_str)
            token_dic = json.loads(tokens_str)
            print("Token string dic", token_dic)
            # Check if token exists for the participant
            if participant.participant_id in token_dic:
                participant.token = token_dic[participant.participant_id]['token']
                print(participant.participant_id, participant.token)
                participant.is_authorized = True
                print(f"Loaded token for participant {participant.participant_id}")
            else:
                print(f"No token found for participant {participant.participant_id}, re-authorization needed.")

        except FileNotFoundError:
            print("No tokens file found. All participants need to be authorized.")

