# -*- coding: utf-8 -*-
#
# Copyright (c) 2023-2026 Chris (ckvsoft) <chris@ckvsoft.at>
# SPDX-License-Identifier: MIT

"""Kivy app shell: builds the thermostat layout and wires the widgets
to the controller/handlers. `ui.py` provides the widgets themselves."""

import subprocess

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen, ScreenManager, NoTransition

from handlers import MinimalScreen

Window.show_cursor = False


class ThermostatApp(App):
    def __init__(self, ui, controller, handlers, weather_view, hotwater, cfg,
                 min_ui_enabled, pir_enabled, pir_check_interval, temp_check_interval):
        super().__init__()
        self.ui = ui
        self.controller = controller
        self.handlers = handlers
        self.weather_view = weather_view
        self.hotwater = hotwater
        self.cfg = cfg
        self.min_ui_enabled = min_ui_enabled
        self.pir_enabled = pir_enabled
        self.pir_check_interval = pir_check_interval
        self.temp_check_interval = temp_check_interval

    def build(self):
        ui = self.ui
        controller = self.controller
        handlers = self.handlers

        thermostatUI = FloatLayout(size=(800, 480))

        with thermostatUI.canvas.before:
            Color(0.0, 0.0, 0.0, 1)
            self.rect = Rectangle(size=(800, 480), pos=thermostatUI.pos)

        wimg = Image(source='web/images/logo.png')

        def show_reboot_dialog(instance, touch):
            if not instance.collide_point(*touch.pos):
                return
            content = BoxLayout(orientation='vertical', padding=10, spacing=10)
            content.add_widget(Label(text="[b]Thermostat jetzt neu starten?[/b]",
                                     font_size='22sp', markup=True))
            btns = BoxLayout(orientation='horizontal',
                             size_hint=(1, None), height=60, spacing=10)
            btn_ok = Button(text="Reboot", size_hint=(1, 1))
            btn_cancel = Button(text="Abbrechen", size_hint=(1, 1))
            btns.add_widget(btn_ok)
            btns.add_widget(btn_cancel)
            content.add_widget(btns)
            popup = Popup(title="Thermostat", content=content,
                          size_hint=(0.6, 0.4), auto_dismiss=True)

            def do_reboot(btn):
                popup.dismiss()
                subprocess.Popen(["/sbin/reboot"])

            btn_ok.bind(on_press=do_reboot)
            btn_cancel.bind(on_press=lambda b: popup.dismiss())
            popup.open()

        wimg.bind(on_touch_down=show_reboot_dialog)

        ui.coolControl.bind(on_press=controller.control_callback)
        ui.heatControl.bind(on_press=controller.control_callback)
        ui.fanControl.bind(on_press=controller.control_callback)
        ui.holdControl.bind(on_press=controller.control_callback)

        ui.tempSlider.bind(on_touch_down=controller.update_set_temp, on_touch_move=controller.update_set_temp)

        wimg.size = (80, 80)
        wimg.size_hint = (None, None)
        wimg.pos = (10, 380)

        ui.heatControl.size = (80, 80)
        ui.heatControl.pos = (680, 380)

        ui.coolControl.size = (80, 80)
        ui.coolControl.pos = (680, 270)

        ui.fanControl.size = (80, 80)
        ui.fanControl.pos = (680, 160)

        ui.statusHeatLabel.pos = (635, 80)
        ui.statusCoolLabel.pos = (635, 60)
        ui.statusFanLabel.pos = (635, 40)
        ui.statusSchedLabel.pos = (635, 20)
        ui.statusHeatValueLabel.pos = (710, 80)
        ui.statusCoolValueLabel.pos = (710, 60)
        ui.statusFanValueLabel.pos = (710, 40)
        ui.statusSchedValueLabel.pos = (710, 20)

        ui.tempSlider.size = (100, 360)
        ui.tempSlider.pos = (570, 20)

        ui.holdControl.size = (80, 80)
        ui.holdControl.pos = (480, 380)

        ui.setLabel.pos = (590, 390)

        ui.currentLabel.pos = (390, 300)
        ui.currentWaterLabel.pos = (340, 235)
        ui.currentWaterValueLabel.pos = (450, 235)

        ui.dateLabel.pos = (180, 370)
        ui.timeLabel.pos = (345, 380)

        ui.weatherImg.pos = (265, 160)
        ui.weatherSummaryLabel.pos = (430, 160)
        ui.weatherTempLabel.pos = (365, 135)
        ui.weatherTempValueLabel.pos = (450, 135)
        ui.weatherHumidityLabel.pos = (365, 110)
        ui.weatherHumidityValueLabel.pos = (450, 110)
        ui.weatherWindLabel.pos = (365, 85)
        ui.weatherWindValueLabel.pos = (450, 85)
        ui.weatherCloudsLabel.pos = (365, 60)
        ui.weatherCloudsValueLabel.pos = (450, 60)
        ui.weatherSunLabel.pos = (365, 35)
        ui.weatherSunValueLabel.pos = (450, 35)

        ui.versionLabel.pos = (320, 0)

        forecastTodayHeading = Label(text="[b]"+ _("Today") + "[/b]:", font_size='20sp', markup=True, size_hint=(None, None),
                                     pos=(0, 300))

        ui.forecastTodayImg.pos = (0, 275)
        ui.forecastTodaySummaryLabel.pos = (100, 275)
        ui.forecastTodayHighLabel.pos = (30, 248)
        ui.forecastTodayHighValueLabel.pos = (150, 248)
        ui.forecastTodayHumidityLabel.pos = (30, 231)
        ui.forecastTodayHumidityValueLabel.pos = (150, 231)
        ui.forecastTodayWindLabel.pos = (30, 214)
        ui.forecastTodayWindValueLabel.pos = (150, 214)
        ui.forecastTodayCloudsLabel.pos = (30, 197)
        ui.forecastTodayCloudsValueLabel.pos = (150, 197)
        ui.forecastTodayRainLabel.pos = (30, 180)
        ui.forecastTodayRainValueLabel.pos = (150, 180)

        forecastTomoHeading = Label(text="[b]" + _("Tomorrow") + "[/b]:", font_size='20sp', markup=True, size_hint=(None, None),
                                    pos=(0, 130))
        ui.forecastTomoImg.pos = (0, 100)
        ui.forecastTomoSummaryLabel.pos = (100, 100)
        ui.forecastTomoHighLabel.pos = (30, 73)
        ui.forecastTomoHighValueLabel.pos = (150, 73)
        ui.forecastTomoHumidityLabel.pos = (30, 57)
        ui.forecastTomoHumidityValueLabel.pos = (150, 57)
        ui.forecastTomoWindLabel.pos = (30, 41)
        ui.forecastTomoWindValueLabel.pos = (150, 41)
        ui.forecastTomoCloudsLabel.pos = (30, 25)
        ui.forecastTomoCloudsValueLabel.pos = (150, 25)
        ui.forecastTomoRainLabel.pos = (30, 9)
        ui.forecastTomoRainValueLabel.pos = (150, 9)

        thermostatUI.add_widget(wimg)
        thermostatUI.add_widget(ui.coolControl)
        thermostatUI.add_widget(ui.heatControl)
        thermostatUI.add_widget(ui.fanControl)
        thermostatUI.add_widget(ui.holdControl)
        thermostatUI.add_widget(ui.tempSlider)
        thermostatUI.add_widget(ui.currentLabel)
        thermostatUI.add_widget(ui.currentWaterLabel)
        thermostatUI.add_widget(ui.currentWaterValueLabel)
        thermostatUI.add_widget(ui.setLabel)
        thermostatUI.add_widget(ui.statusHeatLabel)
        thermostatUI.add_widget(ui.statusCoolLabel)
        thermostatUI.add_widget(ui.statusFanLabel)
        thermostatUI.add_widget(ui.statusSchedLabel)
        thermostatUI.add_widget(ui.statusHeatValueLabel)
        thermostatUI.add_widget(ui.statusCoolValueLabel)
        thermostatUI.add_widget(ui.statusFanValueLabel)
        thermostatUI.add_widget(ui.statusSchedValueLabel)

        thermostatUI.add_widget(ui.dateLabel)
        thermostatUI.add_widget(ui.timeLabel)
        thermostatUI.add_widget(ui.weatherImg)
        thermostatUI.add_widget(ui.weatherSummaryLabel)
        thermostatUI.add_widget(ui.weatherTempLabel)
        thermostatUI.add_widget(ui.weatherTempValueLabel)
        thermostatUI.add_widget(ui.weatherHumidityLabel)
        thermostatUI.add_widget(ui.weatherHumidityValueLabel)
        thermostatUI.add_widget(ui.weatherWindLabel)
        thermostatUI.add_widget(ui.weatherWindValueLabel)
        thermostatUI.add_widget(ui.weatherCloudsLabel)
        thermostatUI.add_widget(ui.weatherCloudsValueLabel)
        thermostatUI.add_widget(ui.weatherSunLabel)
        thermostatUI.add_widget(ui.weatherSunValueLabel)

        thermostatUI.add_widget(ui.versionLabel)
        thermostatUI.add_widget(forecastTodayHeading)
        thermostatUI.add_widget(ui.forecastTodayImg)
        thermostatUI.add_widget(ui.forecastTodaySummaryLabel)
        thermostatUI.add_widget(ui.forecastTodayHighLabel)
        thermostatUI.add_widget(ui.forecastTodayHighValueLabel)
        thermostatUI.add_widget(ui.forecastTodayHumidityLabel)
        thermostatUI.add_widget(ui.forecastTodayHumidityValueLabel)
        thermostatUI.add_widget(ui.forecastTodayWindLabel)
        thermostatUI.add_widget(ui.forecastTodayWindValueLabel)
        thermostatUI.add_widget(ui.forecastTodayCloudsLabel)
        thermostatUI.add_widget(ui.forecastTodayCloudsValueLabel)
        thermostatUI.add_widget(ui.forecastTodayRainLabel)
        thermostatUI.add_widget(ui.forecastTodayRainValueLabel)

        thermostatUI.add_widget(forecastTomoHeading)
        thermostatUI.add_widget(ui.forecastTomoImg)
        thermostatUI.add_widget(ui.forecastTomoSummaryLabel)
        thermostatUI.add_widget(ui.forecastTomoHighLabel)
        thermostatUI.add_widget(ui.forecastTomoHighValueLabel)
        thermostatUI.add_widget(ui.forecastTomoHumidityLabel)
        thermostatUI.add_widget(ui.forecastTomoHumidityValueLabel)
        thermostatUI.add_widget(ui.forecastTomoWindLabel)
        thermostatUI.add_widget(ui.forecastTomoWindValueLabel)
        thermostatUI.add_widget(ui.forecastTomoCloudsLabel)
        thermostatUI.add_widget(ui.forecastTomoCloudsValueLabel)
        thermostatUI.add_widget(ui.forecastTomoRainLabel)
        thermostatUI.add_widget(ui.forecastTomoRainValueLabel)

        layout = thermostatUI

        if self.min_ui_enabled:
            uiScreen = Screen(name="thermostatUI")
            uiScreen.add_widget(thermostatUI)

            minScreen = MinimalScreen(name="minimalUI")
            minScreen.handlers = handlers
            minUI = FloatLayout(size=(800, 480))

            with minUI.canvas.before:
                Color(0.0, 0.0, 0.0, 1)
                self.rect = Rectangle(size=(800, 480), pos=minUI.pos)

            ui.altCurLabel.pos = (390, 275)
            ui.altTimeLabel.pos = (45, 398)
            ui.altDecisionLabel.pos = (575, 398)
            ui.altWaterLabel.pos = (55, 165)
            ui.altWaterValueLabel.pos = (240, 163)
            ui.altHeaterLabel.pos = (430, 165)
            ui.altHeaterValueLabel.pos = (575, 163)

            battery_pos = list(self.cfg.value("battery_line_pos", [35, 225]))
            ui.altBatteryLabel.pos = (battery_pos[0], battery_pos[1])
            ui.altBatteryValueLabel.pos = (battery_pos[0] + 130, battery_pos[1] - 3)

            priceBarsWidget = ui.PriceBarsWidget(size=(800, 140), size_hint=(None, None), pos=(0, 0))

            minUI.add_widget(ui.altCurLabel)
            minUI.add_widget(ui.altTimeLabel)
            minUI.add_widget(ui.altWaterLabel)
            minUI.add_widget(ui.altWaterValueLabel)
            minUI.add_widget(ui.altHeaterLabel)
            minUI.add_widget(ui.altHeaterValueLabel)
            minUI.add_widget(ui.altBatteryLabel)
            minUI.add_widget(ui.altBatteryValueLabel)
            minUI.add_widget(ui.altDecisionLabel)
            minUI.add_widget(priceBarsWidget)
            minScreen.add_widget(minUI)

            screenMgr = ScreenManager(
                transition=NoTransition())  # FadeTransition seems to have OpenGL bugs in Kivy Dev 1.9.1 and is unstable, so sticking with no transition for now
            screenMgr.add_widget(uiScreen)
            screenMgr.add_widget(minScreen)

            handlers.screen_mgr = screenMgr
            handlers.price_bars = priceBarsWidget

            layout = screenMgr

            handlers.schedule_minimal_ui()

            if self.pir_enabled:
                Clock.schedule_interval(handlers.check_pir, self.pir_check_interval)

        Clock.schedule_interval(controller.check_sensor_temp, self.temp_check_interval)

        if self.hotwater is not None and self.hotwater.enabled:
            self.hotwater.set_ui_callback(handlers.update_hotwater_ui)
            self.hotwater.start()

        self.weather_view.start()

        return layout
