# -*- coding: utf-8 -*-

"""CherryPy web interface for the thermostat.

All dependencies are injected, so this module touches neither Kivy
widgets nor global thermostat state directly.
"""

import json
import time

import cherrypy


class WebInterface(object):
    _template_cache = {}

    def __init__(self, app, status_provider, set_setpoint, set_controls,
                 reload_schedule, version, min_temp, max_temp, temp_step,
                 units, thermostat_lock, schedule_lock, log_info, log_state):
        self.app = app
        self._status_provider = status_provider
        self._set_setpoint = set_setpoint
        self._set_controls = set_controls
        self._reload_schedule = reload_schedule
        self.version = version
        self.min_temp = min_temp
        self.max_temp = max_temp
        self.temp_step = temp_step
        self.units = units
        self._thermostat_lock = thermostat_lock
        self._schedule_lock = schedule_lock
        self._log_info = log_info
        self._log_state = log_state

    @classmethod
    def _load_template(cls, path):
        if path not in cls._template_cache:
            with open(path, "r") as f:
                cls._template_cache[path] = f.read()
        return cls._template_cache[path]

    @staticmethod
    def _kivy_to_html(text):
        """Convert Kivy markup tags to HTML."""
        return (text.replace("[b]", "<b>")
                    .replace("[/b]", "</b>")
                    .replace("\n", "<br>")
                    .replace(" ", "&nbsp;")
                    .replace("[color=00ff00]", '<font color="green">')
                    .replace("[/color]", '</font>'))

    def _datetime(self):
        date_str = "[b]" + time.strftime("%a %d. %b %Y") + "[/b]"
        t = time.strftime("%H:%M")
        time_str = ("[b]" + (t if t[0:1] != "0" else t[1:]) + "[/b]").lower()
        return self._kivy_to_html(date_str) + ", " + self._kivy_to_html(time_str)

    def _render(self, template, replacements):
        html = self._load_template(template)
        for key, val in replacements.items():
            html = html.replace(key, val)
        return html

    @cherrypy.expose
    def index(self):
        self._log_info("text", "Served thermostat.html to: " + cherrypy.request.remote.ip)

        with self._thermostat_lock:
            status_info = json.loads(self._status_provider())
            replacements = {
                "@@version@@": str(self.version),
                "@@temp@@": str(self.app.set_temp),
                "@@temperaturlabel@@": str(_("Temperature")),
                "@@current@@": str(self.app.current_temp) + self.units,
                "@@domesticwaterlabel@@": self._kivy_to_html("[b]" + _("Domestic water") + "[/b]:"),
                "@@domesticwater@@": str(self.app.domestic_water) + self.units,
                "@@minTemp@@": str(self.min_temp),
                "@@maxTemp@@": str(self.max_temp),
                "@@tempStep@@": str(self.temp_step),
                "@@heatlabel@@": _("Heat"),
                "@@coollabel@@": _("Cool"),
                "@@fanlabel@@": _("Fan"),
                "@@schedlabel@@": _("Sched"),
                "@@holdlabel@@": _("Hold"),
                "@@applysettings@@": _("Apply settings"),
                "@@editschedule@@": _("Edit schedule"),
                "@@heat@@": self._kivy_to_html(str(status_info['heat'])),
                "@@cool@@": self._kivy_to_html(str(status_info['cool'])),
                "@@fan@@": self._kivy_to_html(str(status_info['fan'])),
                "@@sched@@": self._kivy_to_html(str(status_info['sched'])),
                "@@dt@@": self._datetime(),
                "@@heatChecked@@": "checked" if self.app.heat else "",
                "@@coolChecked@@": "checked" if self.app.cool else "",
                "@@fanChecked@@": "checked" if self.app.fan else "",
                "@@holdChecked@@": "checked" if self.app.hold else "",
            }

        return self._render("web/html/thermostat.html", replacements)

    @cherrypy.expose
    def set(self, temp, heat="off", cool="off", fan="off", hold="off"):
        self._log_info("text", "Set thermostat received from: " + cherrypy.request.remote.ip)

        try:
            new_temp = float(temp)
        except (TypeError, ValueError):
            raise cherrypy.HTTPError(400, "Invalid temperature value")
        if not (self.min_temp <= new_temp <= self.max_temp):
            raise cherrypy.HTTPError(400,
                f"Temperature out of range ({self.min_temp}\u2013{self.max_temp})")

        with self._thermostat_lock:
            temp_changed = self.app.set_temp != new_temp
            self._set_setpoint(new_temp)
            if temp_changed:
                self._log_state("temperature", str(new_temp))
            self._set_controls(heat == "on", cool == "on", fan == "on", hold == "on")
            self._reload_schedule()

            def highlight(val, active):
                return ('<font color="red"><b>' + str(val) + '</b></font>') if active else str(val)

            replacements = {
                "@@version@@": str(self.version),
                "@@dt@@": self._datetime(),
                "@@temp@@": highlight(self.app.set_temp, temp_changed),
                "@@heat@@": highlight(heat, heat == "on"),
                "@@cool@@": highlight(cool, cool == "on"),
                "@@fan@@":  highlight(fan,  fan  == "on"),
                "@@hold@@": highlight(hold, hold == "on"),
            }

        return self._render("web/html/thermostat_set.html", replacements)

    @cherrypy.expose
    def schedule(self):
        self._log_info("text", "Served thermostat_schedule.html to: " + cherrypy.request.remote.ip)

        with self._thermostat_lock:
            replacements = {
                "@@version@@": str(self.version),
                "@@minTemp@@": str(self.min_temp),
                "@@maxTemp@@": str(self.max_temp),
                "@@tempStep@@": str(self.temp_step),
                "@@dt@@": self._datetime(),
            }

        return self._render("web/html/thermostat_schedule.html", replacements)

    @cherrypy.expose
    @cherrypy.tools.json_in()
    def save(self):
        self._log_state("text", "Set schedule received from: " + cherrypy.request.remote.ip)
        sched_data = cherrypy.request.json

        with self._schedule_lock:
            with open("thermostat_schedule.json", "w") as f:
                f.write(json.dumps(sched_data, indent=4))

        self._reload_schedule()

        with self._thermostat_lock:
            replacements = {
                "@@version@@": str(self.version),
                "@@dt@@": self._datetime(),
            }

        return self._render("web/html/thermostat_saved.html", replacements)
