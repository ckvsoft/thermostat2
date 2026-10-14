# -*- coding: utf-8 -*-
#
# Copyright (c) 2023-2026 Chris (ckvsoft) <chris@ckvsoft.at>
# SPDX-License-Identifier: MIT

"""MQTT/utility commands: version, log level, restart and IP lookup."""

import os
import socket
import sys

from logging_setup import LOG_LEVEL_INFO, LOG_LEVEL_STATE, LOG_LEVEL_ERROR

CHILD_DEVICE_NODE = "node"
MSG_SUBTYPE_CUSTOM = "custom"
MSG_SUBTYPE_VERSION = "sketchVersion"


class Commands(object):
    def __init__(self, log, logger, mqtt, gpio, version, script):
        self._log = log
        self.logger = logger
        self.mqtt = mqtt
        self.gpio = gpio
        self.version = version
        self.script = script

    def get_ip_address(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(10)
            try:
                s.connect(("8.8.8.8", 80))  # Google DNS server
                ip = s.getsockname()[0]
                self._log(LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/ip", ip, timestamp=False)
            except socket.error:
                ip = "127.0.0.1"
                self._log(LOG_LEVEL_ERROR, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/ip",
                          "FAILED to get ip address, returning " + ip, timestamp=False)
        return ip

    def get_version(self, message):
        payload = message.payload.decode('utf-8')

        self._log(LOG_LEVEL_STATE, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/getVersion",
                  f"Empfangene Nachricht: {payload}", single=True)
        self._log(LOG_LEVEL_STATE, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/getVersion",
                  f"Empfangszeitpunkt: {message.timestamp}", single=True)
        print(f"Empfangene Nachricht: {payload}")
        print(f"Empfangszeitpunkt: {message.timestamp}")
        self._log(LOG_LEVEL_STATE, CHILD_DEVICE_NODE, MSG_SUBTYPE_VERSION, self.version)

    def restart(self, message):
        payload = message.payload.decode('utf-8') if isinstance(message.payload, bytes) else str(message.payload)

        self._log(LOG_LEVEL_STATE, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/restart",
                  f"Thermostat restarting... ({payload})", single=True)

        try:
            self.gpio.cleanup()
        except Exception:
            pass

        self.logger.flush()
        self.mqtt.stop()

        os.execl(sys.executable, 'python', self.script, *sys.argv[1:])  # does not return

    def set_log_level(self, msg):
        payload = msg.payload
        if isinstance(payload, bytes):
            payload = payload.decode('utf-8')
        payload = payload.strip().lower()

        if self.logger.set_level(payload):
            self._log(LOG_LEVEL_STATE, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/loglevel",
                      "LogLevel set to: " + payload)
        else:
            self._log(LOG_LEVEL_ERROR, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/loglevel",
                      "Invalid LogLevel: " + payload)
