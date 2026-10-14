# -*- coding: utf-8 -*-
#
# Copyright (c) 2026 Chris (ckvsoft) <chris@ckvsoft.at>
# SPDX-License-Identifier: MIT

"""Kivy widgets for the thermostat.

`create()` builds the widget instances; they live as module globals
(`ui.currentLabel`, `ui.heatControl`, ...) and are referenced by the
rest of the app as `ui.<name>`. Keeping the construction here leaves
`thermostat.py` with the wiring and the control logic.
"""

import json
import time
import traceback

from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Rectangle
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.slider import Slider
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.widget import Widget

controlColours = {}
_log_binary = None
_lock = None


def setControlState(control, state):
    with _lock:
        try:
            control.state = state
            if state == "normal":
                control.background_color = controlColours["normal"]
            else:
                control.background_color = controlColours[control.text.replace("[b]", "").replace("[/b]", "")]

            controlLabel = control.text.replace("[b]", "").replace("[/b]", "").lower()
            _log_binary(controlLabel, "0" if state == "normal" else "1")

        except Exception:
            traceback.print_exc()


def create(app, status_provider, min_temp, max_temp, temp_step, units, version,
           log_binary, lock):
    global controlColours, _log_binary, _lock
    global coolControl, heatControl, fanControl, holdControl
    global versionLabel, currentLabel, currentWaterLabel, currentWaterValueLabel
    global altCurLabel, altWaterLabel, altWaterValueLabel, setLabel
    global statusHeatLabel, statusCoolLabel, statusFanLabel, statusSchedLabel
    global statusHeatValueLabel, statusCoolValueLabel, statusFanValueLabel, statusSchedValueLabel
    global dateLabel, timeLabel, altTimeLabel
    global altDecisionLabel, altHeaterLabel, altHeaterValueLabel, altBatteryLabel, altBatteryValueLabel
    global altHourLabels, tempSlider
    global weatherSummaryLabel, weatherImg, weatherTempLabel, weatherTempValueLabel
    global weatherHumidityLabel, weatherHumidityValueLabel, weatherWindLabel, weatherWindValueLabel
    global weatherCloudsLabel, weatherCloudsValueLabel, weatherSunLabel, weatherSunValueLabel
    global forecastTodaySummaryLabel, forecastTodayImg, forecastTodayHighLabel, forecastTodayHighValueLabel
    global forecastTodayHumidityLabel, forecastTodayHumidityValueLabel, forecastTodayWindLabel, forecastTodayWindValueLabel
    global forecastTodayCloudsLabel, forecastTodayCloudsValueLabel, forecastTodayRainLabel, forecastTodayRainValueLabel
    global forecastTomoSummaryLabel, forecastTomoImg, forecastTomoHighLabel, forecastTomoHighValueLabel
    global forecastTomoHumidityLabel, forecastTomoHumidityValueLabel, forecastTomoWindLabel, forecastTomoWindValueLabel
    global forecastTomoCloudsLabel, forecastTomoCloudsValueLabel, forecastTomoRainLabel, forecastTomoRainValueLabel

    _log_binary = log_binary
    _lock = lock

    controlColours = {
        "normal": (1.0, 1.0, 1.0, 1.0),
        _("Cool"): (0.0, 0.0, 1.0, 0.4),
        _("Heat"): (1.0, 0.0, 0.0, 1.0),
        _("Fan"): (0.0, 1.0, 0.0, 0.4),
        _("Hold"): (0.0, 1.0, 0.0, 0.4)
    }

    status_info = json.loads(status_provider())

    coolControl = ToggleButton(text="[b]" + _("Cool") + "[/b]", markup=True, size_hint=(None, None))
    setControlState(coolControl, "down" if app.cool else "normal")

    heatControl = ToggleButton(text="[b]" + _("Heat") + "[/b]", markup=True, size_hint=(None, None))
    setControlState(heatControl, "down" if app.heat else "normal")

    fanControl = ToggleButton(text="[b]" + _("Fan") + "[/b]", markup=True, size_hint=(None, None))
    setControlState(fanControl, "down" if app.fan else "normal")

    holdControl = ToggleButton(text="[b]" + _("Hold") + "[/b]", markup=True, size_hint=(None, None))
    setControlState(holdControl, "down" if app.hold else "normal")

    versionLabel = Label(text="Thermostat v" + str(version), size_hint=(None, None), font_size='10sp', markup=True, text_size=(150, 20))
    currentLabel = Label(text="[b]" + str(app.current_temp) + units + "[/b]", size_hint=(None, None), font_size='100sp', markup=True, text_size=(300, 200))
    currentWaterLabel = Label(text="[b]" + _("Domestic water") + "[/b]:", size_hint=(None, None), font_size='25sp', markup=True, text_size=(200, 100))
    currentWaterValueLabel = Label(text=str(app.domestic_water) + units, size_hint=(None, None), font_size='25sp', markup=True, text_size=(100, 100))

    altCurLabel = Label(text=currentLabel.text, size_hint=(None, None), font_size='80sp', markup=True, text_size=(300, 120), color=(0.5, 0.5, 0.5, 0.35))
    altWaterLabel = Label(text=currentWaterLabel.text, size_hint=(None, None), font_size='26sp', markup=True, text_size=(190, 42), color=(0.45, 0.45, 0.45, 0.6))
    altWaterValueLabel = Label(text=currentWaterValueLabel.text, size_hint=(None, None), font_size='36sp', markup=True, text_size=(190, 55), color=(0.6, 0.6, 0.6, 0.55))

    setLabel = Label(text="  Set\n[b]" + str(app.set_temp) + units + "[/b]", size_hint=(None, None), font_size='25sp', markup=True, text_size=(100, 100))

    statusHeatLabel = Label(text=_("Heat") + ":", size_hint=(None, None), font_size='20sp', markup=True, text_size=(90, 20), halign='left')
    statusCoolLabel = Label(text=_("Cool") + ":", size_hint=(None, None), font_size='20sp', markup=True, text_size=(90, 20), halign='left')
    statusFanLabel = Label(text=_("Fan") + ":", size_hint=(None, None), font_size='20sp', markup=True, text_size=(90, 20), halign='left')
    statusSchedLabel = Label(text=_("Sched") + ":", size_hint=(None, None), font_size='20sp', markup=True, text_size=(90, 20), halign='left')

    statusHeatValueLabel = Label(text=status_info['heat'], size_hint=(None, None), font_size='20sp', markup=True, text_size=(70, 20), halign='left')
    statusCoolValueLabel = Label(text=status_info['cool'], size_hint=(None, None), font_size='20sp', markup=True, text_size=(70, 20), halign='left')
    statusFanValueLabel = Label(text=status_info['fan'], size_hint=(None, None), font_size='20sp', markup=True, text_size=(70, 20), halign='left')
    statusSchedValueLabel = Label(text=status_info['sched'], size_hint=(None, None), font_size='20sp', markup=True, text_size=(70, 20), halign='left')

    dateLabel = Label(text="[b]" + time.strftime("%a %d. %b %Y") + "[/b]", size_hint=(None, None), font_size='20sp', markup=True, text_size=(270, 40))

    timeStr = time.strftime("%H:%M")

    timeLabel = Label(text="[b]" + (timeStr if timeStr[0:1] != "0" else timeStr[1:]) + "[/b]", size_hint=(None, None), font_size='40sp', markup=True, text_size=(180, 75))
    altTimeLabel = Label(text=timeLabel.text, size_hint=(None, None), font_size='32sp', markup=True, text_size=(160, 55), color=(0.5, 0.5, 0.5, 0.6))

    # Hotwater / price display labels (sleep mode / minimalUI)
    altDecisionLabel = Label(text="", size_hint=(None, None), font_size='32sp', markup=True, text_size=(270, 55), halign='left', color=(0, 0, 0, 0))
    altHeaterLabel = Label(text="[b]" + _("Heater") + "[/b]:", size_hint=(None, None), font_size='26sp', markup=True, text_size=(190, 42), color=(0.45, 0.45, 0.45, 0.6))
    altHeaterValueLabel = Label(text="--", size_hint=(None, None), font_size='36sp', markup=True, text_size=(120, 55), color=(0.6, 0.6, 0.6, 0.55))
    altBatteryLabel = Label(text="[b]Akku[/b]:", size_hint=(None, None), font_size='26sp', markup=True, text_size=(130, 42), color=(0.45, 0.45, 0.45, 0.6))
    altBatteryValueLabel = Label(text="--", size_hint=(None, None), font_size='30sp', markup=True, text_size=(200, 55), color=(0.6, 0.6, 0.6, 0.55))
    altHourLabels = []

    tempSlider = Slider(orientation='vertical', min=min_temp, max=max_temp, step=temp_step, value=app.set_temp, size_hint=(None, None))

    weatherSummaryLabel = Label(text="", size_hint=(None, None), font_size='20sp', markup=True, text_size=(200, 20))
    weatherImg = Image(source="web/images/na.png", size_hint=(None, None))
    weatherTempLabel = Label(text=_("Temp") + ":", size_hint=(None, None), font_size='20sp', markup=True, text_size=(240, 20), valign="top", halign='left')
    weatherTempValueLabel = Label(text="N/A", size_hint=(None, None), font_size='20sp', markup=True, text_size=(160, 20), valign="top", halign='left')
    weatherHumidityLabel = Label(text=_("Humidity") + ":", size_hint=(None, None), font_size='20sp', markup=True, text_size=(240, 20), valign="top", halign='left')
    weatherHumidityValueLabel = Label(text="N/A", size_hint=(None, None), font_size='20sp', markup=True, text_size=(160, 20), valign="top", halign='left')
    weatherWindLabel = Label(text=_("Wind") + ":", size_hint=(None, None), font_size='20sp', markup=True, text_size=(240, 20), valign="top", halign='left')
    weatherWindValueLabel = Label(text="N/A", size_hint=(None, None), font_size='20sp', markup=True, text_size=(160, 20), valign="top", halign='left')
    weatherCloudsLabel = Label(text=_("Clouds") + ":", size_hint=(None, None), font_size='20sp', markup=True, text_size=(240, 20), valign="top", halign='left')
    weatherCloudsValueLabel = Label(text="N/A", size_hint=(None, None), font_size='20sp', markup=True, text_size=(160, 20), valign="top", halign='left')
    weatherSunLabel = Label(text=_("Sun") + ":", size_hint=(None, None), font_size='20sp', markup=True, text_size=(240, 20), valign="top", halign='left')
    weatherSunValueLabel = Label(text="N/A", size_hint=(None, None), font_size='20sp', markup=True, text_size=(160, 20), valign="top", halign='left')

    forecastTodaySummaryLabel = Label(text="", size_hint=(None, None), font_size='15sp', markup=True, text_size=(100, 15))
    forecastTodayImg = Image(source="web/images/na.png", size_hint=(None, None))
    forecastTodayHighLabel = Label(text=_("High") + ":", size_hint=(None, None), font_size='15sp', markup=True, text_size=(100, 16), valign="top", halign='left')
    forecastTodayHighValueLabel = Label(text="N/A", size_hint=(None, None), font_size='15sp', markup=True, text_size=(160, 16), valign="top", halign='left')
    forecastTodayHumidityLabel = Label(text=_("Humidity") + ":", size_hint=(None, None), font_size='15sp', markup=True, text_size=(100, 16), valign="top", halign='left')
    forecastTodayHumidityValueLabel = Label(text="N/A", size_hint=(None, None), font_size='15sp', markup=True, text_size=(160, 16), valign="top", halign='left')
    forecastTodayWindLabel = Label(text=_("Wind") + ":", size_hint=(None, None), font_size='15sp', markup=True, text_size=(100, 16), valign="top", halign='left')
    forecastTodayWindValueLabel = Label(text="N/A", size_hint=(None, None), font_size='15sp', markup=True, text_size=(160, 16), valign="top", halign='left')
    forecastTodayCloudsLabel = Label(text=_("Clouds") + ":", size_hint=(None, None), font_size='15sp', markup=True, text_size=(100, 16), valign="top", halign='left')
    forecastTodayCloudsValueLabel = Label(text="N/A", size_hint=(None, None), font_size='15sp', markup=True, text_size=(160, 16), valign="top", halign='left')
    forecastTodayRainLabel = Label(text="", size_hint=(None, None), font_size='15sp', markup=True, text_size=(100, 16), valign="top", halign='left')
    forecastTodayRainValueLabel = Label(text="", size_hint=(None, None), font_size='15sp', markup=True, text_size=(160, 16), valign="top", halign='left')

    forecastTomoSummaryLabel = Label(text="", size_hint=(None, None), font_size='15sp', markup=True, text_size=(100, 15))
    forecastTomoImg = Image(source="web/images/na.png", size_hint=(None, None))
    forecastTomoHighLabel = Label(text=_("High") + ":", size_hint=(None, None), font_size='15sp', markup=True, text_size=(100, 16), valign="top", halign='left')
    forecastTomoHighValueLabel = Label(text="N/A", size_hint=(None, None), font_size='15sp', markup=True, text_size=(160, 16), valign="top", halign='left')
    forecastTomoHumidityLabel = Label(text=_("Humidity") + ":", size_hint=(None, None), font_size='15sp', markup=True, text_size=(100, 16), valign="top", halign='left')
    forecastTomoHumidityValueLabel = Label(text="N/A", size_hint=(None, None), font_size='15sp', markup=True, text_size=(160, 16), valign="top", halign='left')
    forecastTomoWindLabel = Label(text=_("Wind") + ":", size_hint=(None, None), font_size='15sp', markup=True, text_size=(100, 16), valign="top", halign='left')
    forecastTomoWindValueLabel = Label(text="N/A", size_hint=(None, None), font_size='15sp', markup=True, text_size=(160, 16), valign="top", halign='left')
    forecastTomoCloudsLabel = Label(text=_("Clouds") + ":", size_hint=(None, None), font_size='15sp', markup=True, text_size=(100, 16), valign="top", halign='left')
    forecastTomoCloudsValueLabel = Label(text="N/A", size_hint=(None, None), font_size='15sp', markup=True, text_size=(160, 16), valign="top", halign='left')
    forecastTomoRainLabel = Label(text="", size_hint=(None, None), font_size='15sp', markup=True, text_size=(100, 16), valign="top", halign='left')
    forecastTomoRainValueLabel = Label(text="", size_hint=(None, None), font_size='15sp', markup=True, text_size=(160, 16), valign="top", halign='left')


