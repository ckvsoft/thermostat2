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
# import math
import os
import os.path
import re
import gettext
# import random
import socket
import sys
import threading
import time
import urllib.request
import uuid

import kivy

##############################################################################
#                                                                            #
#       Kivy UI Imports                                                      #
#                                                                            #
##############################################################################

kivy.require('2.1.0')  # replace with your current kivy version !

from kivy.app import App
# from kivy.uix.button import Button
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.label import Label
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.slider import Slider
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.storage.jsonstore import JsonStore
from kivy.uix.screenmanager import ScreenManager, Screen, NoTransition

##############################################################################
#                                                                            #
#       Other Imports                                                        #
#                                                                            #
##############################################################################

import cherrypy
import schedule
import subprocess
import locale

# from gpiozero import LED
# from gpiozero.pins.pigpio import PiGPIOFactory

# factory = PiGPIOFactory(host='10.1.1.110')
#
# pump = LED(21, pin_factory=factory)
# pumpWW = LED(20, pin_factory=factory)

##############################################################################
#                                                                            #
#       GPIO & Simulation Imports                                            #
#                                                                            #
##############################################################################

try:
    import RPi.GPIO as GPIO
except ImportError:
    import FakeRPi.GPIO as GPIO

try:
    from w1thermsensor import W1ThermSensor, Unit
except ImportError:
    from FakeRPi.w1thermsensor import W1ThermSensor, Unit

##############################################################################
#                                                                            #
#       Sensor Imports                                                       #
#                                                                            #
##############################################################################

# from w1thermsensor import W1ThermSensor, Unit


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
#       Utility classes                                                      #
#                                                                            #
##############################################################################

# class switch(object):
#    def __init__(self, value):
#        self.value = value
#        self.fall = False
#
#    def __iter__(self):
#        """Return the match method once, then stop"""
#        yield self.match
#        raise StopIteration
#
#    def match(self, *args):
#        """Indicate whether to enter a case suite"""
#        if self.fall or not args:
#            return True
#        elif self.value in args:  # changed for v1.5, see below
#            self.fall = True
#            return True
#        else:
#            return False

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
MSG_SUBTYPE_TRIPPED = "armed"
MSG_SUBTYPE_ARMED = "tripped"
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

THERMOSTAT_VERSION = "2.0.6"

# Debug settings

debug = False
useTestSchedule = False

# Threading Locks

thermostatLock = threading.RLock()
weatherLock = threading.Lock()
scheduleLock = threading.RLock()

# Thermostat persistent settings

settings = JsonStore("thermostat_settings.json")
state = JsonStore("thermostat_state.json")

# Internationalization (i18n)
t_locale = 'de_AT.utf8' if not (settings.exists("i18n")) else settings.get("i18n")["locale"]
locale.setlocale(locale.LC_ALL, t_locale)

# domesticwater
domestic_water_enabled = False if not (settings.exists("domestic_water")) else settings.get("domestic_water")["enabled"]
domestic_water_topic = '' if not (settings.exists("domestic_water")) else settings.get("domestic_water")["topic"]
domestic_key_value_pair = '' if not (settings.exists("domestic_water")) else settings.get("domestic_water")["key_value_pair"]
domestic_timeout_duration = 300 # 5 min
domestic_last_message_time = 0

# MQTT settings/setup

def mqtt_on_connect(client, userdata, flags, rc):
    global mqttReconnect

    print("MQTT Connected with result code: " + str(rc))

    if rc == 0:
        if mqttReconnect:
            log(LOG_LEVEL_STATE, CHILD_DEVICE_MQTT, MSG_SUBTYPE_TEXT,
                "Reconnected to: " + mqttServer + ":" + str(mqttPort))
        else:
            mqttReconnect = True
            log(LOG_LEVEL_STATE, CHILD_DEVICE_MQTT, MSG_SUBTYPE_TEXT,
                "Connected to: " + mqttServer + ":" + str(mqttPort))

        mqtt_subscriptions = [
            (mqttSub_restart, 0),  # Subscribe to restart commands
            (mqttSub_loglevel, 0),  # Subscribe to log level commands
            (mqttSub_version, 0)  # Subscribe to version commands
        ]

        if domestic_water_enabled:
            mqtt_subscriptions.append((domestic_water_topic, 0))

        mqtt_subscriptions.append((mqttSub_state, 0))
        src = client.subscribe(mqtt_subscriptions)

        if src[0] == 0:
            log(LOG_LEVEL_INFO, CHILD_DEVICE_MQTT, MSG_SUBTYPE_TEXT,
                "Subscribe Succeeded: " + mqttServer + ":" + str(mqttPort))
        else:
            log(LOG_LEVEL_ERROR, CHILD_DEVICE_MQTT, MSG_SUBTYPE_TEXT, "Subscribe FAILED, result code: " + src[0])


if mqttAvailable:
    mqttReconnect = False
    mqttEnabled = True if not (settings.exists("mqtt")) else settings.get("mqtt")["enabled"]
    mqttClientID = 'thermostat1' if not (settings.exists("mqtt")) else settings.get("mqtt")["clientID"]
    mqttServer = '127.0.0.1' if not (settings.exists("mqtt")) else settings.get("mqtt")["server"]
    mqttPort = 1883 if not (settings.exists("mqtt")) else settings.get("mqtt")["port"]
    mqttPubPrefix = "thermostat" if not (settings.exists("mqtt")) else settings.get("mqtt")["pubPrefix"]

    mqttSub_version = str(mqttPubPrefix + "/" + mqttClientID + "/command/version")
    mqttSub_restart = str(mqttPubPrefix + "/" + mqttClientID + "/command/restart")
    mqttSub_loglevel = str(mqttPubPrefix + "/" + mqttClientID + "/command/loglevel")
    mqttSub_state = str(mqttPubPrefix + "/" + mqttClientID + "/command/state")

    mqttPub_state = str(mqttPubPrefix + "/" + mqttClientID + "/state/status")
    mqttPub_fanstate = str(mqttPubPrefix + "/" + mqttClientID + "/state/fan")

else:
    mqttEnabled = False

# Logging settings/setup

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


loggingChannel = "none" if not (settings.exists("logging")) else settings.get("logging")["channel"]
loggingLevel = "state" if not (settings.exists("logging")) else settings.get("logging")["level"]

loggingChannel = "none" if not (settings.exists("logging")) else settings.get("logging")["channel"]
loggingLevel = "state" if not (settings.exists("logging")) else settings.get("logging")["level"]

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
    log = log_dummy  # Default case

logLevel = LOG_LEVELS.get(loggingLevel, LOG_LEVEL_NONE)

# Send presentations for Node

log(LOG_LEVEL_STATE, CHILD_DEVICE_NODE, MSG_SUBTYPE_NAME, "Thermostat Starting Up...", msg_type=MSG_TYPE_PRESENTATION)
log(LOG_LEVEL_STATE, CHILD_DEVICE_NODE, MSG_SUBTYPE_VERSION, THERMOSTAT_VERSION, msg_type=MSG_TYPE_PRESENTATION)

# send presentations for all other child "sensors"

for i in range(len(CHILD_DEVICES)):
    child = CHILD_DEVICES[i]
    if child != CHILD_DEVICE_NODE:
        log(LOG_LEVEL_STATE, child, child, "", msg_type=MSG_TYPE_PRESENTATION)

