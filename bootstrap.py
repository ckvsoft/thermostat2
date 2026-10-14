# -*- coding: utf-8 -*-
#
# Copyright (c) 2023-2026 Chris (ckvsoft) <chris@ckvsoft.at>
# SPDX-License-Identifier: MIT

"""Composition root: reads settings, builds and wires every component.

`Thermostat.run()` starts the web/scheduler threads and the Kivy app.
"""

import datetime
import gettext
import locale
import os
import os.path
import threading

import kivy

kivy.require('2.3.0')  # keep in sync with requirements.txt

from kivy.storage.jsonstore import JsonStore

import cherrypy

try:
    import RPi.GPIO as GPIO
except ImportError:
    import FakeRPi.GPIO as GPIO

try:
    from w1thermsensor import W1ThermSensor, Unit
except (ImportError, OSError, RuntimeError, Exception) as e:
    print(f"Fehler beim Laden von w1thermsensor: {e}")
    from FakeRPi.w1thermsensor import W1ThermSensor, Unit

try:
    from hotwater_control import HotWaterControl
    hotwater_module_available = True
except ImportError:
    HotWaterControl = None
    hotwater_module_available = False

from faikin import FaikinController
from config import Config
from weather import build_urls, WeatherView
from app_state import AppState
from web import WebInterface
from scheduler import Scheduler
import ui
from controller import ThermostatController
from handlers import Handlers
from app import ThermostatApp
from commands import Commands
from mqtt import MqttService
from logging_setup import (Logger, LOG_LEVEL_DEBUG, LOG_LEVEL_INFO,
                           LOG_LEVEL_ERROR, LOG_LEVEL_STATE, LOG_LEVEL_NONE)

MSG_TYPE_PRESENTATION = "presentation"

CHILD_DEVICE_NODE = "node"
CHILD_DEVICE_MQTT = "mqtt"
CHILD_DEVICE_UICONTROL_HEAT = "heatControl"
CHILD_DEVICE_UICONTROL_COOL = "coolControl"
CHILD_DEVICE_UICONTROL_FAN = "fanControl"
CHILD_DEVICE_UICONTROL_HOLD = "holdControl"
CHILD_DEVICE_UICONTROL_SLIDER = "tempSlider"
CHILD_DEVICE_WEATHER_CURR = "weatherCurrent"
CHILD_DEVICE_WEATHER_FCAST_TODAY = "weatherForecastToday"
CHILD_DEVICE_WEATHER_FCAST_TOMO = "weatherForecastTomorrow"
CHILD_DEVICE_HEAT = "heat"
CHILD_DEVICE_COOL = "cool"
CHILD_DEVICE_FAN = "fan"
CHILD_DEVICE_PIR = "motionSensor"
CHILD_DEVICE_TEMP = "temperatureSensor"
CHILD_DEVICE_SCREEN = "screen"
CHILD_DEVICE_SCHEDULER = "scheduler"
CHILD_DEVICE_WEBSERVER = "webserver"
CHILD_DEVICE_FAIKIN = "faikin"

CHILD_DEVICES = [
    CHILD_DEVICE_NODE, CHILD_DEVICE_MQTT, CHILD_DEVICE_UICONTROL_HEAT,
    CHILD_DEVICE_UICONTROL_COOL, CHILD_DEVICE_UICONTROL_FAN,
    CHILD_DEVICE_UICONTROL_HOLD, CHILD_DEVICE_UICONTROL_SLIDER,
    CHILD_DEVICE_WEATHER_CURR, CHILD_DEVICE_WEATHER_FCAST_TODAY,
    CHILD_DEVICE_WEATHER_FCAST_TOMO, CHILD_DEVICE_HEAT, CHILD_DEVICE_COOL,
    CHILD_DEVICE_FAN, CHILD_DEVICE_PIR, CHILD_DEVICE_TEMP, CHILD_DEVICE_SCREEN,
    CHILD_DEVICE_SCHEDULER, CHILD_DEVICE_WEBSERVER, CHILD_DEVICE_FAIKIN
]

CHILD_DEVICE_SUFFIX_UICONTROL = "Control"

