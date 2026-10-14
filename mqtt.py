# -*- coding: utf-8 -*-
#
# Copyright (c) 2023-2026 Chris (ckvsoft) <chris@ckvsoft.at>
# SPDX-License-Identifier: MIT

"""MQTT transport: connect, (re)subscribe and publish.

Command topics are registered as handlers by the caller; this module
only owns the paho client and the topic names.
"""

import os
import time

try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False


class MqttService(object):
    def __init__(self, enabled, client_id, server, port, pub_prefix, log):
        self.enabled = bool(enabled) and MQTT_AVAILABLE
        self.client_id = client_id
        self.server = server
        self.port = port
        self.pub_prefix = pub_prefix
        self._log = log
        self.client = None
        self._handlers = []
        self._reconnect = False

    def command_topic(self, what):
        return self.pub_prefix + "/" + self.client_id + "/command/" + what

    def state_topic(self, what):
        return self.pub_prefix + "/" + self.client_id + "/state/" + what

    def log_topic(self, level_str, child_device, msg_type, msg_subtype):
        return (self.pub_prefix + "/sensor/log/" + level_str + "/" + self.client_id +
                "/" + child_device + "/" + msg_type + "/" + msg_subtype)

    def add_handler(self, topic, callback):
        self._handlers.append((topic, callback))

    def publish(self, topic, payload):
        if self.client is not None:
            self.client.publish(topic, payload)

    def start(self):
        if not self.enabled:
            return

        # paho-mqtt v2 requires CallbackAPIVersion; v1 does not know the argument
        try:
            self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                                      client_id=self.client_id, protocol=mqtt.MQTTv5)
        except (AttributeError, TypeError):
            self.client = mqtt.Client(client_id=self.client_id, protocol=mqtt.MQTTv5)

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        for topic, callback in self._handlers:
            self.client.message_callback_add(topic, lambda c, u, m, cb=callback: cb(m))

        # Make sure we can reach the broker (max 30s wait)
        ping = "ping -c 1 -W 1 " + self.server + " > /dev/null 2>&1"
        count = 0
        while os.system(ping) != 0 and count < 30:
            count += 1
            time.sleep(1)

        try:
            self.client.connect(self.server, self.port, keepalive=60)
            self.client.loop_start()
        except Exception as e:
            self._log("error", "Initial MQTT connect failed: " + str(e))

    def stop(self):
        if self.client is not None:
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except Exception:
                pass

    def _on_connect(self, client, userdata, connect_flags, reason_code, properties):
        if reason_code == 0:
            if self._reconnect:
                self._log("state", "Reconnected to: " + self.server + ":" + str(self.port))
            else:
                self._reconnect = True
                self._log("state", "Connected to: " + self.server + ":" + str(self.port))

            src = client.subscribe([(topic, 0) for topic, _ in self._handlers])
            if src[0] == 0:
                self._log("info", "Subscribe Succeeded: " + self.server + ":" + str(self.port))
            else:
                self._log("error", "Subscribe FAILED, result code: " + str(src[0]))

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        if reason_code != 0:
            self._log("error", "Unexpected MQTT Broker disconnection: " + str(reason_code))
