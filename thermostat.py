# -*- coding: utf-8 -*-

# BEGIN LICENSE
# Copyright (c) 2015 Andrzej Taramina <andrzej@chaeron.com>

# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:

# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
# END LICENSE

##############################################################################
#                                                                            #
#       Core Imports                                                         #
#                                                                            #
##############################################################################

import datetime
import json
import os
import os.path
import gettext
# from gettext import gettext as _
import socket
import sys
import threading
import time
import traceback
import urllib.request
import uuid

from faikin import FaikinController
from config import Config
from weather import build_urls, get_weather, get_cardinal_direction, get_precip_amount
from app_state import AppState
from web import WebInterface
from scheduler import Scheduler
import ui

try:
    from hotwater_control import HotWaterControl
    hotwater_module_available = True
except ImportError:
    HotWaterControl = None
    hotwater_module_available = False

import kivy
from kivy.core.window import Window

##############################################################################
#                                                                            #
#       Kivy UI Imports                                                      #
#                                                                            #
##############################################################################

kivy.require('2.3.0')  # keep in sync with requirements.txt

from kivy.app import App
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.core.text import Label as CoreLabel
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.slider import Slider
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.storage.jsonstore import JsonStore
from kivy.uix.screenmanager import ScreenManager, Screen, NoTransition
from kivy.uix.popup import Popup
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout

##############################################################################
#                                                                            #
#       Other Imports                                                        #
#                                                                            #
##############################################################################

import cherrypy
import subprocess
import locale

##############################################################################
#                                                                            #
#       GPIO & Simulation Imports                                            #
#                                                                            #
##############################################################################

try:
    import RPi.GPIO as GPIO
except ImportError:
    import FakeRPi.GPIO as GPIO


##############################################################################
#                                                                            #
#       Sensor Imports                                                       #
#                                                                            #
##############################################################################

try:
    from w1thermsensor import W1ThermSensor, Unit
except (ImportError, OSError, RuntimeError, Exception) as e:
    print(f"Fehler beim Laden von w1thermsensor: {e}")
    from FakeRPi.w1thermsensor import W1ThermSensor, Unit

##############################################################################
#                                                                            #
#       MQTT Imports (used for logging and/or external sensors)              #
#                                                                            #
##############################################################################

try:
    import paho.mqtt.client as mqtt
    import paho.mqtt.publish as publish

    mqttAvailable = True
except ImportError:
    mqttAvailable = False


##############################################################################
#                                                                            #
#       MySensor.org Controller compatible translated constants              #
#                                                                            #
##############################################################################

MSG_TYPE_SET = "set"
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
    CHILD_DEVICE_NODE,
    CHILD_DEVICE_MQTT,
    CHILD_DEVICE_UICONTROL_HEAT,
    CHILD_DEVICE_UICONTROL_COOL,
    CHILD_DEVICE_UICONTROL_FAN,
    CHILD_DEVICE_UICONTROL_HOLD,
    CHILD_DEVICE_UICONTROL_SLIDER,
    CHILD_DEVICE_WEATHER_CURR,
    CHILD_DEVICE_WEATHER_FCAST_TODAY,
    CHILD_DEVICE_WEATHER_FCAST_TOMO,
    CHILD_DEVICE_HEAT,
    CHILD_DEVICE_COOL,
    CHILD_DEVICE_FAN,
    CHILD_DEVICE_PIR,
    CHILD_DEVICE_TEMP,
    CHILD_DEVICE_SCREEN,
    CHILD_DEVICE_SCHEDULER,
    CHILD_DEVICE_WEBSERVER,
    CHILD_DEVICE_FAIKIN
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

##############################################################################
#                                                                            #
#       Settings                                                             #
#                                                                            #
##############################################################################

THERMOSTAT_VERSION = "2.3.1"


debug = False
useTestSchedule = False
FAIKIN_CONTROL_HEARTBEAT = 60  # seconds between repeated control commands

Window.show_cursor = False

thermostatLock = threading.RLock()
weatherLock = threading.Lock()
scheduleLock = threading.RLock()

cfg = Config()
state = JsonStore("thermostat_state.json")

# Internationalization (i18n)
t_locale = cfg.get("i18n", "locale")
locale.setlocale(locale.LC_ALL, t_locale)
gettext.install('thermostat', localedir='locales', names='gettext')

domestic_water_enabled = cfg.get("domestic_water", "enabled")
domestic_water_topic = cfg.get("domestic_water", "topic")
domestic_key_value_pair = cfg.get("domestic_water", "key_value_pair")
domestic_timeout_duration = 300 # 5 min
domestic_last_message_time = time.time()

# Hot water (immersion heater on Shelly smart plug) control via SEUSS price data
hotwater_settings = cfg.section("hotwater_control")
hotwater_control = HotWaterControl(hotwater_settings) if hotwater_module_available else None

faikinEnabled = cfg.get("faikin", "enabled")
faikinName = cfg.get("faikin", "name")

def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    # paho-mqtt v2 / CallbackAPIVersion.VERSION2 signature
    if reason_code != 0:
        print(f"Unexpected MQTT Broker disconnection! {reason_code}")
        log(LOG_LEVEL_INFO, CHILD_DEVICE_MQTT, MSG_SUBTYPE_TEXT,
            f"Unexpected MQTT Broker disconnection: {reason_code}")

def mqtt_on_connect(client, userdata, connect_flags, reason_code, properties):
    # paho-mqtt v2 / CallbackAPIVersion.VERSION2 signature
    global mqttReconnect

    print("MQTT Connected with result code: " + str(reason_code))

    if reason_code == 0:
        if mqttReconnect:
            log(LOG_LEVEL_STATE, CHILD_DEVICE_MQTT, MSG_SUBTYPE_TEXT,
                "Reconnected to: " + mqttServer + ":" + str(mqttPort))
        else:
            mqttReconnect = True
            log(LOG_LEVEL_STATE, CHILD_DEVICE_MQTT, MSG_SUBTYPE_TEXT,
                "Connected to: " + mqttServer + ":" + str(mqttPort))

        mqtt_subscriptions = [
            (mqttSub_restart, 0),
            (mqttSub_loglevel, 0),
            (mqttSub_version, 0)
        ]

        if domestic_water_enabled:
            mqtt_subscriptions.append((domestic_water_topic, 0))

        if faikinEnabled:
            mqtt_subscriptions.append((mqttSub_faikin, 0))

        mqtt_subscriptions.append((mqttSub_state, 0))
        src = client.subscribe(mqtt_subscriptions)

        if src[0] == 0:
            log(LOG_LEVEL_INFO, CHILD_DEVICE_MQTT, MSG_SUBTYPE_TEXT,
                "Subscribe Succeeded: " + mqttServer + ":" + str(mqttPort))
        else:
            log(LOG_LEVEL_ERROR, CHILD_DEVICE_MQTT, MSG_SUBTYPE_TEXT,
                "Subscribe FAILED, result code: " + str(src[0]))


if mqttAvailable:
    mqttReconnect = False
    mqttEnabled = cfg.get("mqtt", "enabled")
    mqttClientID = cfg.get("mqtt", "clientID")
    mqttServer = cfg.get("mqtt", "server")
    mqttPort = cfg.get("mqtt", "port")
    mqttPubPrefix = cfg.get("mqtt", "pubPrefix")

    mqttSub_version = str(mqttPubPrefix + "/" + mqttClientID + "/command/version")
    mqttSub_restart = str(mqttPubPrefix + "/" + mqttClientID + "/command/restart")
    mqttSub_loglevel = str(mqttPubPrefix + "/" + mqttClientID + "/command/loglevel")
    mqttSub_state = str(mqttPubPrefix + "/" + mqttClientID + "/command/state")
    # Faikout publishes its status on state/<name>/status
    # (not "Faikin/<name>"), otherwise outside_temp stays 0.0.
    mqttSub_faikin = str("state/" + faikinName + "/status")

    mqttPub_state = str(mqttPubPrefix + "/" + mqttClientID + "/state/status")
    mqttPub_fanstate = str(mqttPubPrefix + "/" + mqttClientID + "/state/fan")