# Various temperature settings:
tempScale = settings.get("scale")["tempScale"]
scaleUnits = "c" if tempScale == "metric" else "f"
precipUnits = " mm" if tempScale == "metric" else '"'
precipFactor = 1.0 if tempScale == "metric" else 0.0393701
precipRound = 0 if tempScale == "metric" else 1
sensorUnits = Unit.DEGREES_C if tempScale == "metric" else Unit.DEGREES_F
# sensorUnits         = W1ThermSensor.DEGREES_C if tempScale == "metric" else W1ThermSensor.DEGREES_F
windFactor = 3.6 if tempScale == "metric" else 1.0
windUnits = " km/h" if tempScale == "metric" else " mph"

TEMP_TOLERANCE = 0.1 if tempScale == "metric" else 0.18

currentTemp = 22.0 if tempScale == "metric" else 72.0
domesticwater = "n/a"
minFlowTemp = 65.0
currentFlowTemp = 0.0

priorCorrected = -100.0
setTemp = 22.0 if not (state.exists("state")) else state.get("state")["setTemp"]

tempHysteresis = 0.5 if not (settings.exists("thermostat")) else settings.get("thermostat")["tempHysteresis"]

tempCheckInterval = 3 if not (settings.exists("thermostat")) else settings.get("thermostat")["tempCheckInterval"]

minUIEnabled = 0 if not (settings.exists("thermostat")) else settings.get("thermostat")["minUIEnabled"]
minUITimeout = 3 if not (settings.exists("thermostat")) else settings.get("thermostat")["minUITimeout"]
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
log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/temperature/currentTemp", str(currentTemp),
    timestamp=False)
log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/temperature/setTemp", str(setTemp),
    timestamp=False)
log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/temperature/tempHysteresis", str(tempHysteresis),
    timestamp=False)
log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/temperature/tempCheckInterval",
    str(tempCheckInterval), timestamp=False)
log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/temperature/minUIEnabled", str(minUIEnabled),
    timestamp=False)
log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/temperature/minUITimeout", str(minUITimeout),
    timestamp=False)

# Temperature calibration settings:

elevation = 0 if not (settings.exists("thermostat")) else settings.get("calibration")["elevation"]
boilingPoint = (100.0 - 0.003353 * elevation) if tempScale == "metric" else (212.0 - 0.00184 * elevation)
freezingPoint = 0.01 if tempScale == "metric" else 32.018
referenceRange = boilingPoint - freezingPoint

boilingMeasured = settings.get("calibration")["boilingMeasured"]
freezingMeasured = settings.get("calibration")["freezingMeasured"]
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

# UI Slider settings:

minTemp = 15.0 if not (settings.exists("thermostat")) else settings.get("thermostat")["minTemp"]
maxTemp = 30.0 if not (settings.exists("thermostat")) else settings.get("thermostat")["maxTemp"]
tempStep = 0.5 if not (settings.exists("thermostat")) else settings.get("thermostat")["tempStep"]

log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/UISlider/minTemp", str(minTemp), timestamp=False)
log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/UISlider/maxTemp", str(maxTemp), timestamp=False)
log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/UISlider/tempStep", str(tempStep),
    timestamp=False)

try:
    tempSensor = W1ThermSensor()
except W1ThermSensor:
    tempSensor = None

# Faikin (Daikin AC) setup:
faikinEnabled = 0 if not (settings.exists("faikin")) else settings.get("faikin")["enabled"]
faikinName = 'GuestAC' if not (settings.exists("faikin")) else settings.get("faikin")["name"]

# PIR (Motion Sensor) setup:
pirEnabled = 0 if not (settings.exists("pir")) else settings.get("pir")["pirEnabled"]
pirPin = 5 if not (settings.exists("pir")) else settings.get("pir")["pirPin"]

pirCheckInterval = 0.5 if not (settings.exists("pir")) else settings.get("pir")["pirCheckInterval"]

pirIgnoreFromStr = "00:00" if not (settings.exists("pir")) else settings.get("pir")["pirIgnoreFrom"]
pirIgnoreToStr = "00:00" if not (settings.exists("pir")) else settings.get("pir")["pirIgnoreTo"]

pirIgnoreFrom = datetime.time(int(pirIgnoreFromStr.split(":")[0]), int(pirIgnoreFromStr.split(":")[1]))
pirIgnoreTo = datetime.time(int(pirIgnoreToStr.split(":")[0]), int(pirIgnoreToStr.split(":")[1]))

log(LOG_LEVEL_INFO, CHILD_DEVICE_PIR, MSG_SUBTYPE_ARMED, str(pirEnabled), timestamp=False)
log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/pir/checkInterval", str(pirCheckInterval),
    timestamp=False)
log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/pir/ignoreFrom", str(pirIgnoreFromStr),
    timestamp=False)
log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/pir/ignoreTo", str(pirIgnoreToStr),
    timestamp=False)

# GPIO Pin setup and utility routines:

coolPin = 18 if not (settings.exists("thermostat")) else settings.get("thermostat")["coolPin"]
heatPin = 23 if not (settings.exists("thermostat")) else settings.get("thermostat")["heatPin"]
fanPin = 25 if not (settings.exists("thermostat")) else settings.get("thermostat")["fanPin"]

GPIO.setmode(GPIO.BCM)
GPIO.setup(coolPin, GPIO.OUT)
GPIO.output(coolPin, GPIO.HIGH)
GPIO.setup(heatPin, GPIO.OUT)
GPIO.output(heatPin, GPIO.HIGH)
GPIO.setup(fanPin, GPIO.OUT)
GPIO.output(fanPin, GPIO.HIGH)

if pirEnabled:
    GPIO.setup(pirPin, GPIO.IN)

CHILD_DEVICE_HEAT = "heat"
CHILD_DEVICE_COOL = "cool"
CHILD_DEVICE_FAN = "fan"

log(LOG_LEVEL_INFO, CHILD_DEVICE_COOL, MSG_SUBTYPE_BINARY_STATUS, str(coolPin), timestamp=False)
log(LOG_LEVEL_INFO, CHILD_DEVICE_HEAT, MSG_SUBTYPE_BINARY_STATUS, str(heatPin), timestamp=False)
log(LOG_LEVEL_INFO, CHILD_DEVICE_FAN, MSG_SUBTYPE_BINARY_STATUS, str(fanPin), timestamp=False)
log(LOG_LEVEL_INFO, CHILD_DEVICE_PIR, MSG_SUBTYPE_TRIPPED, str(pirPin), timestamp=False)

##############################################################################
#                                                                            #
#       UI Controls/Widgets                                                  #
#                                                                            #
##############################################################################

controlColours = {
    "normal": (1.0, 1.0, 1.0, 1.0),
    "K\u00fchlen": (0.0, 0.0, 1.0, 0.4),
    "Heizen": (1.0, 0.0, 0.0, 1.0),
    "Pumpe": (0.0, 1.0, 0.0, 0.4),
    "Halten": (0.0, 1.0, 0.0, 0.4),
}


def setControlState(control, state):
    with thermostatLock:
        control.state = state
        if state == "normal":
            control.background_color = controlColours["normal"]
        else:
            control.background_color = controlColours[control.text.replace("[b]", "").replace("[/b]", "")]

        controlLabel = control.text.replace("[b]", "").replace("[/b]", "").lower()
        log(LOG_LEVEL_STATE, controlLabel + CHILD_DEVICE_SUFFIX_UICONTROL, MSG_SUBTYPE_BINARY_STATUS,
            "0" if state == "normal" else "1")


coolControl = ToggleButton(text="[b]K\u00fchlen[/b]",
                           markup=True,
                           size_hint=(None, None)
                           )

setControlState(coolControl, "normal" if not (state.exists("state")) else state.get("state")["coolControl"])

heatControl = ToggleButton(text="[b]Heizen[/b]",
                           markup=True,
                           size_hint=(None, None)
                           )

setControlState(heatControl, "normal" if not (state.exists("state")) else state.get("state")["heatControl"])

