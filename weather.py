# -*- coding: utf-8 -*-
#
# Copyright (c) 2026 Chris (ckvsoft) <chris@ckvsoft.at>
# SPDX-License-Identifier: MIT

"""OpenWeatherMap helpers (URL building, fetching, formatting) and the
periodic WeatherView that renders them into the UI."""

import json
import time
import urllib.request

from kivy.clock import Clock

from logging_setup import LOG_LEVEL_INFO, LOG_LEVEL_ERROR

URL_BASE = "http://api.openweathermap.org/data/2.5/"
DIRECTIONS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW", "N"]

CHILD_DEVICE_WEATHER_CURR = "weatherCurrent"
CHILD_DEVICE_WEATHER_FCAST_TODAY = "weatherForecastToday"
MSG_SUBTYPE_TEXT = "text"


def build_urls(units, location, appkey, lang="de"):
    current = URL_BASE + "weather?units=" + units + "&id=" + location + "&APPID=" + appkey + "&lang=" + lang
    forecast = URL_BASE + "forecast/daily?units=" + units + "&id=" + location + "&APPID=" + appkey + "&lang=" + lang
    return current, forecast


def get_weather(url, timeout):
    with urllib.request.urlopen(url, None, timeout) as response:
        return json.loads(response.read())


def get_cardinal_direction(heading):
    return DIRECTIONS[int(round((heading % 360) / 45))]


def get_precip_amount(raw, factor, round_digits, units):
    precip = round(raw * factor, round_digits)
    if units == "metric":
        return str(int(precip))
    return str(precip)


