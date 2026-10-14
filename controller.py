# -*- coding: utf-8 -*-
#
# Copyright (c) 2023-2026 Chris (ckvsoft) <chris@ckvsoft.at>
# SPDX-License-Identifier: MIT

"""Thermostat control loop: sensor reading, heating/cooling relays and
the UI/status updates that go with them."""

import json
import time

from logging_setup import (LOG_LEVEL_DEBUG, LOG_LEVEL_ERROR,
                           LOG_LEVEL_STATE)

CHILD_DEVICE_TEMP = "temperatureSensor"
CHILD_DEVICE_HEAT = "heat"
CHILD_DEVICE_COOL = "cool"
CHILD_DEVICE_FAN = "fan"
CHILD_DEVICE_UICONTROL_SLIDER = "tempSlider"

MSG_SUBTYPE_TEXT = "text"
MSG_SUBTYPE_TEMPERATURE = "temperature"
MSG_SUBTYPE_BINARY_STATUS = "binaryStatus"
MSG_SUBTYPE_CUSTOM = "custom"


class ThermostatController(object):
    def __init__(self, app, ui, gpio, log, mqtt, state_store, lock,
                 heat_pin, cool_pin, fan_pin, temp_hysteresis, units,
                 sensor, sensor_unit, calibration, tolerance,
                 min_flow_temp, current_flow_temp, use_test_schedule,
                 hotwater, publish_faikin, reload_schedule):
        self.app = app
        self.ui = ui
        self.gpio = gpio
        self._log = log
        self.mqtt = mqtt
        self.state = state_store
        self.lock = lock
        self.heat_pin = heat_pin
        self.cool_pin = cool_pin
        self.fan_pin = fan_pin
        self.temp_hysteresis = temp_hysteresis
        self.units = units
        self.sensor = sensor
        self.sensor_unit = sensor_unit
        self.calibration = calibration
        self.tolerance = tolerance
        self.min_flow_temp = min_flow_temp
        self.current_flow_temp = current_flow_temp
        self.use_test_schedule = use_test_schedule
        self.hotwater = hotwater
        self._publish_faikin = publish_faikin
        self._reload_schedule = reload_schedule
        self._prior_corrected = -100.0
        self._last_persisted_state = None

    def get_status_info(self):
        app = self.app
        gpio = self.gpio
        with self.lock:
            sched = "None"
            if app.hold:
                sched = _("Hold")
            elif self.use_test_schedule:
                sched = "Test"
            elif app.heat:
                sched = _("Heat")
            elif app.cool:
                sched = _("Cool")

            status_info = {
                'heat': ("[color=00ff00][b]" + _("On") + "[/b][/color]") if not gpio.input(self.heat_pin) else _("Off"),
                'cool': ("[color=00ff00][b]" + _("On") + "[/b][/color]") if not gpio.input(self.cool_pin) else _("Off"),
                'fan': ("[color=00ff00][b]" + _("On") + "[/b][/color]") if gpio.input(self.fan_pin) else _("Auto"),
                'sched': sched
            }

            return json.dumps(status_info)

    def change_system_settings(self):
        app = self.app
        gpio = self.gpio
        with self.lock:
            hpin_start = str(gpio.input(self.heat_pin))
            cpin_start = str(gpio.input(self.cool_pin))
            fpin_start = str(gpio.input(self.fan_pin))

            if app.heat:
                gpio.output(self.cool_pin, gpio.HIGH)

                if app.set_temp >= app.current_temp + self.temp_hysteresis:
                    gpio.output(self.heat_pin, gpio.LOW)
                    gpio.output(self.fan_pin, gpio.LOW)
                elif app.set_temp <= app.current_temp:
                    gpio.output(self.heat_pin, gpio.HIGH)
                    if not app.fan and gpio.input(self.cool_pin):
                        gpio.output(self.fan_pin, gpio.HIGH)
            else:
                gpio.output(self.heat_pin, gpio.HIGH)

                if app.cool:
                    if app.set_temp <= app.current_temp - self.temp_hysteresis:
                        gpio.output(self.cool_pin, gpio.LOW)
                        gpio.output(self.fan_pin, gpio.LOW)
                    elif app.set_temp >= app.current_temp:
                        gpio.output(self.cool_pin, gpio.HIGH)
                        if not app.fan and gpio.input(self.heat_pin):
                            gpio.output(self.fan_pin, gpio.LOW)
                else:
                    gpio.output(self.cool_pin, gpio.HIGH)
                    if not app.fan and gpio.input(self.heat_pin):
                        gpio.output(self.fan_pin, gpio.HIGH)

            self._log(LOG_LEVEL_STATE, CHILD_DEVICE_TEMP, MSG_SUBTYPE_TEMPERATURE, "minFlow: " + str(self.min_flow_temp))
            self._log(LOG_LEVEL_STATE, CHILD_DEVICE_TEMP, MSG_SUBTYPE_TEMPERATURE, "currentFlow: " + str(self.current_flow_temp))

            if app.fan:
                gpio.output(self.fan_pin, gpio.HIGH)
                self._set_mqtt_fan_command("on")
                self._log(LOG_LEVEL_STATE, CHILD_DEVICE_FAN, MSG_SUBTYPE_TEXT, "fan forced on")
            else:
                self._set_mqtt_fan_command("off")
                if gpio.input(self.heat_pin) and gpio.input(self.cool_pin):
                    gpio.output(self.fan_pin, gpio.LOW)
                    self._log(LOG_LEVEL_STATE, CHILD_DEVICE_FAN, MSG_SUBTYPE_TEXT, "fan off (idle)")

            # persist state across restarts, only when changed (spares the SD card)
            current_state = (app.set_temp, app.heat, app.cool, app.fan, app.hold)
            if current_state != self._last_persisted_state:
                self.state.put("state", setTemp=app.set_temp,
                               heatControl="down" if app.heat else "normal",
                               coolControl="down" if app.cool else "normal",
                               fanControl="down" if app.fan else "normal",
                               holdControl="down" if app.hold else "normal")
                self._last_persisted_state = current_state

            status_info = json.loads(self.get_status_info())
            self.ui.statusHeatValueLabel.text = status_info['heat']
            self.ui.statusCoolValueLabel.text = status_info['cool']
            self.ui.statusFanValueLabel.text = status_info['fan']
            self.ui.statusSchedValueLabel.text = status_info['sched']

            if hpin_start != str(gpio.input(self.heat_pin)):
                self._log(LOG_LEVEL_STATE, CHILD_DEVICE_HEAT, MSG_SUBTYPE_BINARY_STATUS, "1" if gpio.input(self.heat_pin) else "0")
            if cpin_start != str(gpio.input(self.cool_pin)):
                self._log(LOG_LEVEL_STATE, CHILD_DEVICE_COOL, MSG_SUBTYPE_BINARY_STATUS, "1" if gpio.input(self.cool_pin) else "0")
            if fpin_start != str(gpio.input(self.fan_pin)):
                self._log(LOG_LEVEL_STATE, CHILD_DEVICE_FAN, MSG_SUBTYPE_BINARY_STATUS, "1" if gpio.input(self.fan_pin) else "0")

            if self.mqtt.enabled:
                self._publish_faikin()

    def control_callback(self, control):
        app = self.app
        ui = self.ui
        with self.lock:
            ui.setControlState(control, control.state)

            if control is ui.coolControl:
                if control.state == "down":
                    ui.setControlState(ui.heatControl, "normal")
                    app.heat = False
                app.cool = control.state == "down"

            if control is ui.heatControl:
                if control.state == "down":
                    ui.setControlState(ui.coolControl, "normal")
                    app.cool = False
                app.heat = control.state == "down"

            if control is ui.fanControl:
                app.fan = control.state == "down"

            if control is ui.holdControl:
                app.hold = control.state == "down"

        # reload() takes the schedule lock and, inside it, the thermostat
        # lock. Calling it while holding the thermostat lock would invert
        # the global lock order and deadlock against the scheduler thread,
        # so it runs after the lock is released (see scheduler.py reload).
        if control is ui.coolControl or control is ui.heatControl:
            self._reload_schedule()

    def check_sensor_temp(self, dt):
        app = self.app
        ui = self.ui
        with self.lock:
            if self.sensor is not None:
                try:
                    raw_temp = self.sensor.get_temperature(self.sensor_unit)
                    cal = self.calibration
                    corrected = (((raw_temp - cal["freezing_measured"]) * cal["reference_range"]) / cal["measured_range"]) + cal["freezing_point"]
                    app.current_temp = round(corrected, 1)
                    self._log(LOG_LEVEL_DEBUG, CHILD_DEVICE_TEMP, MSG_SUBTYPE_CUSTOM + "/raw", str(raw_temp))
                    self._log(LOG_LEVEL_DEBUG, CHILD_DEVICE_TEMP, MSG_SUBTYPE_CUSTOM + "/corrected", str(corrected))

                    if abs(self._prior_corrected - corrected) >= self.tolerance:
                        self._log(LOG_LEVEL_STATE, CHILD_DEVICE_TEMP, MSG_SUBTYPE_TEMPERATURE, str(app.current_temp))
                        self._prior_corrected = corrected
                except Exception as e:
                    self._log(LOG_LEVEL_ERROR, CHILD_DEVICE_TEMP, MSG_SUBTYPE_TEXT, f"Sensor read failed: {e}")

            ui.currentLabel.text = "[b]" + str(app.current_temp) + self.units + "[/b]"
            ui.altCurLabel.text = ui.currentLabel.text

            ui.dateLabel.text = "[b]" + time.strftime("%a %d. %b %Y") + "[/b]"

            time_str = time.strftime("%H:%M")

            ui.timeLabel.text = ("[b]" + (time_str if time_str[0:1] != "0" else time_str[1:]) + "[/b]").lower()
            ui.altTimeLabel.text = ui.timeLabel.text

            self.change_system_settings()

            if self.hotwater is not None and self.hotwater.enabled:
                try:
                    self.hotwater.update_water_temp(app.domestic_water)
                except Exception as e:
                    self._log(LOG_LEVEL_ERROR, CHILD_DEVICE_TEMP, MSG_SUBTYPE_TEXT, f"hotwater control error: {e}")

    def update_set_temp(self, slider, value):
        with self.lock:
            prior_temp = self.app.set_temp
            self.app.set_temp = round(slider.value, 1)
            self.ui.setLabel.text = "  Set\n[b]" + str(self.app.set_temp) + self.units + "[/b]"
            if prior_temp != self.app.set_temp:
                self._log(LOG_LEVEL_STATE, CHILD_DEVICE_UICONTROL_SLIDER, MSG_SUBTYPE_TEMPERATURE, str(self.app.set_temp))

    def apply_set_temp(self, new_temp):
        self.app.set_temp = new_temp
        self.ui.setLabel.text = "  Set\n[b]" + str(self.app.set_temp) + self.units + "[/b]"
        self.ui.tempSlider.value = self.app.set_temp

    def apply_controls(self, heat, cool, fan, hold):
        ui = self.ui
        ui.setControlState(ui.heatControl, "down" if heat else "normal")
        ui.setControlState(ui.coolControl, "down" if cool else "normal")
        ui.setControlState(ui.fanControl, "down" if fan else "normal")
        ui.setControlState(ui.holdControl, "down" if hold else "normal")
        self.app.heat = bool(heat)
        self.app.cool = bool(cool)
        self.app.fan = bool(fan)
        self.app.hold = bool(hold)

    def _set_mqtt_fan_command(self, state):
        if self.mqtt.enabled:
            self.mqtt.publish(self.mqtt.state_topic("fan"), state)
