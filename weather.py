# -*- coding: utf-8 -*-

"""OpenWeatherMap helpers (URL building, fetching, formatting)."""

import json
import urllib.request

URL_BASE = "http://api.openweathermap.org/data/2.5/"
DIRECTIONS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW", "N"]


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