else:
    mqttEnabled = False


LOG_FILE_NAME = "thermostat.log"

LOG_ALWAYS_TIMESTAMP = True

LOG_LEVEL_DEBUG = 1
LOG_LEVEL_INFO = 2
LOG_LEVEL_ERROR = 3
LOG_LEVEL_STATE = 4
LOG_LEVEL_NONE = 5

LOG_LEVELS = {
    "debug": LOG_LEVEL_DEBUG,
    "info": LOG_LEVEL_INFO,
    "state": LOG_LEVEL_STATE,
    "error": LOG_LEVEL_ERROR
}

LOG_LEVELS_STR = {v: k for k, v in LOG_LEVELS.items()}

logFile = None


def log_dummy(level, child_device, msg_subtype, msg, msg_type=MSG_TYPE_SET, timestamp=True, single=False):
    pass

def log_mqtt(level, child_device, msg_subtype, msg, msg_type=MSG_TYPE_SET, timestamp=True, single=False):
    if level >= logLevel:
        ts = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z ") if LOG_ALWAYS_TIMESTAMP or timestamp else ""
        topic = mqttPubPrefix + "/sensor/log/" + LOG_LEVELS_STR[
            level] + "/" + mqttClientID + "/" + child_device + "/" + msg_type + "/" + msg_subtype
        payload = ts + msg

        if single:
            publish.single(topic, payload, hostname=mqttServer, port=mqttPort, client_id=mqttClientID)
        else:
            mqttc.publish(topic, payload)

def log_file(level, child_device, msg_subtype, msg, msg_type=MSG_TYPE_SET, timestamp=True, single=False):
    if level >= logLevel:
        ts = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z ")
        logFile.write(
            ts + LOG_LEVELS_STR[level] + "/" + child_device + "/" + msg_type + "/" + msg_subtype + ": " + msg + "\n")

def log_print(level, child_device, msg_subtype, msg, msg_type=MSG_TYPE_SET, timestamp=True, single=False):
    if level >= logLevel:
        ts = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z ") if LOG_ALWAYS_TIMESTAMP or timestamp else ""
        print(ts + LOG_LEVELS_STR[level] + "/" + child_device + "/" + msg_type + "/" + msg_subtype + ": " + msg)


loggingChannel = cfg.get("logging", "channel")
loggingLevel = cfg.get("logging", "level")

if loggingChannel == 'none':
    log = log_dummy
elif loggingChannel == 'mqtt' and mqttEnabled:
    log = log_mqtt
elif loggingChannel == 'file':
    log = log_file
    logFile = open(LOG_FILE_NAME, "a")
elif loggingChannel == 'print':
    log = log_print
else:
    log = log_dummy

logLevel = LOG_LEVELS.get(loggingLevel, LOG_LEVEL_NONE)


log(LOG_LEVEL_STATE, CHILD_DEVICE_NODE, MSG_SUBTYPE_NAME, "Thermostat Starting Up...", msg_type=MSG_TYPE_PRESENTATION)
log(LOG_LEVEL_STATE, CHILD_DEVICE_NODE, MSG_SUBTYPE_VERSION, THERMOSTAT_VERSION, msg_type=MSG_TYPE_PRESENTATION)


for child in CHILD_DEVICES:
    if child != CHILD_DEVICE_NODE:
        log(LOG_LEVEL_STATE, child, child, "", msg_type=MSG_TYPE_PRESENTATION)

tempScale = cfg.get("scale", "tempScale")
scaleUnits = "c" if tempScale == "metric" else "f"
precipUnits = " mm" if tempScale == "metric" else '"'
precipFactor = 1.0 if tempScale == "metric" else 0.0393701
precipRound = 0 if tempScale == "metric" else 1
sensorUnits = Unit.DEGREES_C if tempScale == "metric" else Unit.DEGREES_F
windFactor = 3.6 if tempScale == "metric" else 1.0
windUnits = " km/h" if tempScale == "metric" else " mph"

TEMP_TOLERANCE = 0.1 if tempScale == "metric" else 0.18

minFlowTemp = 65.0
currentFlowTemp = 0.0

priorCorrected = -100.0
_saved = state.get("state") if state.exists("state") else {}
app = AppState(
    current_temp=22.0 if tempScale == "metric" else 72.0,
    set_temp=_saved.get("setTemp", 22.0),
    heat=_saved.get("heatControl") == "down",
    cool=_saved.get("coolControl") == "down",
    fan=_saved.get("fanControl") == "down",
    hold=_saved.get("holdControl") == "down",
)
_last_persisted_state = None  # cache to avoid needless writes (spares the SD card)

tempHysteresis = cfg.get("thermostat", "tempHysteresis")

tempCheckInterval = cfg.get("thermostat", "tempCheckInterval")

minUIEnabled = cfg.get("thermostat", "minUIEnabled")
minUITimeout = cfg.get("thermostat", "minUITimeout")
minUITimer = None
blackScreenTimer = None

log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/temperature/tempScale", str(tempScale),
    timestamp=False)
log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/temperature/scaleUnits", str(scaleUnits),
    timestamp=False)
log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/temperature/precipUnits", str(precipUnits),
    timestamp=False)
log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/temperature/precipFactor", str(precipFactor),
    timestamp=False)
log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/temperature/sensorUnits", str(sensorUnits),
    timestamp=False)
log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/temperature/windFactor", str(windFactor),
    timestamp=False)
log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/temperature/windUnits", str(windUnits),
    timestamp=False)
log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/temperature/currentTemp", str(app.current_temp),
    timestamp=False)
log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/temperature/app.set_temp", str(app.set_temp),
    timestamp=False)
log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/temperature/tempHysteresis", str(tempHysteresis),
    timestamp=False)
log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/temperature/tempCheckInterval",
    str(tempCheckInterval), timestamp=False)
log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/temperature/minUIEnabled", str(minUIEnabled),
    timestamp=False)
log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/temperature/minUITimeout", str(minUITimeout),
    timestamp=False)


elevation = cfg.get("calibration", "elevation")
boilingPoint = (100.0 - 0.003353 * elevation) if tempScale == "metric" else (212.0 - 0.00184 * elevation)
freezingPoint = 0.01 if tempScale == "metric" else 32.018
referenceRange = boilingPoint - freezingPoint

boilingMeasured = cfg.get("calibration", "boilingMeasured")
freezingMeasured = cfg.get("calibration", "freezingMeasured")
measuredRange = boilingMeasured - freezingMeasured

log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/calibration/elevation", str(elevation),
    timestamp=False)
log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/calibration/boilingPoint", str(boilingPoint),
    timestamp=False)
log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/calibration/freezingPoint", str(freezingPoint),
    timestamp=False)
log(LOG_LEVEL_DEBUG, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/calibration/referenceRange",
    str(referenceRange), timestamp=False)
log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/calibration/boilingMeasured",
    str(boilingMeasured), timestamp=False)
log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/calibration/freezingMeasured",
    str(freezingMeasured), timestamp=False)
log(LOG_LEVEL_DEBUG, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/calibration/measuredRange", str(measuredRange),
    timestamp=False)


minTemp = cfg.get("thermostat", "minTemp")
maxTemp = cfg.get("thermostat", "maxTemp")
tempStep = cfg.get("thermostat", "tempStep")

log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/UISlider/minTemp", str(minTemp), timestamp=False)
log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/UISlider/maxTemp", str(maxTemp), timestamp=False)
log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/UISlider/tempStep", str(tempStep),
    timestamp=False)

try:
    tempSensor = W1ThermSensor()
except Exception as e:
    log(LOG_LEVEL_ERROR, CHILD_DEVICE_TEMP, MSG_SUBTYPE_TEXT, f"Sensor init failed: {e}")
    tempSensor = None

