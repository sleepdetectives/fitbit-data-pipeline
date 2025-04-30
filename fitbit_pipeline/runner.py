import json
from fitbit_pipeline.Classes.DataCollector import DataCollector
from fitbit_pipeline.Classes.Init import Participant, Device
from fitbit_pipeline.Classes.PManager import ParticipantManager
import config as cfg
import os

client_id = os.getenv("client_id")
client_secret = os.getenv("client_secret")
redirect_uri = cfg.REDIRECT_URI


def execute():
    data_collector = DataCollector(client_id, client_secret, redirect_uri)
    participant_manager = ParticipantManager()

    try:
        with open('fitbit_pipeline/participants.json', "r") as file:
            p_data = json.load(file)
            print("I got here")

            participants = []
            devices = []
            for p in p_data["participants"]:
                participant = Participant(p["pid"], p["age"], p["study_period"], p["collection_dates"])
                participants.append(participant)
                device = Device(p["device"]["fitbit_id"], p["device"]["model"])
                devices.append(device)

            for participant, device in zip(participants, devices):
                participant_manager.add_participant(participant)
                participant_manager.add_device(device)

                participant_manager.assign_device_to_participant(participant.participant_id,device.device_id)  # assign each participant a device
                data_collector.get_fitbit_oauth(participant, participant_manager)  # Authorize the app
            # Collect Data for All Participants
            data_collector.collect_sleep_all(participant_manager)

            for participant in participants:
                session = participant_manager.get_participant_session(participant.participant_id)
                if session:
                    participant_manager.end_session(session,
                                                    participant.study_period[1])  # end all current session for participants
    except FileNotFoundError:
        print("Opps! No participant file found. Are you sure you have participants.json in fitbit_pipeline directory?.")

