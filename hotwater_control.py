#  -*- coding: utf-8 -*-
#
#  HotWaterControl - controls a Shelly smart plug that feeds a water
#  heater (Warmwasser-Heizstab) based on SEUSS spot-market price data
#  and the domestic water temperature.
#
#  thermostat2 polls SEUSS /api/prices over HTTP and, together with the
#  current water temperature (received on MQTT topic Heizung/Cmd by the
#  main thermostat module), decides whether the heater plug should be
#  on or off.
#
#  Control logic (temperature hysteresis):
#
#      water >= target_temp            -> OFF  (warm enough)
#      water <  min_temp               -> ON   (too cold, price irrelevant)
#      in_cheap_block AND water < target_temp - hysteresis -> ON
#      otherwise                       -> OFF
#
#  Fail-safe: when SEUSS is unreachable the cheap-price flag falls back
#  to "not cheap", so the heater only switches on when the water is
#  actually cold -> hot water stays guaranteed.

import json
import threading
import time
import urllib.request


class HotWaterControl:
    def __init__(self, settings=None):
        settings = settings or {}
        self.enabled = int(settings.get("enabled", 0))
        self.seuss_url = str(settings.get("seuss_url", "http://localhost:5000")).rstrip("/")
        self.poll_interval = int(settings.get("poll_interval_seconds", 300))
        self.target_temp = float(settings.get("target_temp", 55.0))
        self.min_temp = float(settings.get("min_temp", 42.0))
        self.hysteresis = float(settings.get("hysteresis", 1.5))
        self.shelly_ip = str(settings.get("shelly_ip", ""))
        self.shelly_relay = int(settings.get("shelly_relay", 0))
        self.min_on_seconds = float(settings.get("min_on_seconds", 600))
        self.min_off_seconds = float(settings.get("min_off_seconds", 60))
        self.http_timeout = float(settings.get("http_timeout", 8))

        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

        # Latest price snapshot from SEUSS
        self.current_price = None
        self.in_cheap_block = False
        self.avg_today = None
        self.avg_tomorrow = None
        self.prices_today = {}
        self.prices_tomorrow = {}
        self.hard_cap = None
        self.market = None
        self.timestamp = None
        self.seuss_reachable = False
        self.last_error = None

        # Heater relay state
        self.heater_state = "off"
        self.last_state_change = 0.0
        self.last_decision = None

        # Optional callback receiving get_status() dict (UI update)
        self.ui_callback = None

    # ------------------------------------------------------------------ lifecycle

    def start(self):
        if not self.enabled or self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._poll_loop, daemon=True, name="hotwater-poll"
        )
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    # ------------------------------------------------------------------ polling

    def _poll_loop(self):
        while not self._stop.is_set():
            try:
                self.poll()
            except Exception as e:
                self._set_offline(f"poll error: {e}")
            self._stop.wait(self.poll_interval)

    def poll(self):
        """Fetch the price snapshot from SEUSS /api/prices."""
        url = f"{self.seuss_url}/api/prices"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.http_timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            self._set_offline(f"{type(e).__name__}: {e}")
            return

        with self._lock:
            self.current_price = data.get("current_price")
            self.in_cheap_block = bool(data.get("in_cheap_block", False))
            self.avg_today = data.get("avg_today")
            self.avg_tomorrow = data.get("avg_tomorrow")
            self.prices_today = data.get("prices_today", {}) or {}
            self.prices_tomorrow = data.get("prices_tomorrow", {}) or {}
            self.hard_cap = data.get("hard_cap")
            self.market = data.get("market")
            self.timestamp = data.get("timestamp")
            self.seuss_reachable = True
            self.last_error = None

        self._notify_ui()

    def _set_offline(self, reason):
        with self._lock:
            self.seuss_reachable = False
            self.last_error = reason
            # Conservative fallback: without fresh price data we must NOT
            # claim cheap power -- the heater then only runs when the
            # water is actually cold (below min_temp).
            self.in_cheap_block = False
        self._notify_ui()

    # ------------------------------------------------------------------ heater

    def update_water_temp(self, water_temp):
        """
        Feed the current domestic water temperature into the control
        logic. water_temp may be numeric or "n/a" (stale MQTT feed);
        non-numeric values leave the relay state untouched so we never
        flip the heater on uncertain readings. Returns the relay state.
        """
        if not self.enabled:
            return self.heater_state

        try:
            temp = float(water_temp)
        except (TypeError, ValueError):
            return self.heater_state

        with self._lock:
            cheap = self.in_cheap_block

        decision, reason = self._decide(temp, cheap)
        return self._apply(decision, reason)

    def _decide(self, temp, cheap):
        """Pure decision function -> ('on' | 'off', reason string)."""
        if temp >= self.target_temp:
            return "off", "water reached target temp"
        if temp < self.min_temp:
            return "on", "water below min temp"
        if cheap and temp < self.target_temp - self.hysteresis:
            return "on", "in cheap block, water below target"
        return "off", "not in cheap block, water still ok"

    def _apply(self, decision, reason):
        now = time.time()
        # Minimum on/off guards protect the heating element from
        # short-cycling relay chatter.
        if decision == self.heater_state:
            return self.heater_state
        if decision == "on" and (now - self.last_state_change) < self.min_off_seconds:
            return self.heater_state
        if decision == "off" and (now - self.last_state_change) < self.min_on_seconds:
            return self.heater_state

        self.last_state_change = now
        self.heater_state = decision
        self.last_decision = reason
        # Run the (potentially slow, up to http_timeout seconds) Shelly
        # HTTP call on a worker thread so we never block the Kivy UI
        # thread that usually calls update_water_temp().
        t = threading.Thread(
            target=self._switch_shelly, args=(decision,),
            daemon=True, name="shelly-switch",
        )
        t.start()
        self._notify_ui()
        return self.heater_state

    def _switch_shelly(self, action):
        if not self.shelly_ip:
            self._set_error("no shelly_ip configured")
            return
        url = f"http://{self.shelly_ip}/relay/{self.shelly_relay}?turn={action}"
        try:
            urllib.request.urlopen(url, timeout=self.http_timeout).read()
            self._set_error(None)
        except Exception as e:
            self._set_error(f"shelly {action} failed: {e}")

    def _set_error(self, err):
        with self._lock:
            self.last_error = err

    # ------------------------------------------------------------------ UI

    def set_ui_callback(self, callback):
        self.ui_callback = callback
        self._notify_ui()

    def _notify_ui(self):
        if self.ui_callback is None:
            return
        try:
            self.ui_callback(self.get_status())
        except Exception:
            pass

    def get_status(self):
        with self._lock:
            return {
                "enabled": self.enabled,
                "seuss_reachable": self.seuss_reachable,
                "last_error": self.last_error,
                "current_price": self.current_price,
                "in_cheap_block": self.in_cheap_block,
                "avg_today": self.avg_today,
                "avg_tomorrow": self.avg_tomorrow,
                "prices_today": self.prices_today,
                "prices_tomorrow": self.prices_tomorrow,
                "hard_cap": self.hard_cap,
                "market": self.market,
                "timestamp": self.timestamp,
                "target_temp": self.target_temp,
                "min_temp": self.min_temp,
                "hysteresis": self.hysteresis,
                "heater_state": self.heater_state,
                "last_decision": self.last_decision,
            }