pirEnabled = cfg.get("pir", "pirEnabled")
pirPin = cfg.get("pir", "pirPin")

pirCheckInterval = cfg.get("pir", "pirCheckInterval")

pirIgnoreFromStr = cfg.get("pir", "pirIgnoreFrom")
pirIgnoreToStr = cfg.get("pir", "pirIgnoreTo")

pirIgnoreFrom = datetime.time(int(pirIgnoreFromStr.split(":")[0]), int(pirIgnoreFromStr.split(":")[1]))
pirIgnoreTo = datetime.time(int(pirIgnoreToStr.split(":")[0]), int(pirIgnoreToStr.split(":")[1]))

log(LOG_LEVEL_INFO, CHILD_DEVICE_PIR, MSG_SUBTYPE_ARMED, str(pirEnabled), timestamp=False)
log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/pir/checkInterval", str(pirCheckInterval),
    timestamp=False)
log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/pir/ignoreFrom", str(pirIgnoreFromStr),
    timestamp=False)
log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/pir/ignoreTo", str(pirIgnoreToStr),
    timestamp=False)


coolPin = cfg.get("thermostat", "coolPin")
heatPin = cfg.get("thermostat", "heatPin")
fanPin = cfg.get("thermostat", "fanPin")

GPIO.setmode(GPIO.BCM)
GPIO.setup(coolPin, GPIO.OUT)
GPIO.output(coolPin, GPIO.HIGH)
GPIO.setup(heatPin, GPIO.OUT)
GPIO.output(heatPin, GPIO.HIGH)
GPIO.setup(fanPin, GPIO.OUT)
GPIO.output(fanPin, GPIO.HIGH)

if pirEnabled:
    GPIO.setup(pirPin, GPIO.IN)

log(LOG_LEVEL_INFO, CHILD_DEVICE_COOL, MSG_SUBTYPE_BINARY_STATUS, str(coolPin), timestamp=False)
log(LOG_LEVEL_INFO, CHILD_DEVICE_HEAT, MSG_SUBTYPE_BINARY_STATUS, str(heatPin), timestamp=False)
log(LOG_LEVEL_INFO, CHILD_DEVICE_FAN, MSG_SUBTYPE_BINARY_STATUS, str(fanPin), timestamp=False)
log(LOG_LEVEL_INFO, CHILD_DEVICE_PIR, MSG_SUBTYPE_TRIPPED, str(pirPin), timestamp=False)

##############################################################################
#                                                                            #
#       UI Controls/Widgets                                                  #
#                                                                            #
##############################################################################

def get_status_info():
    with thermostatLock:
        sched = "None"

        if app.hold:
            sched = _("Hold")
        elif useTestSchedule:
            sched = "Test"
        elif app.heat:
            sched = _("Heat")
        elif app.cool:
            sched = _("Cool")

        status_info = {
            'heat': f"[color=00ff00][b]" + _("On") + "[/b][/color]" if not GPIO.input(heatPin) else f"" + _("Off"),
            'cool': f"[color=00ff00][b]" + _("On") + "[/b][/color]" if not GPIO.input(coolPin) else f"" + _("Off"),
            'fan': f"[color=00ff00][b]" + _("On") + "[/b][/color]" if GPIO.input(fanPin) else f"" + _("Auto"),
            'sched': sched
        }

        status_info_json = json.dumps(status_info)

        return status_info_json

def _ui_log_binary(control_label, value):
    log(LOG_LEVEL_STATE, control_label + CHILD_DEVICE_SUFFIX_UICONTROL, MSG_SUBTYPE_BINARY_STATUS, value)


ui.create(
    app=app,
    status_provider=get_status_info,
    min_temp=minTemp,
    max_temp=maxTemp,
    temp_step=tempStep,
    units=scaleUnits,
    version=THERMOSTAT_VERSION,
    log_binary=_ui_log_binary,
    lock=thermostatLock,
)

# Price bar chart (sleep mode / minimalUI) - today only
priceBarsWidget = None
PRICE_BAR_HOURS = 24


screenMgr = None


##############################################################################
#                                                                            #
#       Faikin mqtt stuff                                                    #
#                                                                            #
##############################################################################

def _get_faikin_snapshot():
    """Current thermostat snapshot for the FaikinController."""
    return app.snapshot()


def _faikin_log_debug(msg):
    log(LOG_LEVEL_DEBUG, CHILD_DEVICE_FAIKIN,
        MSG_SUBTYPE_FAIKIN + "/" + faikinName, msg)


def _faikin_log_error(msg):
    log(LOG_LEVEL_ERROR, CHILD_DEVICE_FAIKIN,
        MSG_SUBTYPE_FAIKIN + "/" + faikinName, msg)

##############################################################################
#                                                                            #
#       Weather functions/constants/widgets                                  #
#                                                                            #
##############################################################################

weatherLocation = cfg.get("weather", "location")
weatherAppKey = cfg.get("weather", "appkey")
weatherURLCurrent, weatherURLForecast = build_urls(tempScale, weatherLocation, weatherAppKey)
weatherURLTimeout = cfg.get("weather", "URLtimeout")

weatherRefreshInterval = cfg.get("weather", "weatherRefreshInterval") * 60
forecastRefreshInterval = cfg.get("weather", "forecastRefreshInterval") * 60
weatherExceptionInterval = cfg.get("weather", "weatherExceptionInterval") * 60


def display_current_weather(dt):
    with weatherLock:
        interval = weatherRefreshInterval

        try:
            weather = get_weather(weatherURLCurrent, weatherURLTimeout)

            ui.weatherImg.source = "web/images/" + weather["weather"][0]["icon"] + ".png"

            ui.weatherSummaryLabel.text = "[b]" + weather["weather"][0]["description"].title() + "[/b]"

            ui.weatherTempValueLabel.text = str(int(round(weather["main"]["temp"], 0))) + scaleUnits
            ui.weatherHumidityValueLabel.text = str(weather["main"]["humidity"]) + "%"
            ui.weatherWindValueLabel.text = str(int(round(weather["wind"]["speed"] * windFactor))) + windUnits + " " + get_cardinal_direction(weather["wind"]["deg"])
            ui.weatherCloudsValueLabel.text = str(weather["clouds"]["all"]) + "%"
            ui.weatherSunValueLabel.text = time.strftime("%H:%M", time.localtime(weather["sys"]["sunrise"])) + ", " + time.strftime("%H:%M", time.localtime(weather["sys"]["sunset"])) + ""

            log(LOG_LEVEL_INFO, CHILD_DEVICE_WEATHER_CURR, MSG_SUBTYPE_TEXT, json.dumps(weather))

        except Exception as e:
            interval = weatherExceptionInterval

            ui.weatherImg.source = "web/images/na.png"
            ui.weatherSummaryLabel.text = "N/A"
            ui.weatherTempValueLabel.text = "N/A"
            ui.weatherHumidityValueLabel.text = "N/A"
            ui.weatherWindValueLabel.text = "N/A"
            ui.weatherCloudsValueLabel.text = "N/A"
            ui.weatherSunValueLabel.text = "N/A"

            log(LOG_LEVEL_ERROR, CHILD_DEVICE_WEATHER_CURR, MSG_SUBTYPE_TEXT, "Update FAILED!")
            log(LOG_LEVEL_ERROR, CHILD_DEVICE_WEATHER_CURR, MSG_SUBTYPE_TEXT, f"Exception {e}")

        Clock.schedule_once(display_current_weather, interval)


