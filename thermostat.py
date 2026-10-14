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
import os
import os.path
import gettext
# from gettext import gettext as _
import threading

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

try:
    from hotwater_control import HotWaterControl
    hotwater_module_available = True
except ImportError:
    HotWaterControl = None
    hotwater_module_available = False

import kivy

##############################################################################
#                                                                            #
#       Kivy UI Imports                                                      #
#                                                                            #
##############################################################################

kivy.require('2.3.0')  # keep in sync with requirements.txt

from kivy.storage.jsonstore import JsonStore

##############################################################################
#                                                                            #
#       Other Imports                                                        #
#                                                                            #
##############################################################################

import cherrypy
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



##############################################################################
#                                                                            #
#       MySensor.org Controller compatible translated constants              #
#                                                                            #
##############################################################################

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

THERMOSTAT_VERSION = "2.4.0"


debug = False
useTestSchedule = False
FAIKIN_CONTROL_HEARTBEAT = 60  # seconds between repeated control commands


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

# Hot water (immersion heater on Shelly smart plug) control via SEUSS price data
hotwater_settings = cfg.section("hotwater_control")
hotwater_control = HotWaterControl(hotwater_settings) if hotwater_module_available else None

faikinEnabled = cfg.get("faikin", "enabled")
faikinName = cfg.get("faikin", "name")

def _mqtt_log(level, msg):
    lvl = {"state": LOG_LEVEL_STATE, "error": LOG_LEVEL_ERROR}.get(level, LOG_LEVEL_INFO)
    log(lvl, CHILD_DEVICE_MQTT, MSG_SUBTYPE_TEXT, msg)


mqtt = MqttService(
    enabled=cfg.get("mqtt", "enabled"),
    client_id=cfg.get("mqtt", "clientID"),
    server=cfg.get("mqtt", "server"),
    port=cfg.get("mqtt", "port"),
    pub_prefix=cfg.get("mqtt", "pubPrefix"),
    log=_mqtt_log,
)


logger = Logger(
    channel=cfg.get("logging", "channel"),
    level_name=cfg.get("logging", "level"),
    publish=mqtt.publish if mqtt.enabled else None,
    log_topic=mqtt.log_topic,
)
log = logger.log


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

_saved = state.get("state") if state.exists("state") else {}
app = AppState(
    current_temp=22.0 if tempScale == "metric" else 72.0,
    set_temp=_saved.get("setTemp", 22.0),
    heat=_saved.get("heatControl") == "down",
    cool=_saved.get("coolControl") == "down",
    fan=_saved.get("fanControl") == "down",
    hold=_saved.get("holdControl") == "down",
)

tempHysteresis = cfg.get("thermostat", "tempHysteresis")

tempCheckInterval = cfg.get("thermostat", "tempCheckInterval")

minUIEnabled = cfg.get("thermostat", "minUIEnabled")
minUITimeout = cfg.get("thermostat", "minUITimeout")
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

def _publish_faikin():
    if mqtt.enabled:
        faikin.publish_control()


def _reload_schedule():
    scheduler.reload()


controller = ThermostatController(
    app=app,
    ui=ui,
    gpio=GPIO,
    log=log,
    mqtt=mqtt,
    state_store=state,
    lock=thermostatLock,
    heat_pin=heatPin,
    cool_pin=coolPin,
    fan_pin=fanPin,
    temp_hysteresis=tempHysteresis,
    units=scaleUnits,
    sensor=tempSensor,
    sensor_unit=sensorUnits,
    calibration={
        "freezing_measured": freezingMeasured,
        "reference_range": referenceRange,
        "measured_range": measuredRange,
        "freezing_point": freezingPoint,
    },
    tolerance=TEMP_TOLERANCE,
    min_flow_temp=minFlowTemp,
    current_flow_temp=currentFlowTemp,
    use_test_schedule=useTestSchedule,
    hotwater=hotwater_control,
    publish_faikin=_publish_faikin,
    reload_schedule=_reload_schedule,
)


