import logging
import os
import json
import platform
import subprocess
from pathlib import Path

import pandas as pd
from datetime import datetime, timedelta


root_folder = os.getcwd()
print("The current working directory:",root_folder)
def get_time(date_time_str):
    """Convert a timestamp string to a time object."""
    return datetime.strptime(date_time_str, '%Y-%m-%dT%H:%M:%S.%f').time()


def dump_data(uid, start_date, end_date, sleep_data):
    """Save sleep data as a JSON file."""
    #folder_path = "./raw_sleep_data"
    dump_path = os.path.join(root_folder, 'raw_sleep_data')
    os.makedirs(dump_path, exist_ok=True)

    file_path = os.path.join(dump_path, f"{uid}_{start_date}_to_{end_date}.json")

    with open(file_path, "w") as json_file:
        json.dump(sleep_data, json_file, indent=4)

    log = get_logger()
    log.info(f"Sleep data saved to {file_path}")
    print(f"Sleep data saved to {file_path}")


def time_diff(time1, time2):
    """Calculate the difference in minutes between two time objects."""
    if isinstance(time1, str):
        time1 = datetime.strptime(time1, "%H:%M").time()
    if isinstance(time2, str):
        time2 = datetime.strptime(time2, "%H:%M").time()

    dt1, dt2 = datetime.combine(datetime.today(), time1), datetime.combine(datetime.today(), time2)

    # Handle cases where time2 is past midnight
    if dt2 < dt1:
        dt2 += timedelta(days=1)

    return (dt2 - dt1).seconds / 60


def process_sleep_response(pid, sleep_data):
    """Process sleep data and return structured DataFrames."""
    all_sleep = []
    all_sleep_stages = []

    for night in sleep_data:
        levels_data = night['levels']['data']


        bed_time, out_of_bed_time = get_time(night['startTime']), get_time(night['endTime'])
        minutesAwake = night['minutesAwake']
        minutesAsleep = night['minutesAsleep']
        timeInBed = night['timeInBed']
        efficiency = night['efficiency']
        type = night['type']
        short_data = night['levels'].get('shortData', [])

        ############## This block contained derived values ########################################
        sleep_start = get_time(levels_data[0]['dateTime']) if(levels_data[0]['level'] != "wake") else get_time(levels_data[1]['dateTime'])
        wake_start = get_time(night['endTime']) if (levels_data[-1]['level'] != 'wake') else get_time(levels_data[-1]['dateTime'])
        SOL = 0 if levels_data[0]['level'] != 'wake' else levels_data[0]['seconds'] / 60
        WASO = night['minutesAwake'] - SOL
        TST = time_diff(sleep_start, wake_start) - WASO
        SE = round((TST / timeInBed),2) * 100 if minutesAsleep else 0
        ############## This block contained derived values ########################################
        # Extract sleep stage summary data
        summary = night['levels'].get('summary', {})
        stage_counts = {stage: summary.get(stage, {}).get('count', 0) for stage in ['wake', 'rem', 'light', 'deep']}
        stage_minutes = {stage: summary.get(stage, {}).get('minutes', 0) for stage in ['wake', 'rem', 'light', 'deep']}

        # Store sleep data
        sleep_df = pd.DataFrame([{
            'pid': pid,
            'date': night['dateOfSleep'],
            'StartTime': bed_time,
            'EndTime': out_of_bed_time,
            'TimeInBed': timeInBed,
            'MinutesAwake': minutesAwake,
            'TotalSleepTime': minutesAsleep,
            **stage_counts,
            **stage_minutes,
            'SleepEfficiency': efficiency,
            'sleep_time': sleep_start,
            'wake_time': wake_start,
            'SOL': SOL,
            'WASO': WASO,
            'TST': TST,
            'SE': SE,
            'LogType': type,
            'isMainSleep': night['isMainSleep'],
        }])

        all_sleep.append(sleep_df)

        if night['type'] == 'stages':
            sleep_stages_df = get_fitbit_epoch(pid, levels_data, short_data)
            all_sleep_stages.append(sleep_stages_df)

    sleep_df = pd.concat(all_sleep, ignore_index=True) if all_sleep else None
    sleep_stages_df = pd.concat(all_sleep_stages, ignore_index=True) if all_sleep_stages else None

    return sleep_df, sleep_stages_df


def get_fitbit_epoch(pid, data, short_data):
    """Convert Fitbit sleep data into 30-second epochs."""
    stage_map = {"wake": "W", "light": "L", "deep": "D", "rem": "R"}
    short_wakes = {datetime.fromisoformat(sh['dateTime']).strftime("%H:%M:%S") for sh in short_data for _ in
                   range(sh['seconds'] // 30)}

    epochs = []
    for entry in data:
        start_time = datetime.fromisoformat(entry['dateTime'])
        stage = stage_map.get(entry['level'], "")

        for _ in range(entry['seconds'] // 30):
            time_str = start_time.strftime("%H:%M:%S")
            if time_str in short_wakes:
                stage = "W"
            epochs.append({"pid": pid, "date": start_time.strftime("%Y-%m-%d"), "time": time_str, "sleep_stage": stage})
            start_time += timedelta(seconds=30)

    return pd.DataFrame(epochs)


def browser_incognito(url):
    if platform.system() == "Windows":
        subprocess.Popen(f'start chrome --new-window --incognito "{url}"', shell=True)


def get_logger(log_file= 'app.log'):
    logger = logging.getLogger(log_file)

    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        log_path = Path.cwd() / 'logs'
        log_path.mkdir(parents=True, exist_ok=True)

        file_path = log_path / log_file
        file_handler = logging.FileHandler(file_path)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