MSG_SUBTYPE_NAME = "sketchName"
MSG_SUBTYPE_VERSION = "sketchVersion"
MSG_SUBTYPE_BINARY_STATUS = "binaryStatus"
MSG_SUBTYPE_TRIPPED = "tripped"
MSG_SUBTYPE_ARMED = "armed"
MSG_SUBTYPE_TEMPERATURE = "temperature"
MSG_SUBTYPE_FORECAST = "forecast"
MSG_SUBTYPE_CUSTOM = "custom"
MSG_SUBTYPE_TEXT = "text"
MSG_SUBTYPE_FAIKIN = "faikin"

THERMOSTAT_VERSION = "2.4.0"

FAIKIN_CONTROL_HEARTBEAT = 60  # seconds between repeated control commands


class _SchedulerLog(object):
    def __init__(self, log):
        self._log = log

    def info(self, subtype, msg):
        self._log(LOG_LEVEL_INFO, CHILD_DEVICE_SCHEDULER, subtype, msg)

    def state(self, subtype, msg):
        self._log(LOG_LEVEL_STATE, CHILD_DEVICE_SCHEDULER, subtype, msg)

    def debug(self, subtype, msg):
        self._log(LOG_LEVEL_DEBUG, CHILD_DEVICE_SCHEDULER, subtype, msg)

    def error(self, subtype, msg):
        self._log(LOG_LEVEL_ERROR, CHILD_DEVICE_SCHEDULER, subtype, msg)