class PriceBarsWidget(Widget):
    """Horizontal colored timeline strip for the sleep screen.

    24 segments for today's hours: green = cheap block & SEUSS charges,
    olive = cheap block but the battery skips the purchase, red =
    discharge, gray = neutral. Past hours are dimmed."""

    def update_bars(self, status):
        today = status.get("prices_today") or {}
        colors = status.get("colors_today") or {}
        cheap = bool(status.get("cheap_now", status.get("in_cheap_block")))
        self._redraw(today, colors, cheap, status)

    def _redraw(self, today, colors, cheap, status):
        self.canvas.clear()
        if not today:
            return
        w, h = self.width, self.height
        strip_h = int(h * 0.5)
        strip_y = self.y + h - strip_h
        hour_w = w / 24.0
        now_hour = int(time.strftime("%H"))
        now_min = int(time.strftime("%M"))
        now_frac = now_hour + now_min / 60.0

        with self.canvas:
            for hr in range(24):
                key = str(hr)
                col = colors.get(key, "gray")
                is_past = hr < now_hour
                if col == "green":
                    Color(0.0, 0.35, 0.0, 0.4) if is_past else Color(0.0, 0.8, 0.0, 0.95)
                elif col == "olive":
                    Color(0.25, 0.25, 0.0, 0.45) if is_past else Color(0.62, 0.62, 0.05, 0.95)
                elif col == "red":
                    Color(0.4, 0.08, 0.05, 0.45) if is_past else Color(0.9, 0.15, 0.1, 0.95)
                else:
                    Color(0.2, 0.2, 0.2, 0.35) if is_past else Color(0.4, 0.4, 0.4, 0.65)
                x = self.x + hr * hour_w
                Rectangle(pos=(x, strip_y), size=(hour_w - 1, strip_h))

            now_x = self.x + now_frac * hour_w
            Color(1, 1, 1, 0.7)
            Rectangle(pos=(now_x - 1, strip_y - 5), size=(3, strip_h + 10))

            for hr in range(24):
                tl = CoreLabel(text=f"{hr:02d}", font_size=15, color=(0.55, 0.55, 0.55, 0.8))
                tl.refresh()
                num_x = self.x + hr * hour_w + (hour_w - tl.texture.width) / 2
                Rectangle(texture=tl.texture, pos=(num_x, self.y + 6), size=tl.texture.size)

        if cheap:
            altDecisionLabel.text = "[b]JA[/b] [size=18](" + "Strom günstig" + ")[/size]"
            altDecisionLabel.color = (0.0, 0.55, 0.0, 0.6)
        else:
            altDecisionLabel.text = "[b]NEIN[/b] [size=18](" + "Strom teuer" + ")[/size]"
            altDecisionLabel.color = (0.7, 0.1, 0.06, 0.6)

        self._apply_heater_state(status.get("heater_state"))

    def _apply_heater_state(self, state):
        if state == "on":
            altHeaterValueLabel.text = "[b]" + _("On") + "[/b]"
            altHeaterValueLabel.color = (0.85, 0.5, 0.08, 0.7)
        elif state == "off":
            altHeaterValueLabel.text = "[b]" + _("Off") + "[/b]"
            altHeaterValueLabel.color = (0.45, 0.45, 0.45, 0.5)
        else:
            altHeaterValueLabel.text = "--"
            altHeaterValueLabel.color = (0.45, 0.45, 0.45, 0.5)