handlers = Handlers(
    app=app,
    ui=ui,
    gpio=GPIO,
    log=log,
    lock=thermostatLock,
    hotwater=hotwater_control,
    units=scaleUnits,
    domestic_key=domestic_key_value_pair,
    domestic_timeout=domestic_timeout_duration,
    pir_pin=pirPin,
    pir_ignore_from=pirIgnoreFrom,
    pir_ignore_to=pirIgnoreTo,
    min_ui_timeout=minUITimeout,
)


def _ui_log_binary(control_label, value):
    log(LOG_LEVEL_STATE, control_label + CHILD_DEVICE_SUFFIX_UICONTROL, MSG_SUBTYPE_BINARY_STATUS, value)


ui.create(
    app=app,
    status_provider=controller.get_status_info,
    min_temp=minTemp,
    max_temp=maxTemp,
    temp_step=tempStep,
    units=scaleUnits,
    version=THERMOSTAT_VERSION,
    log_binary=_ui_log_binary,
    lock=thermostatLock,
)

# Price bar chart (sleep mode / minimalUI) - today only




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


weather_view = WeatherView(
    ui=ui,
    log=log,
    lock=weatherLock,
    current_url=weatherURLCurrent,
    forecast_url=weatherURLForecast,
    timeout=weatherURLTimeout,
    current_interval=weatherRefreshInterval,
    forecast_interval=forecastRefreshInterval,
    exception_interval=weatherExceptionInterval,
    units=scaleUnits,
    wind_factor=windFactor,
    wind_units=windUnits,
    precip_factor=precipFactor,
    precip_round=precipRound,
    precip_units=precipUnits,
    units_system=tempScale,
)

##############################################################################
#                                                                            #
#       Thermostat Implementation                                            #
#                                                                            #
##############################################################################


##############################################################################
#                                                                            #
#       Utility Functions                                                    #
#                                                                            #
##############################################################################

commands = Commands(
    log=log,
    logger=logger,
    mqtt=mqtt,
    gpio=GPIO,
    version=THERMOSTAT_VERSION,
    script=__file__,
)
if mqtt.enabled:
    faikin = FaikinController(
        name=faikinName,
        enabled=faikinEnabled,
        summer_temp=cfg.get("faikin", "summer_temp"),
        publish=mqtt.publish,
        get_snapshot=_get_faikin_snapshot,
        state_topic=mqtt.state_topic("status"),
        heartbeat=FAIKIN_CONTROL_HEARTBEAT,
        log_debug=_faikin_log_debug,
        log_error=_faikin_log_error,
    )

    mqtt.add_handler(mqtt.command_topic("restart"), lambda message: commands.restart(message))
    mqtt.add_handler(mqtt.command_topic("loglevel"), lambda message: commands.set_log_level(message))
    mqtt.add_handler(mqtt.command_topic("version"), lambda message: commands.get_version(message))
    mqtt.add_handler(mqtt.command_topic("state"), lambda message: controller.get_status_info())
    if domestic_water_enabled:
        mqtt.add_handler(domestic_water_topic, lambda message: handlers.set_domestic_water(message))
    if faikinEnabled:
        mqtt.add_handler("state/" + faikinName + "/status",
                         lambda message: faikin.handle_status_message(message))

    mqtt.start()


##############################################################################
#                                                                            #
#       Kivy Thermostat App class                                            #
#                                                                            #
##############################################################################

##############################################################################
#                                                                            #
#       Web Server Interface                                                 #
#                                                                            #
##############################################################################

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
    apply_set_temp=controller.apply_set_temp,
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
    cherrypy.server.socket_host = host if host != "discover" else commands.get_ip_address()
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
        status_provider=controller.get_status_info,
        set_setpoint=controller.apply_set_temp,
        set_controls=controller.apply_controls,
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

    ThermostatApp(
        ui=ui,
        controller=controller,
        handlers=handlers,
        weather_view=weather_view,
        hotwater=hotwater_control,
        cfg=cfg,
        min_ui_enabled=minUIEnabled,
        pir_enabled=pirEnabled,
        pir_check_interval=pirCheckInterval,
        temp_check_interval=tempCheckInterval,
    ).run()

if __name__ == '__main__':
    try:
        main()
    finally:
        log(LOG_LEVEL_STATE, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/shutdown", "Thermostat Shutting Down...")
        GPIO.cleanup()

        logger.close()

        mqtt.stop()
