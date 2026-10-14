# -*- coding: utf-8 -*-

"""Peripheral MQTT/sensor handlers: domestic water, PIR/motion, the
sleep screen and the hot-water sleep-screen labels."""

import datetime
import json
import time

from kivy.clock import Clock
from kivy.uix.screenmanager import Screen

from logging_setup import LOG_LEVEL_DEBUG, LOG_LEVEL_INFO, LOG_LEVEL_ERROR

CHILD_DEVICE_MQTT = "mqtt"
CHILD_DEVICE_PIR = "motionSensor"
CHILD_DEVICE_SCREEN = "screen"

MSG_SUBTYPE_TEXT = "text"
MSG_SUBTYPE_TRIPPED = "tripped"


class Handlers(object):
    def __init__(self, app, ui, gpio, log, lock, hotwater, units,
                 domestic_key, domestic_timeout,
                 pir_pin, pir_ignore_from, pir_ignore_to,
                 min_ui_timeout):
        self.app = app
        self.ui = ui
        self.gpio = gpio
        self._log = log
        self.lock = lock
        self.hotwater = hotwater
        self.units = units
        self.domestic_key = domestic_key
        self.domestic_timeout = domestic_timeout
        self.pir_pin = pir_pin
        self.pir_ignore_from = pir_ignore_from
        self.pir_ignore_to = pir_ignore_to
        self.min_ui_timeout = min_ui_timeout
        self.screen_mgr = None
        self.price_bars = None
        self._domestic_last = time.time()
        self._min_ui_timer = None

    # -- domestic water ----------------------------------------------------
    def set_domestic_water(self, message):
        try:
            payload = message.payload
            if isinstance(payload, bytes):
                payload = payload.decode('utf-8')

            data = json.loads(payload)
            value = data.get(self.domestic_key)
            if value is not None and self.app.domestic_water != value:
                self.app.domestic_water = value
                self._show_water(value)

            self._domestic_last = time.time()
            Clock.schedule_once(self.check_domestic_water_timeout, self.domestic_timeout)

        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self._log(LOG_LEVEL_ERROR, CHILD_DEVICE_MQTT, MSG_SUBTYPE_TEXT,
                      f"Invalid domestic_water payload: {e}")
        except Exception as e:
            self._log(LOG_LEVEL_ERROR, CHILD_DEVICE_MQTT, MSG_SUBTYPE_TEXT,
                      f"set_domestic_water error: {e}")

    def check_domestic_water_timeout(self, dt):
        if time.time() - self._domestic_last > self.domestic_timeout:
            self.app.domestic_water = "n/a"
            self._show_water("n/a", with_units=False)

    def _show_water(self, value, with_units=True):
        text = "[b]" + str(value) + (self.units if with_units else "") + "[/b]"
        self.ui.currentWaterValueLabel.text = text
        self.ui.altWaterValueLabel.text = text
        self.ui.altWaterValueLabel.color = (0.6, 0.6, 0.6, 0.55)

    # -- hot water sleep-screen labels -------------------------------------
    def update_hotwater_ui(self, status):
        def _apply(dt):
            bars = self.price_bars
            if bars is not None:
                try:
                    bars.update_bars(status)
                except Exception:
                    pass
            try:
                soc = status.get("battery_soc_percent")
                state = status.get("battery_state")
                if soc is None or state is None:
                    self.ui.altBatteryValueLabel.text = "--"
                    self.ui.altBatteryValueLabel.color = (0.45, 0.45, 0.45, 0.55)
                else:
                    state_text = {"charging": "Ladung",
                                  "discharging": "Entladung"}.get(state, state)
                    self.ui.altBatteryValueLabel.text = \
                        f"[b]{soc:.0f} %[/b] [size=20]({state_text})[/size]"
                    if state == "charging":
                        self.ui.altBatteryValueLabel.color = (0.0, 0.55, 0.0, 0.85)
                    elif state == "discharging":
                        self.ui.altBatteryValueLabel.color = (0.85, 0.3, 0.1, 0.85)
                    else:
                        self.ui.altBatteryValueLabel.color = (0.6, 0.6, 0.6, 0.8)
            except Exception:
                pass

        Clock.schedule_once(_apply, 0)

    # -- PIR motion / sleep screen -----------------------------------------
    def check_pir(self, pin):
        with self.lock:
            if self.gpio.input(self.pir_pin):
                self._log(LOG_LEVEL_INFO, CHILD_DEVICE_PIR, MSG_SUBTYPE_TRIPPED, "1")
                self.schedule_minimal_ui()

                ignore = False
                now = datetime.datetime.now().time()
                if self.pir_ignore_from > self.pir_ignore_to:
                    if now >= self.pir_ignore_from or now < self.pir_ignore_to:
                        ignore = True
                else:
                    if self.pir_ignore_from <= now < self.pir_ignore_to:
                        ignore = True

                mgr = self.screen_mgr
                if mgr is not None and mgr.current == "minimalUI" and not ignore:
                    mgr.current = "thermostatUI"
                    self.log_screen("Full")
            else:
                self._log(LOG_LEVEL_DEBUG, CHILD_DEVICE_PIR, MSG_SUBTYPE_TRIPPED, "0")

    def show_minimal_ui(self, dt):
        with self.lock:
            mgr = self.screen_mgr
            if mgr is not None:
                mgr.current = "minimalUI"
            self.log_screen("Minimal")

    def schedule_minimal_ui(self):
        with self.lock:
            if self._min_ui_timer is not None:
                Clock.unschedule(self.show_minimal_ui)
            self._min_ui_timer = Clock.schedule_once(self.show_minimal_ui, self.min_ui_timeout)

    def force_hotwater_on(self):
        with self.lock:
            if self.hotwater is not None and self.hotwater.enabled:
                try:
                    self.hotwater.force_on()
                except Exception:
                    pass
        self._log(LOG_LEVEL_DEBUG, CHILD_DEVICE_SCREEN, MSG_SUBTYPE_TEXT,
                  "Long press: hotwater override")

    def log_screen(self, what):
        self._log(LOG_LEVEL_DEBUG, CHILD_DEVICE_SCREEN, MSG_SUBTYPE_TEXT, what)


class MinimalScreen(Screen):
    handlers = None

    def _long_press_triggered(self, dt):
        """Fires after 2s of holding the sleep screen without release."""
        self._lp_done = True
        self.handlers.force_hotwater_on()

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            touch.grab(self)
            self._down_time = time.time()
            self._lp_done = False
            self._lp_event = Clock.schedule_once(self._long_press_triggered, 2.0)
            return True

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            if getattr(self, "_lp_event", None) is not None:
                self._lp_event.cancel()
                self._lp_event = None
            with self.handlers.lock:
                self.handlers.schedule_minimal_ui()
                if not self._lp_done:
                    self.manager.current = "thermostatUI"
                    self.handlers.log_screen("Full")
            return True
