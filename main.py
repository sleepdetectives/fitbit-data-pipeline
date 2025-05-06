import fitbit_pipeline.runner as pipeline_runner

if __name__ == '__main__':
    try:
        print("Launching the Fitbit data collection pipeline")
        pipeline_runner.execute()
    except Exception as e:
        print(f"An error has occured: {e}")