fanControl = ToggleButton(text="[b]Pumpe[/b]",
                          markup=True,
                          size_hint=(None, None)
                          )

setControlState(fanControl, "normal" if not (state.exists("state")) else state.get("state")["fanControl"])

holdControl = ToggleButton(text="[b]Halten[/b]",
                           markup=True,
                           size_hint=(None, None)
                           )

setControlState(holdControl, "normal" if not (state.exists("state")) else state.get("state")["holdControl"])


def get_status_string():
    with thermostatLock:
        sched = "None"

        if holdControl.state == "down":
            sched = "Halten"
        elif useTestSchedule:
            sched = "Test"
        elif heatControl.state == "down":
            sched = "Heizen"
        elif coolControl.state == "down":
            sched = "K\u00fchlen"

        return "[b]System:[/b]\n  " + \
            "Heizen: " + ("[color=00ff00][b]Ein[/b][/color]" if not GPIO.input(heatPin) else "Aus") + "\n  " + \
            "K\u00fchlen: " + ("[color=00ff00][b]Ein[/b][/color]" if not GPIO.input(coolPin) else "Aus") + "\n  " + \
            "Pumpe: " + ("[color=00ff00][b]Ein[/b][/color]" if GPIO.input(fanPin) else "Auto") + "\n  " + \
            "Sched: " + sched


versionLabel = Label(text="Thermostat v" + str(THERMOSTAT_VERSION), size_hint=(None, None), font_size='10sp',
                     markup=True, text_size=(150, 20))
currentLabel = Label(text="[b]" + str(currentTemp) + scaleUnits + "[/b]", size_hint=(None, None), font_size='100sp',
                     markup=True, text_size=(300, 200))
currentWaterLabel = Label(text="[b]Warmwasser: " + str(domesticwater) + scaleUnits, size_hint=(None, None), font_size='25sp',
                          markup=True, text_size=(300, 100))

altCurLabel = Label(text=currentLabel.text, size_hint=(None, None), font_size='100sp', markup=True,
                    text_size=(300, 200), color=(0.4, 0.4, 0.4, 0.2))
altWaterLabel = Label(text=currentWaterLabel.text, size_hint=(None, None), font_size='50sp', markup=True,
                      text_size=(500, 200), color=(0.4, 0.4, 0.4, 0.2))

setLabel = Label(text="  Set\n[b]" + str(setTemp) + scaleUnits + "[/b]", size_hint=(None, None), font_size='25sp',
                 markup=True, text_size=(100, 100))
statusLabel = Label(text=get_status_string(), size_hint=(None, None), font_size='20sp', markup=True,
                    text_size=(140, 130))

dateLabel = Label(text="[b]" + time.strftime("%a %d. %b %Y") + "[/b]", size_hint=(None, None), font_size='20sp',
                  markup=True, text_size=(270, 40))

timeStr = time.strftime("%H:%M")

timeLabel = Label(text="[b]" + (timeStr if timeStr[0:1] != "0" else timeStr[1:]) + "[/b]", size_hint=(None, None),
                  font_size='40sp', markup=True, text_size=(180, 75))
altTimeLabel = Label(text=timeLabel.text, size_hint=(None, None), font_size='40sp', markup=True, text_size=(180, 75),
                     color=(0.4, 0.4, 0.4, 0.2))

tempSlider = Slider(orientation='vertical', min=minTemp, max=maxTemp, step=tempStep, value=setTemp,
                    size_hint=(None, None))

screenMgr = None


##############################################################################
#                                                                            #
#       Faikin mqtt stuff                                                    #
#                                                                            #
##############################################################################

def get_state_json():
    autop = True
    if heatControl.state == "down":
        mode = "H"
    elif coolControl.state == "down":
        mode = "C"
    else:
        mode = "A"
        autop = False

    data = {
        "heat": heatControl.state == "down",
        "mode": mode,
        "autop": autop,
        "autot": tempSlider.value
    }
    return json.dumps(data)


def publish_faikin_mqtt_message():
    try:
        payload = get_state_json()
        mqttc.publish(mqttPub_state, payload)

        if faikinEnabled:
            mqttc.publish("command/" + faikinName, payload)
            log(LOG_LEVEL_INFO, CHILD_DEVICE_FAIKIN, MSG_SUBTYPE_FAIKIN + "/command/" + faikinName, str(payload), timestamp=False)

            data = {
                "env": currentTemp,
                "target": [tempSlider.value - tempHysteresis, tempSlider.value + tempHysteresis]
            }
            mqttc.publish("command/" + faikinName +"/control", json.dumps(data))
            log(LOG_LEVEL_INFO, CHILD_DEVICE_FAIKIN, MSG_SUBTYPE_FAIKIN + "/command/" + faikinName + "/control", str(json.dumps(data)), timestamp=False)
    except Exception as e:
        log(LOG_LEVEL_ERROR, CHILD_DEVICE_FAIKIN, MSG_SUBTYPE_FAIKIN + "/" + faikinName, str(e), timestamp=False)



##############################################################################
#                                                                            #
#       Weather functions/constants/widgets                                  #
#                                                                            #
##############################################################################

weatherLocation = settings.get("weather")["location"]
weatherAppKey = settings.get("weather")["appkey"]
weatherURLBase = "http://api.openweathermap.org/data/2.5/"
# weatherURLCurrent   = weatherURLBase + "weather?units=" + tempScale + "&q=" + weatherLocation + "&APPID=" + weatherAppKey
# weatherURLForecast      = weatherURLBase + "forecast/daily?units=" + tempScale + "&q=" + weatherLocation + "&APPID=" + weatherAppKey
weatherURLCurrent = weatherURLBase + "weather?units=" + tempScale + "&id=" + weatherLocation + "&APPID=" + weatherAppKey + "&lang=de"
weatherURLForecast = weatherURLBase + "forecast/daily?units=" + tempScale + "&id=" + weatherLocation + "&APPID=" + weatherAppKey + "&lang=de"
weatherURLTimeout = settings.get("weather")["URLtimeout"]

weatherRefreshInterval = settings.get("weather")["weatherRefreshInterval"] * 60
forecastRefreshInterval = settings.get("weather")["forecastRefreshInterval"] * 60
weatherExceptionInterval = settings.get("weather")["weatherExceptionInterval"] * 60

weatherSummaryLabel = Label(text="", size_hint=(None, None), font_size='20sp', markup=True, text_size=(200, 20))
weatherDetailsLabel = Label(text="", size_hint=(None, None), font_size='20sp', markup=True, text_size=(300, 150),
                            valign="top")
weatherImg = Image(source="web/images/na.png", size_hint=(None, None))

forecastTodaySummaryLabel = Label(text="", size_hint=(None, None), font_size='15sp', markup=True, text_size=(100, 15))
forecastTodayDetailsLabel = Label(text="", size_hint=(None, None), font_size='15sp', markup=True, text_size=(200, 150),
                                  valign="top")
forecastTodayImg = Image(source="web/images/na.png", size_hint=(None, None))
forecastTomoSummaryLabel = Label(text="", size_hint=(None, None), font_size='15sp', markup=True, text_size=(100, 15))
forecastTomoDetailsLabel = Label(text="", size_hint=(None, None), font_size='15sp', markup=True, text_size=(200, 150),
                                 valign="top")
forecastTomoImg = Image(source="web/images/na.png", size_hint=(None, None))


def get_weather(url):
    return json.loads(urllib.request.urlopen(url, None, weatherURLTimeout).read())


def get_cardinal_direction(heading):
    directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW", "N"]
    return directions[int(round(((heading % 360) / 45)))]