def display_forecast_weather(dt):
    with weatherLock:
        interval = forecastRefreshInterval

        try:
            forecast = get_weather(weatherURLForecast, weatherURLTimeout)

            today = forecast["list"][0]
            tomo = forecast["list"][1]

            ui.forecastTodayImg.source = "web/images/" + today["weather"][0]["icon"] + ".png"
            ui.forecastTodaySummaryLabel.text = "[b]" + today["weather"][0]["description"].title() + "[/b]"
            ui.forecastTodayHighValueLabel.text = str(int(round(today["temp"]["max"], 0))) + scaleUnits + ", " + _("Low") + ": " + str(int(round(today["temp"]["min"], 0))) + scaleUnits
            ui.forecastTodayHumidityValueLabel.text = str(today["humidity"]) + "%"
            ui.forecastTodayWindValueLabel.text = str(int(round(today["speed"] * windFactor))) + windUnits + " " + get_cardinal_direction(today["deg"])
            ui.forecastTodayCloudsValueLabel.text = str(today["clouds"]) + "%"

            rainValueText = ""
            if "rain" in today or "snow" in today:
                if "rain" in today:
                    ui.forecastTodayRainLabel.text = _("Rain") + ":"
                    rainValueText = get_precip_amount(today["rain"], precipFactor, precipRound, tempScale) + precipUnits
                    if "snow" in today:
                        rainValueText += ", " + _("Snow") + ": " + get_precip_amount(today["snow"], precipFactor, precipRound, tempScale) + precipUnits
                else:
                    ui.forecastTodayRainLabel.text = _("Snow") + ":"
                    rainValueText = get_precip_amount(today["snow"], precipFactor, precipRound, tempScale) + precipUnits

            ui.forecastTodayRainValueLabel.text = rainValueText

            ui.forecastTomoImg.source = "web/images/" + tomo["weather"][0]["icon"] + ".png"
            ui.forecastTomoSummaryLabel.text = "[b]" + tomo["weather"][0]["description"].title() + "[/b]"
            ui.forecastTomoHighValueLabel.text = str(int(round(tomo["temp"]["max"], 0))) + scaleUnits + ", " + _("Low") + ": " + str(int(round(tomo["temp"]["min"], 0))) + scaleUnits
            ui.forecastTomoHumidityValueLabel.text = str(tomo["humidity"]) + "%"
            ui.forecastTomoWindValueLabel.text = str(int(round(tomo["speed"] * windFactor))) + windUnits + " " + get_cardinal_direction(tomo["deg"])
            ui.forecastTomoCloudsValueLabel.text = str(tomo["clouds"]) + "%"

            rainValueText = ""
            if "rain" in tomo or "snow" in tomo:
                if "rain" in tomo:
                    ui.forecastTomoRainLabel.text = _("Rain") + ":"
                    rainValueText = get_precip_amount(tomo["rain"], precipFactor, precipRound, tempScale) + precipUnits
                    if "snow" in tomo:
                        rainValueText += ", " + _("Snow") + ": " + get_precip_amount(tomo["snow"], precipFactor, precipRound, tempScale) + precipUnits
                else:
                    ui.forecastTomoRainLabel.text = _("Snow") + ":"
                    rainValueText = get_precip_amount(tomo["snow"], precipFactor, precipRound, tempScale) + precipUnits

            ui.forecastTomoRainValueLabel.text = rainValueText

            log(LOG_LEVEL_INFO, CHILD_DEVICE_WEATHER_CURR, MSG_SUBTYPE_TEXT, json.dumps(today["weather"][0]))
            log(LOG_LEVEL_INFO, CHILD_DEVICE_WEATHER_CURR, MSG_SUBTYPE_TEXT, json.dumps(tomo["weather"][0]))

        except Exception as e:
            interval = weatherExceptionInterval

            ui.forecastTodayImg.source = "web/images/na.png"
            ui.forecastTodaySummaryLabel.text = ""
            ui.forecastTodayRainLabel.text = ""
            ui.forecastTodayRainValueLabel.text = ""
            ui.forecastTodayHighValueLabel.text = "N/A"
            ui.forecastTodayHumidityValueLabel.text = "N/A"
            ui.forecastTodayWindValueLabel.text = "N/A"
            ui.forecastTodayCloudsValueLabel.text = "N/A"
            ui.forecastTodayRainLabel.text = ""
            ui.forecastTodayRainValueLabel.text = ""

            ui.forecastTomoImg.source = "web/images/na.png"
            ui.forecastTomoSummaryLabel.text = ""
            ui.forecastTomoHighValueLabel.text = "N/A"
            ui.forecastTomoHumidityValueLabel.text = "N/A"
            ui.forecastTomoWindValueLabel.text = "N/A"
            ui.forecastTomoCloudsValueLabel.text = "N/A"
            ui.forecastTomoRainLabel.text = ""
            ui.forecastTomoRainValueLabel.text = ""
            log(LOG_LEVEL_ERROR, CHILD_DEVICE_WEATHER_FCAST_TODAY, MSG_SUBTYPE_TEXT, "Update FAILED!")
            log(LOG_LEVEL_ERROR, CHILD_DEVICE_WEATHER_FCAST_TODAY, MSG_SUBTYPE_TEXT, f"Exception {e}")

        Clock.schedule_once(display_forecast_weather, interval)

##############################################################################
#                                                                            #
#       Thermostat Implementation                                            #
#                                                                            #
##############################################################################


def change_system_settings():
    with thermostatLock:
        global currentFlowTemp, minFlowTemp

        hpin_start = str(GPIO.input(heatPin))
        cpin_start = str(GPIO.input(coolPin))
        fpin_start = str(GPIO.input(fanPin))

        if app.heat:
            GPIO.output(coolPin, GPIO.HIGH)

            if app.set_temp >= app.current_temp + tempHysteresis:
                GPIO.output(heatPin, GPIO.LOW)
                GPIO.output(fanPin, GPIO.LOW)
            elif app.set_temp <= app.current_temp:
                GPIO.output(heatPin, GPIO.HIGH)
                if not app.fan and GPIO.input(coolPin):
                    GPIO.output(fanPin, GPIO.HIGH)
        else:
            GPIO.output(heatPin, GPIO.HIGH)

            if app.cool:
                if app.set_temp <= app.current_temp - tempHysteresis:
                    GPIO.output(coolPin, GPIO.LOW)
                    GPIO.output(fanPin, GPIO.LOW)
                elif app.set_temp >= app.current_temp:
                    GPIO.output(coolPin, GPIO.HIGH)
                    if not app.fan and GPIO.input(heatPin):
                        GPIO.output(fanPin, GPIO.LOW)
            else:
                GPIO.output(coolPin, GPIO.HIGH)
                if not app.fan and GPIO.input(heatPin):
                    GPIO.output(fanPin, GPIO.HIGH)

        log(LOG_LEVEL_STATE, CHILD_DEVICE_TEMP, MSG_SUBTYPE_TEMPERATURE, "minFlow: " + str(minFlowTemp))
        log(LOG_LEVEL_STATE, CHILD_DEVICE_TEMP, MSG_SUBTYPE_TEMPERATURE, "currentFlow: " + str(currentFlowTemp))

        if app.fan:
            GPIO.output(fanPin, GPIO.HIGH)
            setMqttFanCommand("on")
            log(LOG_LEVEL_STATE, CHILD_DEVICE_FAN, MSG_SUBTYPE_TEXT, "fan forced on")
        else:
            setMqttFanCommand("off")
            if GPIO.input(heatPin) and GPIO.input(coolPin):
                GPIO.output(fanPin, GPIO.LOW)
                log(LOG_LEVEL_STATE, CHILD_DEVICE_FAN, MSG_SUBTYPE_TEXT, "fan off (idle)")

        # persist state across restarts, only when changed (spares the SD card)
        global _last_persisted_state
        current_state = (app.set_temp, app.heat, app.cool, app.fan, app.hold)
        if current_state != _last_persisted_state:
            state.put("state", setTemp=app.set_temp,
                      heatControl="down" if app.heat else "normal",
                      coolControl="down" if app.cool else "normal",
                      fanControl="down" if app.fan else "normal",
                      holdControl="down" if app.hold else "normal")
            _last_persisted_state = current_state

        status_info = json.loads(get_status_info())
        ui.statusHeatValueLabel.text = status_info['heat']
        ui.statusCoolValueLabel.text = status_info['cool']
        ui.statusFanValueLabel.text = status_info['fan']
        ui.statusSchedValueLabel.text = status_info['sched']

        if hpin_start != str(GPIO.input(heatPin)):
            log(LOG_LEVEL_STATE, CHILD_DEVICE_HEAT, MSG_SUBTYPE_BINARY_STATUS, "1" if GPIO.input(heatPin) else "0")
        if cpin_start != str(GPIO.input(coolPin)):
            log(LOG_LEVEL_STATE, CHILD_DEVICE_COOL, MSG_SUBTYPE_BINARY_STATUS, "1" if GPIO.input(coolPin) else "0")
        if fpin_start != str(GPIO.input(fanPin)):
            log(LOG_LEVEL_STATE, CHILD_DEVICE_FAN, MSG_SUBTYPE_BINARY_STATUS, "1" if GPIO.input(fanPin) else "0")

        if mqttEnabled:
            faikin.publish_control()