class WeatherView(object):
    """Fetches current weather/forecast and renders them into the UI."""

    def __init__(self, ui, log, lock, current_url, forecast_url, timeout,
                 current_interval, forecast_interval, exception_interval,
                 units, wind_factor, wind_units,
                 precip_factor, precip_round, precip_units, units_system):
        self.ui = ui
        self._log = log
        self.lock = lock
        self.current_url = current_url
        self.forecast_url = forecast_url
        self.timeout = timeout
        self.current_interval = current_interval
        self.forecast_interval = forecast_interval
        self.exception_interval = exception_interval
        self.units = units
        self.wind_factor = wind_factor
        self.wind_units = wind_units
        self.precip_factor = precip_factor
        self.precip_round = precip_round
        self.precip_units = precip_units
        self.units_system = units_system

    def start(self):
        Clock.schedule_once(self.update_current, 5)
        Clock.schedule_once(self.update_forecast, 10)

    def update_current(self, dt):
        with self.lock:
            interval = self.current_interval
            try:
                weather = get_weather(self.current_url, self.timeout)
                ui = self.ui

                ui.weatherImg.source = "web/images/" + weather["weather"][0]["icon"] + ".png"
                ui.weatherSummaryLabel.text = "[b]" + weather["weather"][0]["description"].title() + "[/b]"
                ui.weatherTempValueLabel.text = str(int(round(weather["main"]["temp"], 0))) + self.units
                ui.weatherHumidityValueLabel.text = str(weather["main"]["humidity"]) + "%"
                ui.weatherWindValueLabel.text = str(int(round(weather["wind"]["speed"] * self.wind_factor))) + self.wind_units + " " + get_cardinal_direction(weather["wind"]["deg"])
                ui.weatherCloudsValueLabel.text = str(weather["clouds"]["all"]) + "%"
                ui.weatherSunValueLabel.text = time.strftime("%H:%M", time.localtime(weather["sys"]["sunrise"])) + ", " + time.strftime("%H:%M", time.localtime(weather["sys"]["sunset"])) + ""

                self._log(LOG_LEVEL_INFO, CHILD_DEVICE_WEATHER_CURR, MSG_SUBTYPE_TEXT, json.dumps(weather))

            except Exception as e:
                interval = self.exception_interval
                ui = self.ui

                ui.weatherImg.source = "web/images/na.png"
                ui.weatherSummaryLabel.text = "N/A"
                ui.weatherTempValueLabel.text = "N/A"
                ui.weatherHumidityValueLabel.text = "N/A"
                ui.weatherWindValueLabel.text = "N/A"
                ui.weatherCloudsValueLabel.text = "N/A"
                ui.weatherSunValueLabel.text = "N/A"

                self._log(LOG_LEVEL_ERROR, CHILD_DEVICE_WEATHER_CURR, MSG_SUBTYPE_TEXT, "Update FAILED!")
                self._log(LOG_LEVEL_ERROR, CHILD_DEVICE_WEATHER_CURR, MSG_SUBTYPE_TEXT, f"Exception {e}")

            Clock.schedule_once(self.update_current, interval)

    def update_forecast(self, dt):
        with self.lock:
            interval = self.forecast_interval
            try:
                forecast = get_weather(self.forecast_url, self.timeout)
                ui = self.ui

                today = forecast["list"][0]
                tomo = forecast["list"][1]

                ui.forecastTodayImg.source = "web/images/" + today["weather"][0]["icon"] + ".png"
                ui.forecastTodaySummaryLabel.text = "[b]" + today["weather"][0]["description"].title() + "[/b]"
                ui.forecastTodayHighValueLabel.text = str(int(round(today["temp"]["max"], 0))) + self.units + ", " + _("Low") + ": " + str(int(round(today["temp"]["min"], 0))) + self.units
                ui.forecastTodayHumidityValueLabel.text = str(today["humidity"]) + "%"
                ui.forecastTodayWindValueLabel.text = str(int(round(today["speed"] * self.wind_factor))) + self.wind_units + " " + get_cardinal_direction(today["deg"])
                ui.forecastTodayCloudsValueLabel.text = str(today["clouds"]) + "%"

                rain_value_text = ""
                if "rain" in today or "snow" in today:
                    if "rain" in today:
                        ui.forecastTodayRainLabel.text = _("Rain") + ":"
                        rain_value_text = self._precip(today["rain"])
                        if "snow" in today:
                            rain_value_text += ", " + _("Snow") + ": " + self._precip(today["snow"])
                    else:
                        ui.forecastTodayRainLabel.text = _("Snow") + ":"
                        rain_value_text = self._precip(today["snow"])

                ui.forecastTodayRainValueLabel.text = rain_value_text

                ui.forecastTomoImg.source = "web/images/" + tomo["weather"][0]["icon"] + ".png"
                ui.forecastTomoSummaryLabel.text = "[b]" + tomo["weather"][0]["description"].title() + "[/b]"
                ui.forecastTomoHighValueLabel.text = str(int(round(tomo["temp"]["max"], 0))) + self.units + ", " + _("Low") + ": " + str(int(round(tomo["temp"]["min"], 0))) + self.units
                ui.forecastTomoHumidityValueLabel.text = str(tomo["humidity"]) + "%"
                ui.forecastTomoWindValueLabel.text = str(int(round(tomo["speed"] * self.wind_factor))) + self.wind_units + " " + get_cardinal_direction(tomo["deg"])
                ui.forecastTomoCloudsValueLabel.text = str(tomo["clouds"]) + "%"

                rain_value_text = ""
                if "rain" in tomo or "snow" in tomo:
                    if "rain" in tomo:
                        ui.forecastTomoRainLabel.text = _("Rain") + ":"
                        rain_value_text = self._precip(tomo["rain"])
                        if "snow" in tomo:
                            rain_value_text += ", " + _("Snow") + ": " + self._precip(tomo["snow"])
                    else:
                        ui.forecastTomoRainLabel.text = _("Snow") + ":"
                        rain_value_text = self._precip(tomo["snow"])

                ui.forecastTomoRainValueLabel.text = rain_value_text

                self._log(LOG_LEVEL_INFO, CHILD_DEVICE_WEATHER_CURR, MSG_SUBTYPE_TEXT, json.dumps(today["weather"][0]))
                self._log(LOG_LEVEL_INFO, CHILD_DEVICE_WEATHER_CURR, MSG_SUBTYPE_TEXT, json.dumps(tomo["weather"][0]))

            except Exception as e:
                interval = self.exception_interval
                ui = self.ui

                ui.forecastTodayImg.source = "web/images/na.png"
                ui.forecastTodaySummaryLabel.text = ""
                ui.forecastTodayRainLabel.text = ""
                ui.forecastTodayRainValueLabel.text = ""
                ui.forecastTodayHighValueLabel.text = "N/A"
                ui.forecastTodayHumidityValueLabel.text = "N/A"
                ui.forecastTodayWindValueLabel.text = "N/A"
                ui.forecastTodayCloudsValueLabel.text = "N/A"

                ui.forecastTomoImg.source = "web/images/na.png"
                ui.forecastTomoSummaryLabel.text = ""
                ui.forecastTomoHighValueLabel.text = "N/A"
                ui.forecastTomoHumidityValueLabel.text = "N/A"
                ui.forecastTomoWindValueLabel.text = "N/A"
                ui.forecastTomoCloudsValueLabel.text = "N/A"
                ui.forecastTomoRainLabel.text = ""
                ui.forecastTomoRainValueLabel.text = ""

                self._log(LOG_LEVEL_ERROR, CHILD_DEVICE_WEATHER_FCAST_TODAY, MSG_SUBTYPE_TEXT, "Update FAILED!")
                self._log(LOG_LEVEL_ERROR, CHILD_DEVICE_WEATHER_FCAST_TODAY, MSG_SUBTYPE_TEXT, f"Exception {e}")

            Clock.schedule_once(self.update_forecast, interval)

    def _precip(self, raw):
        return get_precip_amount(raw, self.precip_factor, self.precip_round, self.units_system) + self.precip_units
