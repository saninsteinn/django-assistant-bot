import inspect
import json
import os


def load_test_data(filename):
    with open(filename, 'r') as file:
        return json.load(file)


def local_fixture(file_name: str):
    caller_frame = inspect.stack()[1]
    caller_filepath = caller_frame.filename

    test_data_filepath = os.path.join(os.path.dirname(caller_filepath), file_name)
    return load_test_data(test_data_filepath)
