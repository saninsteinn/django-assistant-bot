import time
from typing import Dict


class TimeDebugger:

    info: Dict

    def __init__(self, debug_info: Dict, key: str = None):
        if key:
            if key not in debug_info:
                debug_info[key] = {}
            self.info = debug_info[key]
        else:
            self.info = debug_info

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._execution_time = self.execution_time
        self.info['took'] = self.execution_time

    @property
    def execution_time(self) -> float:
        try:
            return self._execution_time
        except AttributeError:
            return time.time() - self.start_time
