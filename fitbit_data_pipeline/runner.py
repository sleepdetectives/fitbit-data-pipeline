import csv
import time

from fitbit_data_pipeline.Classes.DataCollector import DataCollector
from fitbit_data_pipeline.Classes.Participant import Participant, Device
from fitbit_data_pipeline.Classes.PManager import ParticipantManager
import config as cfg
import os
import fitbit_data_pipeline.Utility as util

client_id = os.getenv("client_id")
client_secret = os.getenv("client_secret")
redirect_uri = cfg.REDIRECT_URI


def execute():
    root_folder = os.getcwd()
    print(f"Root folder: {root_folder}")
    output_path = os.path.join(root_folder, "logs")
    os.makedirs(output_path, exist_ok=True)
    data_collector = DataCollector(client_id, client_secret, redirect_uri)
    participant_manager = ParticipantManager()
    log = util.get_logger()

    try:
        with open(root_folder+'/participants_.csv', "r") as file:
            p_data = csv.DictReader(file)
            ##print("I got here")
            #log.info("Welcome Here!")
            participants = []
            devices = []
            for p in p_data:
                #print(p["pid"] + p["age"] )
               # print(p["study_period"].split(',') )
                try:
                    participant = Participant(p["pid"], p["age"], p["study_period"].split(','), p["collection_dates"].split(';'))
                    participants.append(participant)
                    device = Device(p["fitbit_id"], p["device_model"])
                    devices.append(device)
                except Exception as e:
                    log.error(f"Skipping - {e}")
            for participant, device in zip(participants, devices):
                try:
                    participant_manager.add_participant(participant)
                    participant_manager.add_device(device)

                    participant_manager.assign_device_to_participant(participant.participant_id,device.device_id)
                    participant.assigned_fitbit = device.device_id
                    data_collector.get_fitbit_oauth(participant, participant_manager)
                    time.sleep(3)
                except Exception as e:
                    participant_manager.participants_error.append(participant.participant_id)
                    log.info(f"Participant {participant.participant_id} returned with error {e} and thus skipping")
            # Collect Data for All Participants
            data_collector.collect_fitbit_data(participant_manager)


            for participant in participants:
                session = participant_manager.get_participant_session(participant.participant_id)
                if session:
                    participant_manager.end_session(session, participant.study_period[1])
    except FileNotFoundError:
        print("Opps! No participant file found. Are you sure you have participants_.csv in fitbit_data_pipeline directory?.")

