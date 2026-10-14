# -*- coding: utf-8 -*-

"""Faikin/Faikout (Daikin) Anlagensteuerung.

Kapselt die MQTT-Kommunikation mit einem Faikout-Modul sowie die
Uebersetzung des Thermostat-Zustands in gueltige `control`-Befehle.

Bewusst frei von Kivy/GPIO/globalen Thermostat-Variablen: alle
Abhaengigkeiten werden hereingereicht (Dependency Injection), damit
dieses Modul ohne Display/GPIO importiert und getestet werden kann.
"""

import json
import time
import traceback


class FaikinController(object):
    """Steuert eine Daikin-Anlage ueber ein Faikout/Faikin MQTT-Modul.

    Parameter
    ---------
    name : str
        Geraetename (MQTT-Hostname), z. B. "DaikinWZ".
    enabled : bool/int
        Faikin-Steuerung aktiv.
    summer_temp : float
        Ab dieser Aussentemperatur wird nicht geheizt.
    publish : callable(topic, payload)
        MQTT-Publish-Funktion.
    get_snapshot : callable() -> dict
        Liefert den aktuellen Thermostat-Zustand mit den Schluesseln
        ``currentTemp`` (float), ``heat`` (bool), ``cool`` (bool) und
        ``target`` (float, Sollwert).
    state_topic : str
        MQTT-Topic, auf dem die Thermostat-State-JSON veroeffentlicht wird.
    heartbeat : float
        Sekunden zwischen wiederholten Steuerbefehlen (0 = aus).
    log_debug, log_error : callable(msg)
        Optionale Log-Callbacks.
    """

    def __init__(self, name, enabled, summer_temp, publish, get_snapshot,
                 state_topic, heartbeat=60.0,
                 log_debug=None, log_error=None):
        self.name = name
        self.enabled = bool(enabled)
        self.summer_temp = summer_temp
        self._publish = publish
        self._get_snapshot = get_snapshot
        self.state_topic = state_topic
        self.heartbeat = heartbeat
        self._log_debug = log_debug or (lambda msg: None)
        self._log_error = log_error or (lambda msg: None)

        self.outside_temp = 0.0
        self.prev_temp = None
        self.prev_target = None
        self.prev_mode = None
        self.prev_power = None
        self.last_control_time = 0.0

    # -- Status vom Geraet -------------------------------------------------

    def handle_status_message(self, message):
        """Callback fuer ``state/<name>/status`` (Faikout-Status)."""
        try:
            payload = message.payload
            if isinstance(payload, bytes):
                payload = payload.decode('utf-8')
            data = json.loads(payload)

            # "outside" kann fehlen, None, einzelner Wert oder Liste sein
            val = data.get('outside')
            if val is None:
                return
            if isinstance(val, list):
                numeric = [v for v in val if isinstance(v, (int, float))]
                if not numeric:
                    return
                val = sum(numeric) / len(numeric)
            if isinstance(val, (int, float)):
                self.outside_temp = float(val)

        except (json.JSONDecodeError, UnicodeDecodeError, ValueError, TypeError) as e:
            self._log_error("Bad faikin payload: %s" % e)

    # -- Zustand -----------------------------------------------------------

    def _normalized_outside(self):
        val = self.outside_temp
        # Defensive: outside_temp koennte aus altem Code als Liste vorliegen
        if isinstance(val, list):
            numeric = [v for v in val if isinstance(v, (int, float))]
            val = sum(numeric) / len(numeric) if numeric else 0.0
        if not isinstance(val, (int, float)):
            val = 0.0
        return val

    def build_state(self):
        """Uebersetzt den Thermostat-Zustand in die State-JSON.

        Enthaelt bewusst KEINE Steuerattribute (power/temp) — das ist
        die reine Zustandsbeschreibung des Thermostats.
        """
        snap = self._get_snapshot()
        current_temp = snap["currentTemp"]
        heat_down = bool(snap.get("heat"))
        cool_down = bool(snap.get("cool"))
        targettemp = snap["target"]

        autop = True
        if self.summer_temp < self._normalized_outside():
            heat_state = False
            autop = False
        else:
            heat_state = heat_down

        if heat_down:
            mode = "H"
        elif cool_down:
            mode = "C"
            if not heat_state:
                autop = True
        else:
            mode = "A"
            autop = False

        rounded_temp = round(current_temp * 2) / 2
        return {
            "env": current_temp,
            "rounded": rounded_temp,
            "diff": targettemp - rounded_temp,
            "heat": heat_state,
            "mode": mode,
            "autop": autop,
            "autot": targettemp,
        }

    # -- Steuerbefehl ------------------------------------------------------

    def publish_control(self):
        """Veroeffentlicht State-JSON (eigenes Topic) und ggf. einen
        gueltigen ``control``-Befehl an die Daikin.

        Auf das control-Topic gehoert ein Steuerbefehl mit
        ``power``/``temp``/``mode``/``fan``/``demand`` — NICHT die
        State-JSON (die Faikout ignoriert sie, da ``power`` fehlt).
        """
        snap = self._get_snapshot()
        cur_temp = snap["currentTemp"]

        try:
            state_data = self.build_state()
            self._publish(self.state_topic, json.dumps(state_data))

            if not self.enabled:
                return

            targettemp = state_data["autot"]
            mode = state_data["mode"]
            power = state_data["autop"]
            rounded_temp = state_data["rounded"]

            tolerance = 0.2       # Erlaubte Temperaturschwankung
            fan_hysteresis = 0.5  # Verhindert zu schnelle Luefteraenderungen

            # Ohne gueltige aktuelle Temperatur kann keine Regelung stattfinden
            if cur_temp is None:
                return
            if self.prev_temp is None:
                self.prev_temp = cur_temp

            delta_temp = cur_temp - self.prev_temp

            # Regelung bei zu grosser Abweichung
            if (mode == "H" and targettemp + 4.0 < rounded_temp) or \
               (mode == "C" and targettemp - 4.0 > rounded_temp):
                power = False

            powerful = False
            fan = "3"      # Automatischer Modus als Standard
            demand = 70

            if mode == "H":  # Heizmodus
                temp_diff = cur_temp - targettemp
                if abs(temp_diff) <= tolerance:
                    fan, demand = "3", 70
                elif temp_diff > fan_hysteresis:
                    fan = "1" if abs(temp_diff) > 3 else "2"
                    demand = 30 if abs(temp_diff) > 3 else 50
                elif temp_diff < -fan_hysteresis:
                    fan = "5" if abs(temp_diff) > 2 else "4"
                    demand = 100 if abs(temp_diff) > 2 else 95

            elif mode == "C":  # Kuehlmodus
                temp_diff = targettemp - cur_temp
                if abs(temp_diff) <= tolerance:
                    fan, demand = "3", 70
                elif temp_diff > fan_hysteresis:
                    fan = "4" if abs(temp_diff) > 2 else "5"
                    demand = 95 if abs(temp_diff) > 2 else 100
                elif temp_diff < -fan_hysteresis:
                    fan = "1" if abs(temp_diff) > 2 else "2"
                    demand = 30 if abs(temp_diff) > 2 else 50

            # Steuerbefehl nur bei relevanter Aenderung oder als Heartbeat
            now = time.time()
            control_changed = (
                self.prev_target is None
                or self.prev_target != targettemp
                or self.prev_mode != mode
                or self.prev_power != power
            )

            if control_changed or abs(delta_temp) >= tolerance \
                    or (self.heartbeat and (now - self.last_control_time) >= self.heartbeat):
                data = {
                    "env": cur_temp,
                    "temp": targettemp,
                    "powerful": powerful,
                    "power": power,
                    "mode": mode,
                    "fan": fan,
                    "demand": demand,
                }
                self._publish("command/%s/control" % self.name, json.dumps(data))
                self.last_control_time = now
                self._log_debug("control " + json.dumps(data))

            self.prev_target = targettemp
            self.prev_mode = mode
            self.prev_power = power

        except Exception as e:
            self._log_error("%s\n%s" % (e, traceback.format_exc()))
        finally:
            # prev_temp IMMER aktualisieren, auch bei early-return oder Exception
            if cur_temp is not None:
                self.prev_temp = cur_temp
