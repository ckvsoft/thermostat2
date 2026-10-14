# -*- coding: utf-8 -*-
#
# Copyright (c) 2026 Chris (ckvsoft) <chris@ckvsoft.at>
# SPDX-License-Identifier: MIT

"""Log channels for the thermostat: none, print, file or MQTT.

The MQTT channel only needs a publish callable and a topic builder, so
the logging code stays decoupled from the transport.
"""

import datetime
import os

MSG_TYPE_SET = "set"

LOG_FILE_NAME = "thermostat.log"
LOG_ALWAYS_TIMESTAMP = True

LOG_LEVEL_DEBUG = 1
LOG_LEVEL_INFO = 2
LOG_LEVEL_ERROR = 3
LOG_LEVEL_STATE = 4
LOG_LEVEL_NONE = 5

LOG_LEVELS = {
    "debug": LOG_LEVEL_DEBUG,
    "info": LOG_LEVEL_INFO,
    "state": LOG_LEVEL_STATE,
    "error": LOG_LEVEL_ERROR
}

LOG_LEVELS_STR = {v: k for k, v in LOG_LEVELS.items()}


class Logger(object):
    def __init__(self, channel, level_name, publish=None, log_topic=None,
                 log_file_name=LOG_FILE_NAME):
        self.channel = channel
        self._publish = publish
        self._log_topic = log_topic
        self.file = None
        self.level = LOG_LEVELS.get(level_name, LOG_LEVEL_NONE)

        if channel == "file":
            self.file = open(log_file_name, "a")

    @staticmethod
    def _ts():
        return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z ")

    def set_level(self, name):
        if name in LOG_LEVELS:
            self.level = LOG_LEVELS[name]
            return True
        return False

    def log(self, level, child_device, msg_subtype, msg, msg_type=MSG_TYPE_SET,
            timestamp=True, single=False):
        if level < self.level:
            return

        label = LOG_LEVELS_STR.get(level, str(level))

        if self.channel == "print":
            ts = self._ts() if (LOG_ALWAYS_TIMESTAMP or timestamp) else ""
            print(ts + label + "/" + child_device + "/" + msg_type + "/" + msg_subtype + ": " + msg)

        elif self.channel == "file" and self.file is not None:
            self.file.write(self._ts() + label + "/" + child_device + "/" +
                            msg_type + "/" + msg_subtype + ": " + msg + "\n")

        elif self.channel == "mqtt" and self._publish is not None:
            ts = self._ts() if (LOG_ALWAYS_TIMESTAMP or timestamp) else ""
            topic = self._log_topic(label, child_device, msg_type, msg_subtype)
            self._publish(topic, ts + msg)

    def close(self):
        if self.file is not None:
            try:
                self.file.flush()
                os.fsync(self.file.fileno())
                self.file.close()
            except Exception:
                pass
            self.file = None