def control_callback(control):
    with thermostatLock:
        ui.setControlState(control, control.state)

        if control is ui.coolControl:
            if control.state == "down":
                ui.setControlState(ui.heatControl, "normal")
                app.heat = False
            app.cool = control.state == "down"
            scheduler.reload()

        if control is ui.heatControl:
            if control.state == "down":
                ui.setControlState(ui.coolControl, "normal")
                app.cool = False
            app.heat = control.state == "down"
            scheduler.reload()

        if control is ui.fanControl:
            app.fan = control.state == "down"

        if control is ui.holdControl:
            app.hold = control.state == "down"



def check_sensor_temp(dt):
    with thermostatLock:
        global priorCorrected
        global tempSensor

        if tempSensor is not None:
            try:
                rawTemp = tempSensor.get_temperature(sensorUnits)
                correctedTemp = (((rawTemp - freezingMeasured) * referenceRange) / measuredRange) + freezingPoint
                app.current_temp = round(correctedTemp, 1)
                log(LOG_LEVEL_DEBUG, CHILD_DEVICE_TEMP, MSG_SUBTYPE_CUSTOM + "/raw", str(rawTemp))
                log(LOG_LEVEL_DEBUG, CHILD_DEVICE_TEMP, MSG_SUBTYPE_CUSTOM + "/corrected", str(correctedTemp))

                if abs(priorCorrected - correctedTemp) >= TEMP_TOLERANCE:
                    log(LOG_LEVEL_STATE, CHILD_DEVICE_TEMP, MSG_SUBTYPE_TEMPERATURE, str(app.current_temp))
                    priorCorrected = correctedTemp
            except Exception as e:
                log(LOG_LEVEL_ERROR, CHILD_DEVICE_TEMP, MSG_SUBTYPE_TEXT, f"Sensor read failed: {e}")

        ui.currentLabel.text = "[b]" + str(app.current_temp) + scaleUnits + "[/b]"
        ui.altCurLabel.text = ui.currentLabel.text

        ui.dateLabel.text = "[b]" + time.strftime("%a %d. %b %Y") + "[/b]"

        timeStr = time.strftime("%H:%M")

        ui.timeLabel.text = ("[b]" + (timeStr if timeStr[0:1] != "0" else timeStr[1:]) + "[/b]").lower()
        ui.altTimeLabel.text = ui.timeLabel.text

        change_system_settings()

        if hotwater_control is not None and hotwater_control.enabled:
            try:
                hotwater_control.update_water_temp(app.domestic_water)
            except Exception as e:
                log(LOG_LEVEL_ERROR, CHILD_DEVICE_MQTT, MSG_SUBTYPE_TEXT,
                    f"hotwater control error: {e}")

def update_set_temp(slider, value):
    with thermostatLock:
        priorTemp = app.set_temp
        app.set_temp = round(slider.value, 1)
        ui.setLabel.text = "  Set\n[b]" + str(app.set_temp) + scaleUnits + "[/b]"
        if priorTemp != app.set_temp:
            log(LOG_LEVEL_STATE, CHILD_DEVICE_UICONTROL_SLIDER, MSG_SUBTYPE_TEMPERATURE, str(app.set_temp))


def check_pir(pin):
    global minUITimer

    with thermostatLock:
        if GPIO.input(pirPin):
            log(LOG_LEVEL_INFO, CHILD_DEVICE_PIR, MSG_SUBTYPE_TRIPPED, "1")

            if minUITimer is not None:
                Clock.unschedule(show_minimal_ui)

            minUITimer = Clock.schedule_once(show_minimal_ui, minUITimeout)

            ignore = False
            now = datetime.datetime.now().time()

            if pirIgnoreFrom > pirIgnoreTo:
                if now >= pirIgnoreFrom or now < pirIgnoreTo:
                    ignore = True
            else:
                if pirIgnoreFrom <= now < pirIgnoreTo:
                    ignore = True

            if screenMgr.current == "minimalUI" and not (ignore):
                screenMgr.current = "thermostatUI"
                log(LOG_LEVEL_DEBUG, CHILD_DEVICE_SCREEN, MSG_SUBTYPE_TEXT, "Full")

        else:
            log(LOG_LEVEL_DEBUG, CHILD_DEVICE_PIR, MSG_SUBTYPE_TRIPPED, "0")



def show_minimal_ui(dt):
    with thermostatLock:
        screenMgr.current = "minimalUI"
        log(LOG_LEVEL_DEBUG, CHILD_DEVICE_SCREEN, MSG_SUBTYPE_TEXT, "Minimal")

class MinimalScreen(Screen):
    def _long_press_triggered(self, dt):
        """Fires after 2s of holding the sleep screen without release."""
        self._lp_done = True
        with thermostatLock:
            if hotwater_control is not None and hotwater_control.enabled:
                try:
                    hotwater_control.force_on()
                except Exception:
                    pass
        log(LOG_LEVEL_DEBUG, CHILD_DEVICE_SCREEN, MSG_SUBTYPE_TEXT,
            "Long press: hotwater override")

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            touch.grab(self)
            self._down_time = time.time()
            self._lp_done = False
            self._lp_event = Clock.schedule_once(self._long_press_triggered, 2.0)
            return True

    def on_touch_up(self, touch):
        global minUITimer

        if touch.grab_current is self:
            touch.ungrab(self)
            if getattr(self, "_lp_event", None) is not None:
                self._lp_event.cancel()
                self._lp_event = None
            with thermostatLock:
                if minUITimer is not None:
                    Clock.unschedule(show_minimal_ui)
                minUITimer = Clock.schedule_once(show_minimal_ui, minUITimeout)
                if self._lp_done:
                    # Long press already handled the override -> stay asleep
                    pass
                else:
                    self.manager.current = "thermostatUI"
                    log(LOG_LEVEL_DEBUG, CHILD_DEVICE_SCREEN, MSG_SUBTYPE_TEXT, "Full")
            return True


##############################################################################
#                                                                            #
#       Utility Functions                                                    #
#                                                                            #
##############################################################################

def get_ip_address():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(10)
    try:
        s.connect(("8.8.8.8", 80))  # Google DNS server
        ip = s.getsockname()[0]
        log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/ip", ip, timestamp=False)
    except socket.error:
        ip = "127.0.0.1"
        log(LOG_LEVEL_ERROR, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/ip",
            "FAILED to get ip address, returning " + ip, timestamp=False)

    return ip


def getVersion(message):
    payload = message.payload.decode('utf-8')

    log(LOG_LEVEL_STATE, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/getVersion",
        f"Empfangene Nachricht: {payload}", single=True)
    log(LOG_LEVEL_STATE, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/getVersion",
        f"Empfangszeitpunkt: {message.timestamp}", single=True)
    print(f"Empfangene Nachricht: {payload}")
    print(f"Empfangszeitpunkt: {message.timestamp}")
    log(LOG_LEVEL_STATE, CHILD_DEVICE_NODE, MSG_SUBTYPE_VERSION, THERMOSTAT_VERSION)