class Thermostat(object):
    def __init__(self, script=None):
        self.script = script or __file__
        self.debug = False
        self.version = THERMOSTAT_VERSION
        self.use_test_schedule = False

        self.thermostat_lock = threading.RLock()
        self.weather_lock = threading.Lock()
        self.schedule_lock = threading.RLock()

        self.cfg = Config()
        self.state_store = JsonStore("thermostat_state.json")

        locale.setlocale(locale.LC_ALL, self.cfg.get("i18n", "locale"))
        gettext.install('thermostat', localedir='locales', names='gettext')

        self.domestic_water_enabled = self.cfg.get("domestic_water", "enabled")
        self.domestic_water_topic = self.cfg.get("domestic_water", "topic")
        domestic_key_value_pair = self.cfg.get("domestic_water", "key_value_pair")
        domestic_timeout_duration = 300  # 5 min

        self.hotwater_control = HotWaterControl(self.cfg.section("hotwater_control")) \
            if hotwater_module_available else None

        self.faikin_enabled = self.cfg.get("faikin", "enabled")
        self.faikin_name = self.cfg.get("faikin", "name")
        self.faikin = None

        self.mqtt = MqttService(
            enabled=self.cfg.get("mqtt", "enabled"),
            client_id=self.cfg.get("mqtt", "clientID"),
            server=self.cfg.get("mqtt", "server"),
            port=self.cfg.get("mqtt", "port"),
            pub_prefix=self.cfg.get("mqtt", "pubPrefix"),
            log=self._mqtt_log,
        )

        self.logger = Logger(
            channel=self.cfg.get("logging", "channel"),
            level_name=self.cfg.get("logging", "level"),
            publish=self.mqtt.publish if self.mqtt.enabled else None,
            log_topic=self.mqtt.log_topic,
        )
        self.log = self.logger.log

        self._log_presentations()

        temp_scale = self.cfg.get("scale", "tempScale")
        self.units = "c" if temp_scale == "metric" else "f"
        precip_units = " mm" if temp_scale == "metric" else '"'
        precip_factor = 1.0 if temp_scale == "metric" else 0.0393701
        precip_round = 0 if temp_scale == "metric" else 1
        sensor_unit = Unit.DEGREES_C if temp_scale == "metric" else Unit.DEGREES_F
        wind_factor = 3.6 if temp_scale == "metric" else 1.0
        wind_units = " km/h" if temp_scale == "metric" else " mph"
        tolerance = 0.1 if temp_scale == "metric" else 0.18
        min_flow_temp = 65.0
        current_flow_temp = 0.0

        saved = self.state_store.get("state") if self.state_store.exists("state") else {}
        self.app_state = AppState(
            current_temp=22.0 if temp_scale == "metric" else 72.0,
            set_temp=saved.get("setTemp", 22.0),
            heat=saved.get("heatControl") == "down",
            cool=saved.get("coolControl") == "down",
            fan=saved.get("fanControl") == "down",
            hold=saved.get("holdControl") == "down",
        )

        temp_hysteresis = self.cfg.get("thermostat", "tempHysteresis")
        self.temp_check_interval = self.cfg.get("thermostat", "tempCheckInterval")
        self.min_ui_enabled = self.cfg.get("thermostat", "minUIEnabled")
        self.min_ui_timeout = self.cfg.get("thermostat", "minUITimeout")

        self._log_temperature_settings(temp_scale, precip_units, precip_factor,
                                       sensor_unit, wind_factor, wind_units,
                                       temp_hysteresis)
        self._log_calibration_settings()

        self.min_temp = self.cfg.get("thermostat", "minTemp")
        self.max_temp = self.cfg.get("thermostat", "maxTemp")
        self.temp_step = self.cfg.get("thermostat", "tempStep")

        self.log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/UISlider/minTemp", str(self.min_temp), timestamp=False)
        self.log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/UISlider/maxTemp", str(self.max_temp), timestamp=False)
        self.log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/UISlider/tempStep", str(self.temp_step), timestamp=False)

        try:
            temp_sensor = W1ThermSensor()
        except Exception as e:
            self.log(LOG_LEVEL_ERROR, CHILD_DEVICE_TEMP, MSG_SUBTYPE_TEXT, f"Sensor init failed: {e}")
            temp_sensor = None

        self.pir_enabled = self.cfg.get("pir", "pirEnabled")
        pir_pin = self.cfg.get("pir", "pirPin")
        self.pir_check_interval = self.cfg.get("pir", "pirCheckInterval")
        pir_ignore_from_str = self.cfg.get("pir", "pirIgnoreFrom")
        pir_ignore_to_str = self.cfg.get("pir", "pirIgnoreTo")
        pir_ignore_from = datetime.time(int(pir_ignore_from_str.split(":")[0]), int(pir_ignore_from_str.split(":")[1]))
        pir_ignore_to = datetime.time(int(pir_ignore_to_str.split(":")[0]), int(pir_ignore_to_str.split(":")[1]))

        self.log(LOG_LEVEL_INFO, CHILD_DEVICE_PIR, MSG_SUBTYPE_ARMED, str(self.pir_enabled), timestamp=False)
        self.log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/pir/checkInterval", str(self.pir_check_interval), timestamp=False)
        self.log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/pir/ignoreFrom", str(pir_ignore_from_str), timestamp=False)
        self.log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/pir/ignoreTo", str(pir_ignore_to_str), timestamp=False)

        cool_pin = self.cfg.get("thermostat", "coolPin")
        heat_pin = self.cfg.get("thermostat", "heatPin")
        fan_pin = self.cfg.get("thermostat", "fanPin")

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(cool_pin, GPIO.OUT)
        GPIO.output(cool_pin, GPIO.HIGH)
        GPIO.setup(heat_pin, GPIO.OUT)
        GPIO.output(heat_pin, GPIO.HIGH)
        GPIO.setup(fan_pin, GPIO.OUT)
        GPIO.output(fan_pin, GPIO.HIGH)

        if self.pir_enabled:
            GPIO.setup(pir_pin, GPIO.IN)

        self.log(LOG_LEVEL_INFO, CHILD_DEVICE_COOL, MSG_SUBTYPE_BINARY_STATUS, str(cool_pin), timestamp=False)
        self.log(LOG_LEVEL_INFO, CHILD_DEVICE_HEAT, MSG_SUBTYPE_BINARY_STATUS, str(heat_pin), timestamp=False)
        self.log(LOG_LEVEL_INFO, CHILD_DEVICE_FAN, MSG_SUBTYPE_BINARY_STATUS, str(fan_pin), timestamp=False)
        self.log(LOG_LEVEL_INFO, CHILD_DEVICE_PIR, MSG_SUBTYPE_TRIPPED, str(pir_pin), timestamp=False)

        self.controller = ThermostatController(
            app=self.app_state,
            ui=ui,
            gpio=GPIO,
            log=self.log,
            mqtt=self.mqtt,
            state_store=self.state_store,
            lock=self.thermostat_lock,
            heat_pin=heat_pin,
            cool_pin=cool_pin,
            fan_pin=fan_pin,
            temp_hysteresis=temp_hysteresis,
            units=self.units,
            sensor=temp_sensor,
            sensor_unit=sensor_unit,
            calibration={
                "freezing_measured": self.cfg.get("calibration", "freezingMeasured"),
                "reference_range": self._reference_range(),
                "measured_range": self._measured_range(),
                "freezing_point": 0.01 if temp_scale == "metric" else 32.018,
            },
            tolerance=tolerance,
            min_flow_temp=min_flow_temp,
            current_flow_temp=current_flow_temp,
            use_test_schedule=self.use_test_schedule,
            hotwater=self.hotwater_control,
            publish_faikin=self._publish_faikin,
            reload_schedule=self._reload_schedule,
        )

        self.handlers = Handlers(
            app=self.app_state,
            ui=ui,
            gpio=GPIO,
            log=self.log,
            lock=self.thermostat_lock,
            hotwater=self.hotwater_control,
            units=self.units,
            domestic_key=domestic_key_value_pair,
            domestic_timeout=domestic_timeout_duration,
            pir_pin=pir_pin,
            pir_ignore_from=pir_ignore_from,
            pir_ignore_to=pir_ignore_to,
            min_ui_timeout=self.min_ui_timeout,
        )

        ui.create(
            app=self.app_state,
            status_provider=self.controller.get_status_info,
            min_temp=self.min_temp,
            max_temp=self.max_temp,
            temp_step=self.temp_step,
            units=self.units,
            version=self.version,
            log_binary=self._ui_log_binary,
            lock=self.thermostat_lock,
        )

        weather_location = self.cfg.get("weather", "location")
        weather_appkey = self.cfg.get("weather", "appkey")
        current_url, forecast_url = build_urls(temp_scale, weather_location, weather_appkey)

        self.weather_view = WeatherView(
            ui=ui,
            log=self.log,
            lock=self.weather_lock,
            current_url=current_url,
            forecast_url=forecast_url,
            timeout=self.cfg.get("weather", "URLtimeout"),
            current_interval=self.cfg.get("weather", "weatherRefreshInterval") * 60,
            forecast_interval=self.cfg.get("weather", "forecastRefreshInterval") * 60,
            exception_interval=self.cfg.get("weather", "weatherExceptionInterval") * 60,
            units=self.units,
            wind_factor=wind_factor,
            wind_units=wind_units,
            precip_factor=precip_factor,
            precip_round=precip_round,
            precip_units=precip_units,
            units_system=temp_scale,
        )

        self.commands = Commands(
            log=self.log,
            logger=self.logger,
            mqtt=self.mqtt,
            gpio=GPIO,
            version=self.version,
            script=self.script,
        )

        if self.mqtt.enabled:
            self.faikin = FaikinController(
                name=self.faikin_name,
                enabled=self.faikin_enabled,
                summer_temp=self.cfg.get("faikin", "summer_temp"),
                publish=self.mqtt.publish,
                get_snapshot=self._get_faikin_snapshot,
                state_topic=self.mqtt.state_topic("status"),
                heartbeat=FAIKIN_CONTROL_HEARTBEAT,
                log_debug=self._faikin_log_debug,
                log_error=self._faikin_log_error,
            )

            self.mqtt.add_handler(self.mqtt.command_topic("restart"), lambda message: self.commands.restart(message))
            self.mqtt.add_handler(self.mqtt.command_topic("loglevel"), lambda message: self.commands.set_log_level(message))
            self.mqtt.add_handler(self.mqtt.command_topic("version"), lambda message: self.commands.get_version(message))
            self.mqtt.add_handler(self.mqtt.command_topic("state"), lambda message: self.controller.get_status_info())
            if self.domestic_water_enabled:
                self.mqtt.add_handler(self.domestic_water_topic, lambda message: self.handlers.set_domestic_water(message))
            if self.faikin_enabled:
                self.mqtt.add_handler("state/" + self.faikin_name + "/status",
                                      lambda message: self.faikin.handle_status_message(message))

            self.mqtt.start()

        self.scheduler = Scheduler(
            app=self.app_state,
            apply_set_temp=self.controller.apply_set_temp,
            temp_scale=temp_scale,
            units=self.units,
            use_test_schedule=self.use_test_schedule,
            schedule_lock=self.schedule_lock,
            thermostat_lock=self.thermostat_lock,
            log=_SchedulerLog(self.log),
        )

    # -- glue --------------------------------------------------------------
    def _mqtt_log(self, level, msg):
        lvl = {"state": LOG_LEVEL_STATE, "error": LOG_LEVEL_ERROR}.get(level, LOG_LEVEL_INFO)
        self.log(lvl, CHILD_DEVICE_MQTT, MSG_SUBTYPE_TEXT, msg)

    def _publish_faikin(self):
        if self.mqtt.enabled:
            self.faikin.publish_control()

    def _reload_schedule(self):
        self.scheduler.reload()

    def _ui_log_binary(self, control_label, value):
        self.log(LOG_LEVEL_STATE, control_label + CHILD_DEVICE_SUFFIX_UICONTROL, MSG_SUBTYPE_BINARY_STATUS, value)

    def _get_faikin_snapshot(self):
        return self.app_state.snapshot()

    def _faikin_log_debug(self, msg):
        self.log(LOG_LEVEL_DEBUG, CHILD_DEVICE_FAIKIN, MSG_SUBTYPE_FAIKIN + "/" + self.faikin_name, msg)

    def _faikin_log_error(self, msg):
        self.log(LOG_LEVEL_ERROR, CHILD_DEVICE_FAIKIN, MSG_SUBTYPE_FAIKIN + "/" + self.faikin_name, msg)

    def _web_log_info(self, subtype, msg):
        self.log(LOG_LEVEL_INFO, CHILD_DEVICE_WEBSERVER, subtype, msg)

    def _web_log_state(self, subtype, msg):
        self.log(LOG_LEVEL_STATE, CHILD_DEVICE_WEBSERVER, subtype, msg)

    # -- calibration helpers ----------------------------------------------
    def _reference_range(self):
        elevation = self.cfg.get("calibration", "elevation")
        if self.cfg.get("scale", "tempScale") == "metric":
            return (100.0 - 0.003353 * elevation) - 0.01
        return (212.0 - 0.00184 * elevation) - 32.018

    def _measured_range(self):
        return self.cfg.get("calibration", "boilingMeasured") - self.cfg.get("calibration", "freezingMeasured")

    def _log_presentations(self):
        self.log(LOG_LEVEL_STATE, CHILD_DEVICE_NODE, MSG_SUBTYPE_NAME, "Thermostat Starting Up...", msg_type=MSG_TYPE_PRESENTATION)
        self.log(LOG_LEVEL_STATE, CHILD_DEVICE_NODE, MSG_SUBTYPE_VERSION, self.version, msg_type=MSG_TYPE_PRESENTATION)
        for child in CHILD_DEVICES:
            if child != CHILD_DEVICE_NODE:
                self.log(LOG_LEVEL_STATE, child, child, "", msg_type=MSG_TYPE_PRESENTATION)

    def _log_temperature_settings(self, temp_scale, precip_units, precip_factor,
                                  sensor_unit, wind_factor, wind_units, temp_hysteresis):
        n = CHILD_DEVICE_NODE
        s = MSG_SUBTYPE_CUSTOM + "/settings/temperature/"
        log = self.log
        log(LOG_LEVEL_INFO, n, s + "tempScale", str(temp_scale), timestamp=False)
        log(LOG_LEVEL_INFO, n, s + "scaleUnits", str(self.units), timestamp=False)
        log(LOG_LEVEL_INFO, n, s + "precipUnits", str(precip_units), timestamp=False)
        log(LOG_LEVEL_INFO, n, s + "precipFactor", str(precip_factor), timestamp=False)
        log(LOG_LEVEL_INFO, n, s + "sensorUnits", str(sensor_unit), timestamp=False)
        log(LOG_LEVEL_INFO, n, s + "windFactor", str(wind_factor), timestamp=False)
        log(LOG_LEVEL_INFO, n, s + "windUnits", str(wind_units), timestamp=False)
        log(LOG_LEVEL_INFO, n, s + "currentTemp", str(self.app_state.current_temp), timestamp=False)
        log(LOG_LEVEL_INFO, n, s + "setTemp", str(self.app_state.set_temp), timestamp=False)
        log(LOG_LEVEL_INFO, n, s + "tempHysteresis", str(temp_hysteresis), timestamp=False)
        log(LOG_LEVEL_INFO, n, s + "tempCheckInterval", str(self.temp_check_interval), timestamp=False)
        log(LOG_LEVEL_INFO, n, s + "minUIEnabled", str(self.min_ui_enabled), timestamp=False)
        log(LOG_LEVEL_INFO, n, s + "minUITimeout", str(self.min_ui_timeout), timestamp=False)

    def _log_calibration_settings(self):
        n = CHILD_DEVICE_NODE
        s = MSG_SUBTYPE_CUSTOM + "/settings/calibration/"
        log = self.log
        elevation = self.cfg.get("calibration", "elevation")
        boiling_point = (100.0 - 0.003353 * elevation) if self.cfg.get("scale", "tempScale") == "metric" else (212.0 - 0.00184 * elevation)
        freezing_point = 0.01 if self.cfg.get("scale", "tempScale") == "metric" else 32.018
        reference_range = boiling_point - freezing_point
        boiling_measured = self.cfg.get("calibration", "boilingMeasured")
        freezing_measured = self.cfg.get("calibration", "freezingMeasured")
        measured_range = boiling_measured - freezing_measured
        log(LOG_LEVEL_INFO, n, s + "elevation", str(elevation), timestamp=False)
        log(LOG_LEVEL_INFO, n, s + "boilingPoint", str(boiling_point), timestamp=False)
        log(LOG_LEVEL_INFO, n, s + "freezingPoint", str(freezing_point), timestamp=False)
        log(LOG_LEVEL_DEBUG, n, s + "referenceRange", str(reference_range), timestamp=False)
        log(LOG_LEVEL_INFO, n, s + "boilingMeasured", str(boiling_measured), timestamp=False)
        log(LOG_LEVEL_INFO, n, s + "freezingMeasured", str(freezing_measured), timestamp=False)
        log(LOG_LEVEL_DEBUG, n, s + "measuredRange", str(measured_range), timestamp=False)

    # -- lifecycle ---------------------------------------------------------
    def start_web_server(self):
        host = self.cfg.get("web", "host")
        cherrypy.server.socket_host = host if host != "discover" else self.commands.get_ip_address()
        cherrypy.server.socket_port = self.cfg.get("web", "port")

        self.log(LOG_LEVEL_STATE, CHILD_DEVICE_WEBSERVER, MSG_SUBTYPE_TEXT,
                 "Starting on " + cherrypy.server.socket_host + ":" + str(cherrypy.server.socket_port))

        conf = {
            '/': {
                'tools.staticdir.root': os.path.abspath(os.getcwd()),
                'tools.staticfile.root': os.path.abspath(os.getcwd())
            },
            '/css': {
                'tools.staticdir.on': True,
                'tools.staticdir.dir': './web/css'
            },
            '/javascript': {
                'tools.staticdir.on': True,
                'tools.staticdir.dir': './web/javascript'
            },
            '/images': {
                'tools.staticdir.on': True,
                'tools.staticdir.dir': './web/images'
            },
            '/schedule.json': {
                'tools.staticfile.on': True,
                'tools.staticfile.filename': './thermostat_schedule.json'
            },
            '/favicon.ico': {
                'tools.staticfile.on': True,
                'tools.staticfile.filename': './web/images/favicon.ico'
            }
        }

        cherrypy.config.update(
            {'log.screen': self.debug,
             'log.access_file': "",
             'log.error_file': ""
             }
        )

        cherrypy.quickstart(WebInterface(
            app=self.app_state,
            status_provider=self.controller.get_status_info,
            set_setpoint=self.controller.apply_set_temp,
            set_controls=self.controller.apply_controls,
            reload_schedule=self.scheduler.reload,
            version=self.version,
            min_temp=self.min_temp,
            max_temp=self.max_temp,
            temp_step=self.temp_step,
            units=self.units,
            thermostat_lock=self.thermostat_lock,
            schedule_lock=self.schedule_lock,
            log_info=self._web_log_info,
            log_state=self._web_log_state,
        ), '/', conf)

    def run(self):
        web_thread = threading.Thread(target=self.start_web_server)
        web_thread.daemon = True
        web_thread.start()

        self.scheduler.reload()
        sched_thread = threading.Thread(target=self.scheduler.run_forever)
        sched_thread.daemon = True
        sched_thread.start()

        ThermostatApp(
            ui=ui,
            controller=self.controller,
            handlers=self.handlers,
            weather_view=self.weather_view,
            hotwater=self.hotwater_control,
            cfg=self.cfg,
            min_ui_enabled=self.min_ui_enabled,
            pir_enabled=self.pir_enabled,
            pir_check_interval=self.pir_check_interval,
            temp_check_interval=self.temp_check_interval,
        ).run()

    def shutdown(self):
        self.log(LOG_LEVEL_STATE, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/shutdown", "Thermostat Shutting Down...")
        try:
            GPIO.cleanup()
        except Exception:
            pass
        self.logger.close()
        self.mqtt.stop()