def display_current_weather(dt):
    with weatherLock:
        interval = weatherRefreshInterval

        try:
            weather = get_weather(weatherURLCurrent)

            weatherImg.source = "web/images/" + weather["weather"][0]["icon"] + ".png"

            weatherSummaryLabel.text = "[b]" + weather["weather"][0]["description"].title() + "[/b]"

            weatherDetailsLabel.text = "\n".join((
                "Temp:       " + str(int(round(weather["main"]["temp"], 0))) + scaleUnits,
                "Humidity: " + str(weather["main"]["humidity"]) + "%",
                "Wind:        " + str(
                    int(round(weather["wind"]["speed"] * windFactor))) + windUnits + " " + get_cardinal_direction(
                    weather["wind"]["deg"]),
                "Wolken:    " + str(weather["clouds"]["all"]) + "%",
                "Sonne:      " + time.strftime("%H:%M",
                                               time.localtime(weather["sys"]["sunrise"])) + ", " + time.strftime(
                    "%H:%M", time.localtime(weather["sys"]["sunset"])) + ""
            ))

            log(LOG_LEVEL_INFO, CHILD_DEVICE_WEATHER_CURR, MSG_SUBTYPE_TEXT,
                weather["weather"][0]["description"].title() + "; " + re.sub('\n', "; ", re.sub(' +', ' ',
                                                                                                weatherDetailsLabel.text).strip()))

        except Exception as e:
            interval = weatherExceptionInterval

            weatherImg.source = "web/images/na.png"
            weatherSummaryLabel.text = ""
            weatherDetailsLabel.text = ""

            log(LOG_LEVEL_ERROR, CHILD_DEVICE_WEATHER_CURR, MSG_SUBTYPE_TEXT, "Update FAILED!")
            log(LOG_LEVEL_ERROR, CHILD_DEVICE_WEATHER_CURR, MSG_SUBTYPE_TEXT, "Exception {e}")

        Clock.schedule_once(display_current_weather, interval)


def get_precip_amount(raw):
    precip = round(raw * precipFactor, precipRound)

    if tempScale == "metric":
        return str(int(precip))
    else:
        return str(precip)


def display_forecast_weather(dt):
    with weatherLock:
        interval = forecastRefreshInterval

        try:
            forecast = get_weather(weatherURLForecast)

            today = forecast["list"][0]
            tomo = forecast["list"][1]

            forecastTodayImg.source = "web/images/" + today["weather"][0]["icon"] + ".png"

            forecastTodaySummaryLabel.text = "[b]" + today["weather"][0]["description"].title() + "[/b]"

            todayText = "\n".join((
                "High:         " + str(int(round(today["temp"]["max"], 0))) + scaleUnits + ", Low: " + str(
                    int(round(today["temp"]["min"], 0))) + scaleUnits,
                "Humidity: " + str(today["humidity"]) + "%",
                "Wind:        " + str(
                    int(round(today["speed"] * windFactor))) + windUnits + " " + get_cardinal_direction(today["deg"]),
                "Wolken:   " + str(today["clouds"]) + "%",
            ))

            if "rain" in today or "snow" in today:
                todayText += "\n"
                if "rain" in today:
                    todayText += "Regen:        " + get_precip_amount(today["rain"]) + precipUnits
                    if "snow" in today:
                        todayText += ", Schnee: " + get_precip_amount(today["snow"]) + precipUnits
                else:
                    todayText += "Schnee:       " + get_precip_amount(today["snow"]) + precipUnits

            forecastTodayDetailsLabel.text = todayText

            forecastTomoImg.source = "web/images/" + tomo["weather"][0]["icon"] + ".png"

            forecastTomoSummaryLabel.text = "[b]" + tomo["weather"][0]["description"].title() + "[/b]"

            tomoText = "\n".join((
                "High:         " + str(int(round(tomo["temp"]["max"], 0))) + scaleUnits + ", Low: " + str(
                    int(round(tomo["temp"]["min"], 0))) + scaleUnits,
                "Humidity: " + str(tomo["humidity"]) + "%",
                "Wind:        " + str(
                    int(round(tomo["speed"] * windFactor))) + windUnits + " " + get_cardinal_direction(tomo["deg"]),
                "Wolken:    " + str(tomo["clouds"]) + "%",
            ))

            if "rain" in tomo or "snow" in tomo:
                tomoText += "\n"
                if "rain" in tomo:
                    tomoText += "Regen:       " + get_precip_amount(tomo["rain"]) + precipUnits
                    if "snow" in tomo:
                        tomoText += ", Schnee: " + get_precip_amount(tomo["snow"]) + precipUnits
                else:
                    tomoText += "Schnee:      " + get_precip_amount(tomo["snow"]) + precipUnits

            forecastTomoDetailsLabel.text = tomoText

            log(LOG_LEVEL_INFO, CHILD_DEVICE_WEATHER_FCAST_TODAY, MSG_SUBTYPE_TEXT,
                today["weather"][0]["description"].title() + "; " + re.sub('\n', "; ", re.sub(' +', ' ',
                                                                                              forecastTodayDetailsLabel.text).strip()))
            log(LOG_LEVEL_INFO, CHILD_DEVICE_WEATHER_FCAST_TOMO, MSG_SUBTYPE_TEXT,
                tomo["weather"][0]["description"].title() + "; " + re.sub('\n', "; ", re.sub(' +', ' ',
                                                                                             forecastTomoDetailsLabel.text).strip()))

        except Exception as e:
            interval = weatherExceptionInterval

            forecastTodayImg.source = "web/images/na.png"
            forecastTodaySummaryLabel.text = ""
            forecastTodayDetailsLabel.text = ""
            forecastTomoImg.source = "web/images/na.png"
            forecastTomoSummaryLabel.text = ""
            forecastTomoDetailsLabel.text = ""

            log(LOG_LEVEL_ERROR, CHILD_DEVICE_WEATHER_FCAST_TODAY, MSG_SUBTYPE_TEXT, "Update FAILED!")
            log(LOG_LEVEL_ERROR, CHILD_DEVICE_WEATHER_FCAST_TODAY, MSG_SUBTYPE_TEXT, "Exception {e}")

        Clock.schedule_once(display_forecast_weather, interval)


##############################################################################
#                                                                            #
#       Thermostat Implementation                                            #
#                                                                            #
##############################################################################

# Main furnace/AC system control function:

def change_system_settings():
    with thermostatLock:
        global currentFlowTemp, minFlowTemp

        hpin_start = str(GPIO.input(heatPin))
        cpin_start = str(GPIO.input(coolPin))
        fpin_start = str(GPIO.input(fanPin))

        if heatControl.state == "down":
            GPIO.output(coolPin, GPIO.HIGH)

            if setTemp >= currentTemp + tempHysteresis:
                GPIO.output(heatPin, GPIO.LOW)
                GPIO.output(fanPin, GPIO.LOW)
            elif setTemp <= currentTemp:
                GPIO.output(heatPin, GPIO.HIGH)
                if fanControl.state != "down" and GPIO.input(coolPin):
                    GPIO.output(fanPin, GPIO.HIGH)
        else:
            GPIO.output(heatPin, GPIO.HIGH)

            if coolControl.state == "down":
                if setTemp <= currentTemp - tempHysteresis:
                    GPIO.output(coolPin, GPIO.LOW)
                    GPIO.output(fanPin, GPIO.LOW)
                elif setTemp >= currentTemp:
                    GPIO.output(coolPin, GPIO.HIGH)
                    if fanControl.state != "down" and GPIO.input(heatPin):
                        GPIO.output(fanPin, GPIO.LOW)
            else:
                GPIO.output(coolPin, GPIO.HIGH)
                if fanControl.state != "down" and GPIO.input(heatPin):
                    GPIO.output(fanPin, GPIO.HIGH)

        log(LOG_LEVEL_STATE, CHILD_DEVICE_TEMP, MSG_SUBTYPE_TEMPERATURE, "minFlow: " + str(minFlowTemp))
        log(LOG_LEVEL_STATE, CHILD_DEVICE_TEMP, MSG_SUBTYPE_TEMPERATURE, "currentFlow: " + str(currentFlowTemp))

        if fanControl.state == "down":
            GPIO.output(fanPin, GPIO.HIGH)
            # pump.on()
            # setRemote(11)
            setMqttFanCommand("on")
            log(LOG_LEVEL_STATE, CHILD_DEVICE_FAN, MSG_SUBTYPE_TEXT, "1 pump on")
            # setRemotePump( 11 )
        else:
            # setRemote(10)
            setMqttFanCommand("off")
            # setRemotePump( 10 )
            if GPIO.input(heatPin) and GPIO.input(coolPin):
                GPIO.output(fanPin, GPIO.LOW)
                log(LOG_LEVEL_STATE, CHILD_DEVICE_FAN, MSG_SUBTYPE_TEXT, "3 GPIO.LOW")

        # save the thermostat state in case of restart
        state.put("state", setTemp=setTemp, heatControl=heatControl.state, coolControl=coolControl.state,
                  fanControl=fanControl.state, holdControl=holdControl.state)

        statusLabel.text = get_status_string()

        if hpin_start != str(GPIO.input(heatPin)):
            log(LOG_LEVEL_STATE, CHILD_DEVICE_HEAT, MSG_SUBTYPE_BINARY_STATUS, "1" if GPIO.input(heatPin) else "0")
        if cpin_start != str(GPIO.input(coolPin)):
            log(LOG_LEVEL_STATE, CHILD_DEVICE_COOL, MSG_SUBTYPE_BINARY_STATUS, "1" if GPIO.input(coolPin) else "0")
        if fpin_start != str(GPIO.input(fanPin)):
            log(LOG_LEVEL_STATE, CHILD_DEVICE_FAN, MSG_SUBTYPE_BINARY_STATUS, "1" if GPIO.input(fanPin) else "0")

        if mqttEnabled:
            publish_faikin_mqtt_message()

# This callback will be bound to the touch screen UI buttons:

def control_callback(control):
    with thermostatLock:
        setControlState(control, control.state)  # make sure we change the background colour!

        if control is coolControl:
            if control.state == "down":
                setControlState(heatControl, "normal")
            reloadSchedule()

        if control is heatControl:
            if control.state == "down":
                setControlState(coolControl, "normal")
            reloadSchedule()


# Check the current sensor temperature

def check_sensor_temp(dt):
    with thermostatLock:
        global currentTemp, priorCorrected
        global tempSensor

        if tempSensor is not None:
            rawTemp = tempSensor.get_temperature(sensorUnits)
            correctedTemp = (((rawTemp - freezingMeasured) * referenceRange) / measuredRange) + freezingPoint
            currentTemp = round(correctedTemp, 1)
            log(LOG_LEVEL_DEBUG, CHILD_DEVICE_TEMP, MSG_SUBTYPE_CUSTOM + "/raw", str(rawTemp))
            log(LOG_LEVEL_DEBUG, CHILD_DEVICE_TEMP, MSG_SUBTYPE_CUSTOM + "/corrected", str(correctedTemp))

            if abs(priorCorrected - correctedTemp) >= TEMP_TOLERANCE:
                log(LOG_LEVEL_STATE, CHILD_DEVICE_TEMP, MSG_SUBTYPE_TEMPERATURE, str(currentTemp))
                priorCorrected = correctedTemp

        currentLabel.text = "[b]" + str(currentTemp) + scaleUnits + "[/b]"
        altCurLabel.text = currentLabel.text

        dateLabel.text = "[b]" + time.strftime("%a %d. %b %Y") + "[/b]"

        timeStr = time.strftime("%H:%M")

        timeLabel.text = ("[b]" + (timeStr if timeStr[0:1] != "0" else timeStr[1:]) + "[/b]").lower()
        altTimeLabel.text = timeLabel.text

        change_system_settings()

def check_hotwater_temp():
    while True:
        with thermostatLock:
            global hotWater
            global currentWaterLabel, altWaterLabel

            try:
                # Create a TCP/IP socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(10)
                # Connect the socket to the port where the server is listening
                server_address = ('10.1.1.110', 5000)
                sock.connect(server_address)

                # Send data
                message = '2'
                sock.sendall(message.encode("utf-8"))

                data = sock.recv(1024)
                data = str(data.decode("utf-8")).strip()
                data = round(float(data), 1)
                log(LOG_LEVEL_STATE, CHILD_DEVICE_TEMP, MSG_SUBTYPE_TEMPERATURE, str(data))
                sock.close()

                hotWater = data
                currentWaterLabel.text = "[b]Warmwasser: " + str(data) + scaleUnits + "[/b]"
                altWaterLabel.text = "[b]Warmwasser: " + str(data) + scaleUnits + "[/b]"

            except:
                pass

        time.sleep(10)


def setRemote(what):
    with thermostatLock:
        try:
            # Create a TCP/IP socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            # Connect the socket to the port where the server is listening
            server_address = ('10.1.1.110', 5000)
            sock.connect(server_address)

            # Send data
            message = str(what)
            sock.sendall(message.encode("utf-8"))

            data = sock.recv(1024)
            data = str(data.decode("utf-8")).strip()
            data = round(float(data), 1)
            log(LOG_LEVEL_STATE, CHILD_DEVICE_MQTT, MSG_SUBTYPE_TEXT, "setRemote Pump " + str(data))
            sock.close()

        except Exception as e:
            pass
            log(LOG_LEVEL_STATE, CHILD_DEVICE_MQTT, MSG_SUBTYPE_TEXT, "setRemote Pump: Error = " + repr(e))


# This is called when the desired temp slider is updated:
def update_set_temp(slider, value):
    with thermostatLock:
        global setTemp
        priorTemp = setTemp
        setTemp = round(slider.value, 1)
        setLabel.text = "  Set\n[b]" + str(setTemp) + scaleUnits + "[/b]"
        if priorTemp != setTemp:
            log(LOG_LEVEL_STATE, CHILD_DEVICE_UICONTROL_SLIDER, MSG_SUBTYPE_TEMPERATURE, str(setTemp))


# Check the PIR motion sensor status
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


# Minimal UI Display functions and classes

def show_minimal_ui(dt):
    with thermostatLock:
        screenMgr.current = "minimalUI"
        log(LOG_LEVEL_DEBUG, CHILD_DEVICE_SCREEN, MSG_SUBTYPE_TEXT, "Minimal")
        # screen_off()


class MinimalScreen(Screen):
    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            touch.grab(self)
            return True

    def on_touch_up(self, touch):
        global minUITimer

        if touch.grab_current is self:
            touch.ungrab(self)
            with thermostatLock:
                if minUITimer is not None:
                    Clock.unschedule(show_minimal_ui)
                minUITimer = Clock.schedule_once(show_minimal_ui, minUITimeout)
                self.manager.current = "thermostatUI"
                # screen_on()
                log(LOG_LEVEL_DEBUG, CHILD_DEVICE_SCREEN, MSG_SUBTYPE_TEXT, "Full")
            return True


def screen_off():
    command1 = "echo 1"
    command2 = "tee /sys/class/backlight/rpi_backlight/bl_power"
    process1 = subprocess.Popen(command1.split(), stdout=subprocess.PIPE)
    process2 = subprocess.Popen(command2.split(), stdin=process1.stdout, stdout=subprocess.PIPE)
    output = process2.communicate()[0]
    print(output)


