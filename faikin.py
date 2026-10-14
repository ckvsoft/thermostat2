# -*- coding: utf-8 -*-
#
# Copyright (c) 2023-2026 Chris (ckvsoft) <chris@ckvsoft.at>
# SPDX-License-Identifier: MIT

"""Daikin AC control via a Faikout/Faikin MQTT module.

Dependencies are injected, so this module stays importable and testable
without Kivy or GPIO.
"""

import json
import traceback

from hysteresistimer import HysteresisTimer


class FaikinController(object):
    """Drives a Daikin unit through a Faikout/Faikin MQTT module.

    get_snapshot() must return the current thermostat state as a dict
    with keys currentTemp, heat (bool), cool (bool) and target.
    """

    def __init__(self, name, enabled, summer_temp, publish, get_snapshot,
                 state_topic, fan_interval=10.0,
                 log_debug=None, log_error=None):
        self.name = name
        self.enabled = bool(enabled)
        self.summer_temp = summer_temp
        self._publish = publish
        self._get_snapshot = get_snapshot
        self.state_topic = state_topic
        self._log_debug = log_debug or (lambda msg: None)
        self._log_error = log_error or (lambda msg: None)

        self.outside_temp = 0.0
        self.prev_target = None
        self.prev_fan = None
        self.fan_timer = HysteresisTimer(fan_interval)

    def handle_status_message(self, message):
        try:
            payload = message.payload
            if isinstance(payload, bytes):
                payload = payload.decode('utf-8')
            data = json.loads(payload)

            # "outside" may be absent, null, a single value or a list
            val = data.get('outside')
            if val is None:
                return
            if isinstance(val, list):
                numeric = [v for v in val if isinstance(v, (int, float))]
                if not numeric:
                    return
                val = sum(numeric) / len(numeric)
            if isinstance(val, (int, float)):
                self.outside_temp = float(val)

        except (json.JSONDecodeError, UnicodeDecodeError, ValueError, TypeError) as e:
            self._log_error("Bad faikin payload: %s" % e)

    def _normalized_outside(self):
        val = self.outside_temp
        if isinstance(val, list):
            numeric = [v for v in val if isinstance(v, (int, float))]
            val = sum(numeric) / len(numeric) if numeric else 0.0
        if not isinstance(val, (int, float)):
            val = 0.0
        return val

    def build_state(self):
        """Thermostat state as JSON (no control attributes like power/temp)."""
        snap = self._get_snapshot()
        current_temp = snap["currentTemp"]
        heat_down = bool(snap.get("heat"))
        cool_down = bool(snap.get("cool"))
        targettemp = snap["target"]

        autop = True
        if self.summer_temp < self._normalized_outside():
            heat_state = False
            autop = False
        else:
            heat_state = heat_down

        if heat_down:
            mode = "H"
        elif cool_down:
            mode = "C"
            if not heat_state:
                autop = True
        else:
            mode = "A"
            autop = False

        rounded_temp = round(current_temp * 2) / 2
        return {
            "env": current_temp,
            "rounded": rounded_temp,
            "diff": targettemp - rounded_temp,
            "heat": heat_state,
            "mode": mode,
            "autop": autop,
            "autot": targettemp,
        }

    def publish_control(self):
        """Publish the state JSON and the control command.

        The control topic needs power/temp/mode/fan/demand; Faikout ignores
        the plain state JSON because it has no "power". The command is sent
        on every cycle: Faikout drops back to its own default demand if the
        value is not re-asserted, which made demand/fan oscillate.
        """
        cur_temp = self._get_snapshot()["currentTemp"]

        try:
            state_data = self.build_state()
            self._publish(self.state_topic, json.dumps(state_data))

            if not self.enabled:
                return

            targettemp = state_data["autot"]
            mode = state_data["mode"]
            power = state_data["autop"]
            rounded_temp = state_data["rounded"]

            if cur_temp is None:
                return

            tolerance = 0.2

            if (mode == "H" and targettemp + 4.0 < rounded_temp) or \
               (mode == "C" and targettemp - 4.0 > rounded_temp):
                power = False

            powerful = False
            fan, demand = "3", 70

            # Deviation seen from the active mode: > 0 means "produce less"
            # (too warm when heating, too cold when cooling), < 0 means
            # "produce more". Gapless so no silent default ever applies.
            if mode == "H":
                temp_diff = cur_temp - targettemp
            elif mode == "C":
                temp_diff = targettemp - cur_temp
            else:
                temp_diff = None

            if temp_diff is not None:
                if temp_diff > 3.0:
                    fan, demand = "1", 30
                elif temp_diff > tolerance:
                    fan, demand = "2", 30
                elif temp_diff >= -tolerance:
                    fan, demand = "3", 70
                elif temp_diff >= -1.0:
                    fan, demand = "4", 95
                else:
                    fan, demand = "5", 100

            # Rate-limit fan changes so the unit does not flip-flop; a new
            # setpoint may change the fan immediately.
            if self.prev_target is not None and self.prev_target != targettemp:
                self.fan_timer.last_trigger_time = 0
            if self.prev_fan is not None and fan != self.prev_fan \
                    and not self.fan_timer.check():
                fan = self.prev_fan

            data = {
                "env": cur_temp,
                "temp": targettemp,
                "powerful": powerful,
                "power": power,
                "mode": mode,
                "fan": fan,
                "demand": demand,
            }
            self._publish("command/%s/control" % self.name, json.dumps(data))
            self._log_debug("control " + json.dumps(data))

            self.prev_target = targettemp
            self.prev_fan = fan

        except Exception as e:
            self._log_error("%s\n%s" % (e, traceback.format_exc()))