def restart(message):
    payload = message.payload.decode('utf-8') if isinstance(message.payload, bytes) else str(message.payload)

    log(LOG_LEVEL_STATE, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/restart",
        f"Thermostat restarting... ({payload})", single=True)

    try:
        GPIO.cleanup()
    except Exception:
        pass

    if logFile is not None:
        try:
            logFile.flush()
            os.fsync(logFile.fileno())
            logFile.close()
        except Exception:
            pass

    if mqttEnabled:
        try:
            mqttc.disconnect()
        except Exception:
            pass

    os.execl(sys.executable, 'python', __file__, *sys.argv[1:])  # does not return

def setLogLevel(msg):
    global logLevel

    payload = msg.payload
    if isinstance(payload, bytes):
        payload = payload.decode('utf-8')
    payload = payload.strip().lower()

    if payload in LOG_LEVELS:
        logLevel = LOG_LEVELS[payload]
        log(LOG_LEVEL_STATE, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/loglevel",
            "LogLevel set to: " + payload)
    else:
        log(LOG_LEVEL_ERROR, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/loglevel",
            "Invalid LogLevel: " + payload)

def set_domestic_water(message):
    global domestic_key_value_pair
    global domestic_last_message_time
    try:
        payload = message.payload
        if isinstance(payload, bytes):
            payload = payload.decode('utf-8')

        data = json.loads(payload)
        domestic_water_value = data.get(domestic_key_value_pair)
        if domestic_water_value is not None and app.domestic_water != domestic_water_value:
            app.domestic_water = domestic_water_value
            ui.currentWaterValueLabel.text = "[b]" + str(app.domestic_water) + scaleUnits + "[/b]"
            ui.altWaterValueLabel.text = "[b]" + str(app.domestic_water) + scaleUnits + "[/b]"
            ui.altWaterValueLabel.color = (0.6, 0.6, 0.6, 0.55)

        domestic_last_message_time = time.time()
        Clock.schedule_once(check_domestic_water_timeout, domestic_timeout_duration)

    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        log(LOG_LEVEL_ERROR, CHILD_DEVICE_MQTT, MSG_SUBTYPE_TEXT,
            f"Invalid domestic_water payload: {e}")
    except Exception as e:
        log(LOG_LEVEL_ERROR, CHILD_DEVICE_MQTT, MSG_SUBTYPE_TEXT,
            f"set_domestic_water error: {e}")

def check_domestic_water_timeout(dt):
    global domestic_last_message_time

    current_time = time.time()
    if current_time - domestic_last_message_time > domestic_timeout_duration:
        app.domestic_water = "n/a"
        ui.currentWaterValueLabel.text = "[b]" + str(app.domestic_water) + "[/b]"
        ui.altWaterValueLabel.text = "[b]" + str(app.domestic_water) + "[/b]"
        ui.altWaterValueLabel.color = (0.6, 0.6, 0.6, 0.55)

def update_hotwater_ui(status):
    """Update the sleep-mode labels from the HotWaterControl status.
    Runs on the Kivy UI thread via Clock.schedule_once because the
    status can arrive from the HotWaterControl polling thread."""
    def _apply(dt):
        w = priceBarsWidget
        if w is not None:
            try:
                w.update_bars(status)
            except Exception:
                pass
        # battery line: SOC + charging/discharging/idle from
        # SEUSS /api/battery (display only).
        try:
            soc = status.get("battery_soc_percent")
            state = status.get("battery_state")
            if soc is None or state is None:
                ui.altBatteryValueLabel.text = "--"
                ui.altBatteryValueLabel.color = (0.45, 0.45, 0.45, 0.55)
            else:
                state_text = {"charging": "Ladung",
                              "discharging": "Entladung"}.get(state, state)
                ui.altBatteryValueLabel.text = \
                    f"[b]{soc:.0f} %[/b] [size=20]({state_text})[/size]"
                if state == "charging":
                    ui.altBatteryValueLabel.color = (0.0, 0.55, 0.0, 0.85)
                elif state == "discharging":
                    ui.altBatteryValueLabel.color = (0.85, 0.3, 0.1, 0.85)
                else:
                    ui.altBatteryValueLabel.color = (0.6, 0.6, 0.6, 0.8)
        except Exception:
            pass

    Clock.schedule_once(_apply, 0)

def setMqttFanCommand(state):
    if mqttEnabled:
        mqttc.publish(mqttPub_fanstate, state)

if mqttEnabled:
    # paho-mqtt v2 requires CallbackAPIVersion; v1 does not know the argument
    try:
        mqttc = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                            client_id=mqttClientID, protocol=mqtt.MQTTv5)
    except (AttributeError, TypeError):
        mqttc = mqtt.Client(client_id=mqttClientID, protocol=mqtt.MQTTv5)
    mqttc.on_connect = mqtt_on_connect
    mqttc.on_disconnect = on_disconnect

    mqttc.message_callback_add(mqttSub_restart, lambda client, userdata, message: restart(message) )
    mqttc.message_callback_add(mqttSub_loglevel, lambda client, userdata, message: setLogLevel(message))
    mqttc.message_callback_add(mqttSub_version, lambda client, userdata, message: getVersion(message))
    mqttc.message_callback_add(mqttSub_state, lambda client, userdata, message: get_status_info())
    if domestic_water_enabled:
        mqttc.message_callback_add(domestic_water_topic, lambda client, userdata, message: set_domestic_water(message))

    faikin = FaikinController(
        name=faikinName,
        enabled=faikinEnabled,
        summer_temp=cfg.get("faikin", "summer_temp"),
        publish=mqttc.publish,
        get_snapshot=_get_faikin_snapshot,
        state_topic=mqttPub_state,
        heartbeat=FAIKIN_CONTROL_HEARTBEAT,
        log_debug=_faikin_log_debug,
        log_error=_faikin_log_error,
    )

    if faikinEnabled:
        mqttc.message_callback_add(
            mqttSub_faikin,
            lambda client, userdata, message: faikin.handle_status_message(message))

    # Make sure we can reach the mqtt server by pinging it (max 30s wait)
    pingCount = 0
    pingCmd = "ping -c 1 -W 1 " + mqttServer + " > /dev/null 2>&1"

    while os.system(pingCmd) != 0 and pingCount < 30:
        pingCount += 1
        time.sleep(1)

    try:
        mqttc.connect(mqttServer, mqttPort, keepalive=60)
        mqttc.loop_start()
    except Exception as e:
        log(LOG_LEVEL_ERROR, CHILD_DEVICE_MQTT, MSG_SUBTYPE_TEXT,
            f"Initial MQTT connect failed: {e}")


##############################################################################
#                                                                            #
#       Kivy Thermostat App class                                            #
#                                                                            #
##############################################################################