def screen_on():
    command1 = "echo 0"
    command2 = "tee /sys/class/backlight/rpi_backlight/bl_power"
    process1 = subprocess.Popen(command1.split(), stdout=subprocess.PIPE)
    process2 = subprocess.Popen(command2.split(), stdin=process1.stdout, stdout=subprocess.PIPE)
    output = process2.communicate()[0]
    print(output)


##############################################################################
#                                                                            #
#       Utility Functions                                                    #
#                                                                            #
##############################################################################

def get_ip_address():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(10)  # 10 seconds
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

    # Zeigen Sie den Inhalt der Nachricht und das Empfangsdatum und die Uhrzeit an
    log(LOG_LEVEL_STATE, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/getVersion", "Empfangene Nachricht: {payload}",
        single=True)
    log(LOG_LEVEL_STATE, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/getVersion",
        "Empfangszeitpunkt: {message.timestamp}", single=True)
    print(f"Empfangene Nachricht: {payload}")
    print(f"Empfangszeitpunkt: {message.timestamp}")
    log(LOG_LEVEL_STATE, CHILD_DEVICE_NODE, MSG_SUBTYPE_VERSION, THERMOSTAT_VERSION)


def restart(message):
    payload = message.payload.decode('utf-8')

    # Zeigen Sie den Inhalt der Nachricht und das Empfangsdatum und die Uhrzeit an
    log(LOG_LEVEL_STATE, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/restart", "Empfangene Nachricht: {payload}",
        single=True)
    log(LOG_LEVEL_STATE, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/restart", "Empfangszeitpunkt: {message.timestamp}",
        single=True)
    print("Empfangene Nachricht: {payload}")
    print("Empfangszeitpunkt: {message.timestamp}")

    pass

    log(LOG_LEVEL_STATE, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/restart", "Thermostat restarting...", single=True)
    GPIO.cleanup()

    if logFile is not None:
        logFile.flush()
        os.fsync(logFile.fileno())
        logFile.close()

    if mqttEnabled:
        mqttc.disconnect()

    os.execl(sys.executable, 'python', __file__, *sys.argv[1:])  # This does not return!!!


def setLogLevel(msg):
    global logLevel

    if LOG_LEVELS.get(msg.payload):
        log(LOG_LEVEL_STATE, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/loglevel",
            "LogLevel set to: " + str(msg.payload))

        logLevel = LOG_LEVELS.get(msg.payload, logLevel)
    else:
        log(LOG_LEVEL_ERROR, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/loglevel",
            "Invalid LogLevel: " + str(msg.payload))

def get_domestic_water(message):
    global domestic_key_value_pair, domesticwater
    global currentWaterLabel, altWaterLabel, domestic_last_message_time
    try:
        payload = message.payload
        if isinstance(payload, bytes):
            payload = payload.decode('utf-8')

        data = json.loads(payload)
        domestic_water_value = data.get(domestic_key_value_pair)
        if domestic_water_value is not None and domesticwater != domestic_water_value:
            domesticwater = domestic_water_value
            currentWaterLabel.text = "[b]Warmwasser: " + str(domesticwater) + scaleUnits + "[/b]"
            altWaterLabel.text = "[b]Warmwasser: " + str(domesticwater) + scaleUnits + "[/b]"

        domestic_last_message_time = time.time()
        Clock.schedule_once(check_domestic_water_timeout, domestic_timeout_duration)

    except json.JSONDecodeError:
        status_msg = "Invalid JSON format in command payload"

def check_domestic_water_timeout(dt):
    global domestic_last_message_time, domesticwater
    global currentWaterLabel, altWaterLabel

    current_time = time.time()
    if current_time - domestic_last_message_time > domestic_timeout_duration:
        domesticwater = "n/a"
        currentWaterLabel.text = "[b]Warmwasser: " + str(domesticwater) + "[/b]"
        altWaterLabel.text = "[b]Warmwasser: " + str(domesticwater) + "[/b]"

def setMqttFanCommand(state):
    if mqttEnabled:
        mqttc.publish(mqttPub_fanstate, state)

if mqttEnabled:
    mqttc = mqtt.Client(mqttClientID)
    mqttc.on_connect = mqtt_on_connect

    mqttc.message_callback_add(mqttSub_restart, lambda client, userdata, message: restart(message) )
    mqttc.message_callback_add(mqttSub_loglevel, lambda client, userdata, message: setLogLevel(message))
    mqttc.message_callback_add(mqttSub_version, lambda client, userdata, message: getVersion(message))
    mqttc.message_callback_add(mqttSub_state, lambda client, userdata, message: get_status_string())
    if domestic_water_enabled:
        mqttc.message_callback_add(domestic_water_topic, lambda client, userdata, message: get_domestic_water(message))

    # Make sure we can reach the mqtt server by pinging it
    pingCount = 0
    pingCmd = "ping -c 1 " + mqttServer

    while os.system(pingCmd) != 0 and pingCount <= 100:
        ++pingCount
        time.sleep(1)

    mqttc.connect(mqttServer, mqttPort)
    mqttc.loop_start()


##############################################################################
#                                                                            #
#       Kivy Thermostat App class                                            #
#                                                                            #
##############################################################################

class ThermostatApp(App):
    def build(self):
        global screenMgr

        gettext.install('thermostat', localedir='locales', names='gettext')

        # Set up the thermostat UI layout:
        thermostatUI = FloatLayout(size=(800, 480))

        # Make the background black:
        with thermostatUI.canvas.before:
            Color(0.0, 0.0, 0.0, 1)
            self.rect = Rectangle(size=(800, 480), pos=thermostatUI.pos)

        # Create the rest of the UI objects ( and bind them to callbacks, if necessary ):

        wimg = Image(source='web/images/logo.png')

        coolControl.bind(on_press=control_callback)
        heatControl.bind(on_press=control_callback)
        fanControl.bind(on_press=control_callback)
        holdControl.bind(on_press=control_callback)

        tempSlider.bind(on_touch_down=update_set_temp, on_touch_move=update_set_temp)

        # set sizing and position info

        wimg.size = (80, 80)
        wimg.size_hint = (None, None)
        wimg.pos = (10, 380)

        heatControl.size = (80, 80)
        heatControl.pos = (680, 380)

        coolControl.size = (80, 80)
        coolControl.pos = (680, 270)

        fanControl.size = (80, 80)
        fanControl.pos = (680, 160)

        statusLabel.pos = (660, 40)

        tempSlider.size = (100, 360)
        tempSlider.pos = (570, 20)

        holdControl.size = (80, 80)
        holdControl.pos = (480, 380)

        setLabel.pos = (590, 390)

        currentLabel.pos = (390, 300)
        currentWaterLabel.pos = (395, 235)

        dateLabel.pos = (180, 370)
        timeLabel.pos = (345, 380)

        weatherImg.pos = (265, 160)
        weatherSummaryLabel.pos = (430, 160)
        weatherDetailsLabel.pos = (395, 60)

        versionLabel.pos = (320, 0)

        forecastTodayHeading = Label(text=_("[b]Today[/b]:"), font_size='20sp', markup=True, size_hint=(None, None),
                                     pos=(0, 300))

        forecastTodayImg.pos = (0, 275)
        forecastTodaySummaryLabel.pos = (100, 275)
        forecastTodayDetailsLabel.pos = (80, 167)

        forecastTomoHeading = Label(text=_("[b]Tomorow[/b]:"), font_size='20sp', markup=True, size_hint=(None, None),
                                    pos=(0, 130))

        forecastTomoImg.pos = (0, 100)
        forecastTomoSummaryLabel.pos = (100, 100)
        forecastTomoDetailsLabel.pos = (80, 7)

        # Add the UI elements to the thermostat UI layout:
        thermostatUI.add_widget(wimg)
        thermostatUI.add_widget(coolControl)
        thermostatUI.add_widget(heatControl)
        thermostatUI.add_widget(fanControl)
        thermostatUI.add_widget(holdControl)
        thermostatUI.add_widget(tempSlider)
        thermostatUI.add_widget(currentLabel)
        thermostatUI.add_widget(currentWaterLabel)
        thermostatUI.add_widget(setLabel)
        thermostatUI.add_widget(statusLabel)
        thermostatUI.add_widget(dateLabel)
        thermostatUI.add_widget(timeLabel)
        thermostatUI.add_widget(weatherImg)
        thermostatUI.add_widget(weatherSummaryLabel)
        thermostatUI.add_widget(weatherDetailsLabel)
        thermostatUI.add_widget(versionLabel)
        thermostatUI.add_widget(forecastTodayHeading)
        thermostatUI.add_widget(forecastTodayImg)
        thermostatUI.add_widget(forecastTodaySummaryLabel)
        thermostatUI.add_widget(forecastTodayDetailsLabel)
        thermostatUI.add_widget(forecastTomoHeading)
        thermostatUI.add_widget(forecastTomoImg)
        thermostatUI.add_widget(forecastTomoDetailsLabel)
        thermostatUI.add_widget(forecastTomoSummaryLabel)

        layout = thermostatUI

        # Minimap UI initialization

        if minUIEnabled:
            uiScreen = Screen(name="thermostatUI")
            uiScreen.add_widget(thermostatUI)

            minScreen = MinimalScreen(name="minimalUI")
            minUI = FloatLayout(size=(800, 480))

            with minUI.canvas.before:
                Color(0.0, 0.0, 0.0, 1)
                self.rect = Rectangle(size=(800, 480), pos=minUI.pos)

            altCurLabel.pos = (390, 290)
            altWaterLabel.pos = (350, 200)
            altTimeLabel.pos = (335, 380)

            minUI.add_widget(altCurLabel)
            minUI.add_widget(altWaterLabel)
            minUI.add_widget(altTimeLabel)
            minScreen.add_widget(minUI)

            screenMgr = ScreenManager(
                transition=NoTransition())  # FadeTransition seems to have OpenGL bugs in Kivy Dev 1.9.1 and is unstable, so sticking with no transition for now
            screenMgr.add_widget(uiScreen)
            screenMgr.add_widget(minScreen)

            layout = screenMgr

            minUITimer = Clock.schedule_once(show_minimal_ui, minUITimeout)

            if pirEnabled:
                Clock.schedule_interval(check_pir, pirCheckInterval)

        # Start checking the temperature
        Clock.schedule_interval(check_sensor_temp, tempCheckInterval)
        #       Clock.schedule_interval( check_hotwater_temp, tempCheckInterval )

        # Show the current weather & forecast
        Clock.schedule_once(display_current_weather, 5)
        Clock.schedule_once(display_forecast_weather, 10)

        return layout


##############################################################################
#                                                                            #
#       Scheduler Implementation                                             #
#                                                                            #
##############################################################################

def startScheduler():
    log(LOG_LEVEL_INFO, CHILD_DEVICE_SCHEDULER, MSG_SUBTYPE_TEXT, "Started")
    while True:
        if holdControl.state == "normal":
            with scheduleLock:
                log(LOG_LEVEL_DEBUG, CHILD_DEVICE_SCHEDULER, MSG_SUBTYPE_TEXT, "Running pending")
                schedule.run_pending()

        time.sleep(10)


def setScheduledTemp(temp):
    with thermostatLock:
        global setTemp
        if holdControl.state == "normal":
            setTemp = round(temp, 1)
            setLabel.text = "  Set\n[b]" + str(setTemp) + scaleUnits + "[/b]"
            tempSlider.value = setTemp
            log(LOG_LEVEL_STATE, CHILD_DEVICE_SCHEDULER, MSG_SUBTYPE_TEMPERATURE, str(setTemp))


def getTestSchedule():
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    testSched = {}

    for i in range(len(days)):
        tempList = []
        for minute in range(60 * 24):
            hrs, mins = divmod(minute, 60)
            tempList.append([
                str(hrs).rjust(2, '0') + ":" + str(mins).rjust(2, '0'),
                float(i + 1) / 10.0 + ((19.0 if tempScale == "metric" else 68.0) if minute % 2 == 1 else (
                    22.0 if tempScale == "metric" else 72.0))
            ])

        testSched[days[i]] = tempList

    return testSched


def reloadSchedule():
    with scheduleLock:
        schedule.clear()

        activeSched = None

        with thermostatLock:
            thermoSched = JsonStore("thermostat_schedule.json")

            if holdControl.state != "down":
                if heatControl.state == "down":
                    activeSched = thermoSched["heat"]
                    log(LOG_LEVEL_INFO, CHILD_DEVICE_SCHEDULER, MSG_SUBTYPE_CUSTOM + "/load", "heat")
                elif coolControl.state == "down":
                    activeSched = thermoSched["cool"]
                    log(LOG_LEVEL_INFO, CHILD_DEVICE_SCHEDULER, MSG_SUBTYPE_CUSTOM + "/load", "cool")

                if useTestSchedule:
                    activeSched = getTestSchedule()
                    log(LOG_LEVEL_INFO, CHILD_DEVICE_SCHEDULER, MSG_SUBTYPE_CUSTOM + "/load", "test")
                    print("Using Test Schedule!!!")

        if activeSched is not None:
            for day, entries in activeSched.items():
                for i, entry in enumerate(entries):
                    getattr(schedule.every(), day).at(entry[0]).do(setScheduledTemp, entry[1])
                    log(LOG_LEVEL_DEBUG, CHILD_DEVICE_SCHEDULER, MSG_SUBTYPE_TEXT,
                        "Set " + day + ", at: " + entry[0] + " = " + str(entry[1]) + scaleUnits)


##############################################################################
#                                                                            #
#       Web Server Interface                                                 #
#                                                                            #
##############################################################################

class WebInterface(object):

    @cherrypy.expose
    def index(self):
        log(LOG_LEVEL_INFO, CHILD_DEVICE_WEBSERVER, MSG_SUBTYPE_TEXT,
            "Served thermostat.html to: " + cherrypy.request.remote.ip)
        file = open("web/html/thermostat.html", "r")

        html = file.read()

        file.close()

        with thermostatLock:
            html = html.replace("@@version@@", str(THERMOSTAT_VERSION))
            html = html.replace("@@temp@@", str(setTemp))
            html = html.replace("@@current@@", str(currentTemp) + scaleUnits)
            html = html.replace("@@domesticwater@@", str(domesticwater) + scaleUnits)
            html = html.replace("@@minTemp@@", str(minTemp))
            html = html.replace("@@maxTemp@@", str(maxTemp))
            html = html.replace("@@tempStep@@", str(tempStep))

            status = statusLabel.text.replace("[b]", "<b>").replace("[/b]", "</b>").replace("\n", "<br>").replace(" ",
                                                                                                                  "&nbsp;")
            status = status.replace("[color=00ff00]", '<font color="red">').replace("[/color]", '</font>')

            html = html.replace("@@status@@", status)
            html = html.replace("@@dt@@", dateLabel.text.replace("[b]", "<b>").replace("[/b]",
                                                                                       "</b>") + ", " + timeLabel.text.replace(
                "[b]", "<b>").replace("[/b]", "</b>"))
            html = html.replace("@@heatChecked@@", "checked" if heatControl.state == "down" else "")
            html = html.replace("@@coolChecked@@", "checked" if coolControl.state == "down" else "")
            html = html.replace("@@fanChecked@@", "checked" if fanControl.state == "down" else "")
            html = html.replace("@@holdChecked@@", "checked" if holdControl.state == "down" else "")

        return html

    @cherrypy.expose
    def set(self, temp, heat="off", cool="off", fan="off", hold="off"):
        global setTemp
        global setLabel
        global heatControl
        global coolControl
        global fanControl

        log(LOG_LEVEL_INFO, CHILD_DEVICE_WEBSERVER, MSG_SUBTYPE_TEXT,
            "Set thermostat received from: " + cherrypy.request.remote.ip)

        tempChanged = setTemp != float(temp)

        with thermostatLock:
            setTemp = float(temp)
            setLabel.text = "  Set\n[b]" + str(setTemp) + "c[/b]"
            tempSlider.value = setTemp

            if tempChanged:
                log(LOG_LEVEL_STATE, CHILD_DEVICE_WEBSERVER, MSG_SUBTYPE_TEMPERATURE, str(setTemp))

            if heat == "on":
                setControlState(heatControl, "down")
            else:
                setControlState(heatControl, "normal")

            if cool == "on":
                setControlState(coolControl, "down")
            else:
                setControlState(coolControl, "normal")

            if fan == "on":
                setControlState(fanControl, "down")
            else:
                setControlState(fanControl, "normal")

            if hold == "on":
                setControlState(holdControl, "down")
            else:
                setControlState(holdControl, "normal")

            reloadSchedule()

        file = open("web/html/thermostat_set.html", "r")

        html = file.read()

        file.close()

        with thermostatLock:
            html = html.replace("@@version@@", str(THERMOSTAT_VERSION))
            html = html.replace("@@dt@@", dateLabel.text.replace("[b]", "<b>").replace("[/b]", "</b>") + ", " + timeLabel.text.replace("[b]", "<b>").replace("[/b]", "</b>"))
            html = html.replace("@@temp@@", ('<font color="red"><b>' if tempChanged else "") + str(setTemp) + (
                '</b></font>' if tempChanged else ""))
            html = html.replace("@@heat@@", ('<font color="red"><b>' if heat == "on" else "") + heat + (
                '</b></font>' if heat == "on" else ""))
            html = html.replace("@@cool@@", ('<font color="red"><b>' if cool == "on" else "") + cool + (
                '</b></font>' if cool == "on" else ""))
            html = html.replace("@@fan@@", ('<font color="red"><b>' if fan == "on" else "") + fan + (
                '</b></font>' if fan == "on" else ""))
            html = html.replace("@@hold@@", ('<font color="red"><b>' if hold == "on" else "") + hold + (
                '</b></font>' if hold == "on" else ""))

        return html

    @cherrypy.expose
    def schedule(self):
        log(LOG_LEVEL_INFO, CHILD_DEVICE_WEBSERVER, MSG_SUBTYPE_TEXT,
            "Served thermostat_schedule.html to: " + cherrypy.request.remote.ip)
        file = open("web/html/thermostat_schedule.html", "r")

        html = file.read()

        file.close()

        with thermostatLock:
            html = html.replace("@@version@@", str(THERMOSTAT_VERSION))
            html = html.replace("@@minTemp@@", str(minTemp))
            html = html.replace("@@maxTemp@@", str(maxTemp))
            html = html.replace("@@tempStep@@", str(tempStep))

            html = html.replace("@@dt@@", dateLabel.text.replace("[b]", "<b>").replace("[/b]",
                                                                                       "</b>") + ", " + timeLabel.text.replace(
                "[b]", "<b>").replace("[/b]", "</b>"))

        return html

    @cherrypy.expose
    @cherrypy.tools.json_in()
    def save(self):
        log(LOG_LEVEL_STATE, CHILD_DEVICE_WEBSERVER, MSG_SUBTYPE_TEXT,
            "Set schedule received from: " + cherrypy.request.remote.ip)
        schedule = cherrypy.request.json

        with scheduleLock:
            file = open("thermostat_schedule.json", "w")

            file.write(json.dumps(schedule, indent=4))

            file.close()

        reloadSchedule()

        file = open("web/html/thermostat_saved.html", "r")

        html = file.read()

        file.close()

        with thermostatLock:
            html = html.replace("@@version@@", str(THERMOSTAT_VERSION))
            html = html.replace("@@dt@@", dateLabel.text.replace("[b]", "<b>").replace("[/b]",
                                                                                       "</b>") + ", " + timeLabel.text.replace(
                "[b]", "<b>").replace("[/b]", "</b>"))

        return html


def startWebServer():
    host = "discover" if not (settings.exists("web")) else settings.get("web")["host"]
    cherrypy.server.socket_host = host if host != "discover" else get_ip_address()  # use machine IP address if host
    # = "discover"
    cherrypy.server.socket_port = 80 if not (settings.exists("web")) else settings.get("web")["port"]

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

    cherrypy.quickstart(WebInterface(), '/', conf)


class SensorService(threading.Thread):
    def __init__(self):
        super(SensorService, self).__init__()
        self.daemon = True
        self.mac_name = self.get_mac_name()
        self.BROKER = '10.1.1.109'  # IP-Adresse des MQTT-Brokers
        self.PORT = 1883  # Port des MQTT-Brokers
        # MQTT-Topics festlegen
        self.TOPIC_REPORT = f'command/DaikinWZ/control'

    def get_mac_name(self):
        mac_address = ':'.join(
            ['{:02x}'.format((uuid.getnode() >> elements) & 0xff) for elements in range(0, 2 * 6, 2)][::-1]).upper()
        return mac_address.replace(":", "").upper()

    def run(self):

        # MQTT Callbacks
        def on_connect(client, userdata, flags, rc):
            print(f"Connected with result code {rc}")

        def on_disconnect(client, userdata, rc):
            if rc != 0:
                print("Unexpected disconnection. Reconnecting in 60 seconds...")
                time.sleep(60)
                client.reconnect()  # Erneut verbinden

        client_id = f"Env-{self.mac_name}"
        client = mqtt.Client(client_id)
        client.on_connect = on_connect
        client.on_disconnect = on_disconnect

        while True:
            try:
                client.connect(self.BROKER, self.PORT, 60)
                client.loop_start()

                while True:
                    # OneWire-Sensor
                    sensor = W1ThermSensor()
                    temperature = sensor.get_temperature()

                    # Daten für info/BLE-Env/{mac_name}/report zusammenstellen
                    data_report = {
                        'env': round(temperature, 1),
                        'target': [21.500, 24.000]
                    }

                    data_string = json.dumps(data_report, separators=(',', ':'))
                    client.publish(self.TOPIC_REPORT, str(data_string))

                    # Schlafen für 5 Sekunden
                    time.sleep(5)
            except Exception as e:
                print(f"Fehler: {e}")
                time.sleep(60)  # Warte 60 Sekunden und versuche es erneut


##############################################################################
#                                                                            #
#       Main                                                                 #
#                                                                            #
##############################################################################

def main():
    # Start Web Server
    webThread = threading.Thread(target=startWebServer)
    webThread.daemon = True
    webThread.start()

    # Start Scheduler
    reloadSchedule()
    schedThread = threading.Thread(target=startScheduler)
    schedThread.daemon = True
    schedThread.start()

    # Start remote info
    #remoteThread = threading.Thread(target=check_hotwater_temp)
    #remoteThread.daemon = True
    #remoteThread.start()

    # Start SensorService
    # sensor_service = SensorService()
    # sensor_service.start()
    # sensor_service.join()  # Warten, bis der Thread beendet ist

    # Start Thermostat UI/App
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
