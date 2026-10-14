# -*- coding: utf-8 -*-
#
# Copyright (c) 2023-2026 Chris (ckvsoft) <chris@ckvsoft.at>
# SPDX-License-Identifier: MIT

"""Central access to thermostat_settings.json with built-in defaults.

Replaces the repeated "settings.exists(...) else settings.get(...)"
pattern found all over the code and keeps the defaults in one place.
"""

DEFAULTS = {
    "i18n": {"locale": "de_DE.utf8"},
    "scale": {"tempScale": "metric"},
    "thermostat": {
        "coolPin": 18,
        "heatPin": 23,
        "fanPin": 25,
        "minTemp": 15.0,
        "maxTemp": 30.0,
        "tempStep": 0.5,
        "tempHysteresis": 0.5,
        "tempCheckInterval": 3,
        "minUIEnabled": 0,
        "minUITimeout": 3,
    },
    "calibration": {
        "elevation": 0,
        "boilingMeasured": 100.0,
        "freezingMeasured": 0.0,
    },
    "pir": {
        "pirEnabled": 0,
        "pirPin": 5,
        "pirCheckInterval": 0.5,
        "pirIgnoreFrom": "00:00",
        "pirIgnoreTo": "00:00",
    },
    "logging": {"channel": "none", "level": "state"},
    "mqtt": {
        "enabled": True,
        "clientID": "thermostat1",
        "server": "127.0.0.1",
        "port": 1883,
        "pubPrefix": "thermostat",
    },
    "faikin": {"enabled": 0, "name": "GuestAC", "summer_temp": 14},
    "domestic_water": {"enabled": False, "topic": "", "key_value_pair": ""},
    "weather": {},
    "web": {"host": "discover", "port": 80},
    "hotwater_control": {},
}


class Config(object):
    """Read-only view on the settings store, falling back to DEFAULTS."""

    def __init__(self, path="thermostat_settings.json", defaults=None, store=None):
        if store is None:
            from kivy.storage.jsonstore import JsonStore
            store = JsonStore(path)
        self._store = store
        self._defaults = DEFAULTS if defaults is None else defaults

    def get(self, section, key, default=None):
        if default is None:
            default = self._defaults.get(section, {}).get(key)
        if not self._store.exists(section):
            return default
        return self._store.get(section).get(key, default)

    def section(self, name, default=None):
        if self._store.exists(name):
            return dict(self._store.get(name))
        if default is not None:
            return default
        return dict(self._defaults.get(name, {}))

    def exists(self, name):
        return self._store.exists(name)

    def value(self, name, default=None):
        """Read a non-dict entry, e.g. a plain list."""
        if self._store.exists(name):
            return self._store.get(name)
        return default
