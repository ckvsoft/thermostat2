# -*- coding: utf-8 -*-
#
# Copyright (c) 2026 Chris (ckvsoft) <chris@ckvsoft.at>
# SPDX-License-Identifier: MIT

"""Temperature schedule handling (heat/cool) for the thermostat.

Dependencies are injected, so this module touches neither Kivy widgets
nor global thermostat state directly.
"""

import time

import schedule
from kivy.storage.jsonstore import JsonStore


class Scheduler(object):
    def __init__(self, app, apply_set_temp, temp_scale, units,
                 use_test_schedule, schedule_lock, thermostat_lock, log,
                 schedule_file="thermostat_schedule.json"):
        self.app = app
        self._apply_set_temp = apply_set_temp
        self.temp_scale = temp_scale
        self.units = units
        self.use_test_schedule = use_test_schedule
        self._schedule_lock = schedule_lock
        self._thermostat_lock = thermostat_lock
        self._log = log
        self._schedule_file = schedule_file

    def set_scheduled_temp(self, temp):
        with self._thermostat_lock:
            if not self.app.hold:
                self._apply_set_temp(round(temp, 1))
                self._log.state("temperature", str(self.app.set_temp))

    def reload(self):
        with self._schedule_lock:
            schedule.clear()
            active_sched = None

            with self._thermostat_lock:
                store = JsonStore(self._schedule_file)

                if not self.app.hold:
                    if self.app.heat:
                        active_sched = store["heat"]
                        self._log.info("custom/load", "heat")
                    elif self.app.cool:
                        active_sched = store["cool"]
                        self._log.info("custom/load", "cool")

                    if self.use_test_schedule:
                        active_sched = self._test_schedule()
                        self._log.info("custom/load", "test")

            if active_sched is not None:
                for day, entries in active_sched.items():
                    for entry in entries:
                        getattr(schedule.every(), day).at(entry[0]).do(self.set_scheduled_temp, entry[1])
                        self._log.debug("text", f"Set {day}, at: {entry[0]} = {entry[1]}{self.units}")

    def run_forever(self):
        self._log.info("text", "Started")
        while True:
            try:
                if not self.app.hold:
                    with self._schedule_lock:
                        self._log.debug("text", "Running pending")
                        schedule.run_pending()
            except Exception as e:
                self._log.error("text", f"Scheduler error: {e}")

            time.sleep(10)

    def _test_schedule(self):
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        test_sched = {}
        base_low = 19.0 if self.temp_scale == "metric" else 68.0
        base_high = 22.0 if self.temp_scale == "metric" else 72.0

        for i, day in enumerate(days):
            entries = []
            for minute in range(60 * 24):
                hrs, mins = divmod(minute, 60)
                base = base_low if minute % 2 == 1 else base_high
                entries.append([f"{hrs:02d}:{mins:02d}", float(i + 1) / 10.0 + base])
            test_sched[day] = entries

        return test_sched
