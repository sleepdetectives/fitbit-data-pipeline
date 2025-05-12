def start_server():
    from fitbit_data_pipeline.auth.app_server import app
    app.run(ssl_context='adhoc', port=105)


def run_pipeline():
    from fitbit_data_pipeline.runner import execute
    execute()