class ThermostatApp(App):
    def build(self):
        global screenMgr

        thermostatUI = FloatLayout(size=(800, 480))

        with thermostatUI.canvas.before:
            Color(0.0, 0.0, 0.0, 1)
            self.rect = Rectangle(size=(800, 480), pos=thermostatUI.pos)


        wimg = Image(source='web/images/logo.png')

        def show_reboot_dialog(instance, touch):
            if not instance.collide_point(*touch.pos):
                return
            content = BoxLayout(orientation='vertical', padding=10, spacing=10)
            content.add_widget(Label(text="[b]Thermostat jetzt neu starten?[/b]",
                                     font_size='22sp', markup=True))
            btns = BoxLayout(orientation='horizontal',
                             size_hint=(1, None), height=60, spacing=10)
            btn_ok = Button(text="Reboot", size_hint=(1, 1))
            btn_cancel = Button(text="Abbrechen", size_hint=(1, 1))
            btns.add_widget(btn_ok)
            btns.add_widget(btn_cancel)
            content.add_widget(btns)
            popup = Popup(title="Thermostat", content=content,
                          size_hint=(0.6, 0.4), auto_dismiss=True)

            def do_reboot(btn):
                popup.dismiss()
                subprocess.Popen(["/sbin/reboot"])

            btn_ok.bind(on_press=do_reboot)
            btn_cancel.bind(on_press=lambda b: popup.dismiss())
            popup.open()

        wimg.bind(on_touch_down=show_reboot_dialog)

        ui.coolControl.bind(on_press=control_callback)
        ui.heatControl.bind(on_press=control_callback)
        ui.fanControl.bind(on_press=control_callback)
        ui.holdControl.bind(on_press=control_callback)

        ui.tempSlider.bind(on_touch_down=update_set_temp, on_touch_move=update_set_temp)


        wimg.size = (80, 80)
        wimg.size_hint = (None, None)
        wimg.pos = (10, 380)

        ui.heatControl.size = (80, 80)
        ui.heatControl.pos = (680, 380)

        ui.coolControl.size = (80, 80)
        ui.coolControl.pos = (680, 270)

        ui.fanControl.size = (80, 80)
        ui.fanControl.pos = (680, 160)

        ui.statusHeatLabel.pos = (635, 80)
        ui.statusCoolLabel.pos = (635, 60)
        ui.statusFanLabel.pos = (635, 40)
        ui.statusSchedLabel.pos = (635, 20)
        ui.statusHeatValueLabel.pos = (710, 80)
        ui.statusCoolValueLabel.pos = (710, 60)
        ui.statusFanValueLabel.pos = (710, 40)
        ui.statusSchedValueLabel.pos = (710, 20)

        ui.tempSlider.size = (100, 360)
        ui.tempSlider.pos = (570, 20)

        ui.holdControl.size = (80, 80)
        ui.holdControl.pos = (480, 380)

        ui.setLabel.pos = (590, 390)

        ui.currentLabel.pos = (390, 300)
        ui.currentWaterLabel.pos = (340, 235)
        ui.currentWaterValueLabel.pos = (450, 235)

        ui.dateLabel.pos = (180, 370)
        ui.timeLabel.pos = (345, 380)

        ui.weatherImg.pos = (265, 160)
        ui.weatherSummaryLabel.pos = (430, 160)
        ui.weatherTempLabel.pos = (365, 135)
        ui.weatherTempValueLabel.pos = (450, 135)
        ui.weatherHumidityLabel.pos = (365, 110)
        ui.weatherHumidityValueLabel.pos = (450, 110)
        ui.weatherWindLabel.pos = (365, 85)
        ui.weatherWindValueLabel.pos = (450, 85)
        ui.weatherCloudsLabel.pos = (365, 60)
        ui.weatherCloudsValueLabel.pos = (450, 60)
        ui.weatherSunLabel.pos = (365, 35)
        ui.weatherSunValueLabel.pos = (450, 35)

        ui.versionLabel.pos = (320, 0)

        forecastTodayHeading = Label(text="[b]"+ _("Today") + "[/b]:", font_size='20sp', markup=True, size_hint=(None, None),
                                     pos=(0, 300))

        ui.forecastTodayImg.pos = (0, 275)
        ui.forecastTodaySummaryLabel.pos = (100, 275)
        ui.forecastTodayHighLabel.pos = (30, 248)
        ui.forecastTodayHighValueLabel.pos = (150, 248)
        ui.forecastTodayHumidityLabel.pos = (30, 231)
        ui.forecastTodayHumidityValueLabel.pos = (150, 231)
        ui.forecastTodayWindLabel.pos = (30, 214)
        ui.forecastTodayWindValueLabel.pos = (150, 214)
        ui.forecastTodayCloudsLabel.pos = (30, 197)
        ui.forecastTodayCloudsValueLabel.pos = (150, 197)
        ui.forecastTodayRainLabel.pos = (30, 180)
        ui.forecastTodayRainValueLabel.pos = (150, 180)

        forecastTomoHeading = Label(text="[b]" + _("Tomorrow") + "[/b]:", font_size='20sp', markup=True, size_hint=(None, None),
                                    pos=(0, 130))
        ui.forecastTomoImg.pos = (0, 100)
        ui.forecastTomoSummaryLabel.pos = (100, 100)
        ui.forecastTomoHighLabel.pos = (30, 73)
        ui.forecastTomoHighValueLabel.pos = (150, 73)
        ui.forecastTomoHumidityLabel.pos = (30, 57)
        ui.forecastTomoHumidityValueLabel.pos = (150, 57)
        ui.forecastTomoWindLabel.pos = (30, 41)
        ui.forecastTomoWindValueLabel.pos = (150, 41)
        ui.forecastTomoCloudsLabel.pos = (30, 25)
        ui.forecastTomoCloudsValueLabel.pos = (150, 25)
        ui.forecastTomoRainLabel.pos = (30, 9)
        ui.forecastTomoRainValueLabel.pos = (150, 9)

        thermostatUI.add_widget(wimg)
        thermostatUI.add_widget(ui.coolControl)
        thermostatUI.add_widget(ui.heatControl)
        thermostatUI.add_widget(ui.fanControl)
        thermostatUI.add_widget(ui.holdControl)
        thermostatUI.add_widget(ui.tempSlider)
        thermostatUI.add_widget(ui.currentLabel)
        thermostatUI.add_widget(ui.currentWaterLabel)
        thermostatUI.add_widget(ui.currentWaterValueLabel)
        thermostatUI.add_widget(ui.setLabel)
        thermostatUI.add_widget(ui.statusHeatLabel)
        thermostatUI.add_widget(ui.statusCoolLabel)
        thermostatUI.add_widget(ui.statusFanLabel)
        thermostatUI.add_widget(ui.statusSchedLabel)
        thermostatUI.add_widget(ui.statusHeatValueLabel)
        thermostatUI.add_widget(ui.statusCoolValueLabel)
        thermostatUI.add_widget(ui.statusFanValueLabel)
        thermostatUI.add_widget(ui.statusSchedValueLabel)

        thermostatUI.add_widget(ui.dateLabel)
        thermostatUI.add_widget(ui.timeLabel)
        thermostatUI.add_widget(ui.weatherImg)
        thermostatUI.add_widget(ui.weatherSummaryLabel)
        thermostatUI.add_widget(ui.weatherTempLabel)
        thermostatUI.add_widget(ui.weatherTempValueLabel)
        thermostatUI.add_widget(ui.weatherHumidityLabel)
        thermostatUI.add_widget(ui.weatherHumidityValueLabel)
        thermostatUI.add_widget(ui.weatherWindLabel)
        thermostatUI.add_widget(ui.weatherWindValueLabel)
        thermostatUI.add_widget(ui.weatherCloudsLabel)
        thermostatUI.add_widget(ui.weatherCloudsValueLabel)
        thermostatUI.add_widget(ui.weatherSunLabel)
        thermostatUI.add_widget(ui.weatherSunValueLabel)

        thermostatUI.add_widget(ui.versionLabel)
        thermostatUI.add_widget(forecastTodayHeading)
        thermostatUI.add_widget(ui.forecastTodayImg)
        thermostatUI.add_widget(ui.forecastTodaySummaryLabel)
        thermostatUI.add_widget(ui.forecastTodayHighLabel)
        thermostatUI.add_widget(ui.forecastTodayHighValueLabel)
        thermostatUI.add_widget(ui.forecastTodayHumidityLabel)
        thermostatUI.add_widget(ui.forecastTodayHumidityValueLabel)
        thermostatUI.add_widget(ui.forecastTodayWindLabel)
        thermostatUI.add_widget(ui.forecastTodayWindValueLabel)
        thermostatUI.add_widget(ui.forecastTodayCloudsLabel)
        thermostatUI.add_widget(ui.forecastTodayCloudsValueLabel)
        thermostatUI.add_widget(ui.forecastTodayRainLabel)
        thermostatUI.add_widget(ui.forecastTodayRainValueLabel)

        thermostatUI.add_widget(forecastTomoHeading)
        thermostatUI.add_widget(ui.forecastTomoImg)
        thermostatUI.add_widget(ui.forecastTomoSummaryLabel)
        thermostatUI.add_widget(ui.forecastTomoHighLabel)
        thermostatUI.add_widget(ui.forecastTomoHighValueLabel)
        thermostatUI.add_widget(ui.forecastTomoHumidityLabel)
        thermostatUI.add_widget(ui.forecastTomoHumidityValueLabel)
        thermostatUI.add_widget(ui.forecastTomoWindLabel)
        thermostatUI.add_widget(ui.forecastTomoWindValueLabel)
        thermostatUI.add_widget(ui.forecastTomoCloudsLabel)
        thermostatUI.add_widget(ui.forecastTomoCloudsValueLabel)
        thermostatUI.add_widget(ui.forecastTomoRainLabel)
        thermostatUI.add_widget(ui.forecastTomoRainValueLabel)

        layout = thermostatUI


        if minUIEnabled:
            uiScreen = Screen(name="thermostatUI")
            uiScreen.add_widget(thermostatUI)

            minScreen = MinimalScreen(name="minimalUI")
            minUI = FloatLayout(size=(800, 480))

            with minUI.canvas.before:
                Color(0.0, 0.0, 0.0, 1)
                self.rect = Rectangle(size=(800, 480), pos=minUI.pos)

            ui.altCurLabel.pos = (390, 275)
            ui.altTimeLabel.pos = (45, 398)
            ui.altDecisionLabel.pos = (575, 398)
            ui.altWaterLabel.pos = (55, 165)
            ui.altWaterValueLabel.pos = (240, 163)
            ui.altHeaterLabel.pos = (430, 165)
            ui.altHeaterValueLabel.pos = (575, 163)

            # battery line: per settings key "battery_line_pos": [x, y]
            # (thermostat_settings.json) tweakable without git roundtrips.
            battery_pos = list(cfg.value("battery_line_pos", [35, 225]))
            ui.altBatteryLabel.pos = (battery_pos[0], battery_pos[1])
            ui.altBatteryValueLabel.pos = (battery_pos[0] + 130, battery_pos[1] - 3)

            global priceBarsWidget
            priceBarsWidget = ui.PriceBarsWidget(size=(800, 140), size_hint=(None, None), pos=(0, 0))

            minUI.add_widget(ui.altCurLabel)
            minUI.add_widget(ui.altTimeLabel)
            minUI.add_widget(ui.altWaterLabel)
            minUI.add_widget(ui.altWaterValueLabel)
            minUI.add_widget(ui.altHeaterLabel)
            minUI.add_widget(ui.altHeaterValueLabel)
            minUI.add_widget(ui.altBatteryLabel)
            minUI.add_widget(ui.altBatteryValueLabel)
            minUI.add_widget(ui.altDecisionLabel)
            minUI.add_widget(priceBarsWidget)
            minScreen.add_widget(minUI)

            screenMgr = ScreenManager(
                transition=NoTransition())  # FadeTransition seems to have OpenGL bugs in Kivy Dev 1.9.1 and is unstable, so sticking with no transition for now
            screenMgr.add_widget(uiScreen)
            screenMgr.add_widget(minScreen)

            layout = screenMgr

            minUITimer = Clock.schedule_once(show_minimal_ui, minUITimeout)

            if pirEnabled:
                Clock.schedule_interval(check_pir, pirCheckInterval)

        Clock.schedule_interval(check_sensor_temp, tempCheckInterval)

        if hotwater_control is not None and hotwater_control.enabled:
            hotwater_control.set_ui_callback(update_hotwater_ui)
            hotwater_control.start()

        Clock.schedule_once(display_current_weather, 5)
        Clock.schedule_once(display_forecast_weather, 10)

        return layout


