import time

class HysteresisTimer:
    def __init__(self, interval: float):
        self.interval = interval
        self.last_trigger_time = time.monotonic()

    def check(self) -> bool:
        current_time = time.monotonic()
        if current_time - self.last_trigger_time >= self.interval:
            self.last_trigger_time = current_time
            return True
        return False
