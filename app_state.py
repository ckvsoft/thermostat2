# -*- coding: utf-8 -*-

"""Mutable runtime state shared by thermostat, UI, scheduler and web."""


class AppState(object):
    def __init__(self, current_temp=22.0, set_temp=22.0, domestic_water="n/a",
                 heat=False, cool=False, fan=False, hold=False):
        self.current_temp = current_temp
        self.set_temp = set_temp
        self.domestic_water = domestic_water
        self.heat = heat
        self.cool = cool
        self.fan = fan
        self.hold = hold

    def snapshot(self):
        """Plain dict for the FaikinController."""
        return {
            "currentTemp": self.current_temp,
            "heat": self.heat,
            "cool": self.cool,
            "target": self.set_temp,
        }