##############################################################################
#                                                                            #
#       Web Server Interface                                                 #
#                                                                            #
##############################################################################

def apply_set_temp(new_temp):
    app.set_temp = new_temp
    ui.setLabel.text = "  Set\n[b]" + str(app.set_temp) + scaleUnits + "[/b]"
    ui.tempSlider.value = app.set_temp


def apply_controls(heat, cool, fan, hold):
    ui.setControlState(ui.heatControl, "down" if heat else "normal")
    ui.setControlState(ui.coolControl, "down" if cool else "normal")
    ui.setControlState(ui.fanControl, "down" if fan else "normal")
    ui.setControlState(ui.holdControl, "down" if hold else "normal")
    app.heat = bool(heat)
    app.cool = bool(cool)
    app.fan = bool(fan)
    app.hold = bool(hold)


def _web_log_info(subtype, msg):
    log(LOG_LEVEL_INFO, CHILD_DEVICE_WEBSERVER, subtype, msg)


def _web_log_state(subtype, msg):
    log(LOG_LEVEL_STATE, CHILD_DEVICE_WEBSERVER, subtype, msg)


class _SchedulerLog(object):
    def info(self, subtype, msg):
        log(LOG_LEVEL_INFO, CHILD_DEVICE_SCHEDULER, subtype, msg)

    def state(self, subtype, msg):
        log(LOG_LEVEL_STATE, CHILD_DEVICE_SCHEDULER, subtype, msg)

    def debug(self, subtype, msg):
        log(LOG_LEVEL_DEBUG, CHILD_DEVICE_SCHEDULER, subtype, msg)

    def error(self, subtype, msg):
        log(LOG_LEVEL_ERROR, CHILD_DEVICE_SCHEDULER, subtype, msg)


scheduler = Scheduler(
    app=app,
    apply_set_temp=apply_set_temp,
    temp_scale=tempScale,
    units=scaleUnits,
    use_test_schedule=useTestSchedule,
    schedule_lock=scheduleLock,
    thermostat_lock=thermostatLock,
    log=_SchedulerLog(),
)


def startWebServer():
    host = cfg.get("web", "host")
    # when host = "discover", use the local IP address
    cherrypy.server.socket_host = host if host != "discover" else get_ip_address()
    cherrypy.server.socket_port = cfg.get("web", "port")

    log(LOG_LEVEL_STATE, CHILD_DEVICE_WEBSERVER, MSG_SUBTYPE_TEXT,
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
        {'log.screen': debug,
         'log.access_file': "",
         'log.error_file': ""
         }
    )

    cherrypy.quickstart(WebInterface(
        app=app,
        status_provider=get_status_info,
        set_setpoint=apply_set_temp,
        set_controls=apply_controls,
        reload_schedule=scheduler.reload,
        version=THERMOSTAT_VERSION,
        min_temp=minTemp,
        max_temp=maxTemp,
        temp_step=tempStep,
        units=scaleUnits,
        thermostat_lock=thermostatLock,
        schedule_lock=scheduleLock,
        log_info=_web_log_info,
        log_state=_web_log_state,
    ), '/', conf)


##############################################################################
#                                                                            #
#       Main                                                                 #
#                                                                            #
##############################################################################

def main():
    webThread = threading.Thread(target=startWebServer)
    webThread.daemon = True
    webThread.start()

    scheduler.reload()
    schedThread = threading.Thread(target=scheduler.run_forever)
    schedThread.daemon = True
    schedThread.start()

    ThermostatApp().run()

if __name__ == '__main__':
    try:
        main()
    finally:
        log(LOG_LEVEL_STATE, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/shutdown", "Thermostat Shutting Down...")
        GPIO.cleanup()

        if logFile is not None:
            logFile.flush()
            os.fsync(logFile.fileno())
            logFile.close()

        if mqttEnabled:
            mqttc.loop_stop()
            mqttc.disconnect()
