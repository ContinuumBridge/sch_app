#!/usr/bin/env python
# sch_app_a.py
# Copyright (C) ContinuumBridge Limited, 2014 - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Peter Claydon
#
ModuleName = "sch_app" 

import sys
import os.path
import time
import logging
from cbcommslib import CbApp
from cbconfig import *
import requests
import json
from twisted.internet import reactor
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


SEND_DELAY               = 20  # Time to gather values for a device before sending them
# Default values:
config = {
    'temperature': 'True',
    'temp_min_change': 0.2,
    'irtemperature': 'False',
    'irtemp_min_change': 0.5,
    'humidity': 'True',
    'humidity_min_change': 0.2,
    'buttons': 'False',
    'accel': 'False',
    'accel_min_change': 0.02,
    'accel_polling_interval': 3.0,
    'gyro': 'False',
    'gyro_min_change': 0.5,
    "gyro_polling_interval": 3.0,
    'magnet': 'False',
    'magnet_min_change': 1.5,
    'magnet_polling_interval': 3.0,
    'binary': 'True',
    'luminance': 'True',
    'luminance_min_change': 1.0,
    'power': 'True',
    'power_min_change': 1.0,
    'battery': 'True',
    'battery_min_change': 1.0,
    'connected': 'True',
    'slow_polling_interval': 600.0,
    'geras_key': 'undefined'
}

class DataManager:
    """ Managers data storage for all sensors """
    def __init__(self, bridge_id):
        self.baseurl = "http://geras.1248.io/series/" + bridge_id + "/"
        self.s={}
        self.waiting=[]

    def sendValuesThread(self, values, deviceID):
        url = self.baseurl + deviceID
        status = 0
        logging.debug("%s sendValues, device: %s length: %s", ModuleName, deviceID, str(len(values)))
        headers = {'Content-Type': 'application/json'}
        try:
            r = requests.post(url, auth=(config["geras_key"], ''), data=json.dumps({"e": values}), headers=headers)
            status = r.status_code
            success = True
        except Exception as inst:
            logging.warning("%s sendValues failed, type: %s, exception args: %s", ModuleName, type(inst), str(inst.args))
            success = False
        if status !=200 or not success:
            logging.debug("%s sendValues failed, status: %s", ModuleName, status)
            # On error, store the values that weren't sent ready to be sent again
            reactor.callFromThread(self.storeValues, values, deviceID)

    def sendValues(self, deviceID):
        values = self.s[deviceID]
        # Call in thread as it may take a second or two
        self.waiting.remove(deviceID)
        del self.s[deviceID]
        reactor.callInThread(self.sendValuesThread, values, deviceID)

    def storeValues(self, values, deviceID):
        if not deviceID in self.s:
            self.s[deviceID] = values
        else:
            self.s[deviceID].append(values)
        if not deviceID in self.waiting:
            reactor.callLater(SEND_DELAY, self.sendValues, deviceID)
            self.waiting.append(deviceID)

    def storeAccel(self, deviceID, timeStamp, a):
        values = [
                  {"n":"accel_x", "v":a[0], "t":timeStamp},
                  {"n":"accel_y", "v":a[1], "t":timeStamp},
                  {"n":"accel_z", "v":a[2], "t":timeStamp}
                 ]
        self.storeValues(values, deviceID)

    def storeTemp(self, deviceID, timeStamp, temp):
        values = [
                  {"n":"temperature", "v":temp, "t":timeStamp}
                 ]
        self.storeValues(values, deviceID)

    def storeIrTemp(self, deviceID, timeStamp, temp):
        values = [
                  {"n":"ir_temperature", "v":temp, "t":timeStamp}
                 ]
        self.storeValues(values, deviceID)

    def storeHumidity(self, deviceID, timeStamp, h):
        values = [
                  {"n":"humidity", "v":h, "t":timeStamp}
                 ]
        self.storeValues(values, deviceID)

    def storeButtons(self, deviceID, timeStamp, buttons):
        values = [
                  {"n":"left_button", "v":buttons["leftButton"], "t":timeStamp},
                  {"n":"right_button", "v":buttons["rightButton"], "t":timeStamp}
                 ]
        self.storeValues(values, deviceID)

    def storeGyro(self, deviceID, timeStamp, gyro):
        values = [
                  {"n":"gyro_x", "v":gyro[0], "t":timeStamp},
                  {"n":"gyro_y", "v":gyro[1], "t":timeStamp},
                  {"n":"gyro_z", "v":gyro[2], "t":timeStamp}
                 ]
        self.storeValues(values, deviceID)

    def storeMagnet(self, deviceID, timeStamp, magnet):
        values = [
                  {"n":"magnet_x", "v":magnet[0], "t":timeStamp},
                  {"n":"magnet_y", "v":magnet[1], "t":timeStamp},
                  {"n":"magnet_z", "v":magnet[2], "t":timeStamp}
                 ]
        self.storeValues(values, deviceID)

    def storeBinary(self, deviceID, timeStamp, b):
        values = [
                  {"n":"binary", "v":b, "t":timeStamp}
                 ]
        self.storeValues(values, deviceID)

    def storeLuminance(self, deviceID, timeStamp, v):
        values = [
                  {"n":"luminance", "v":v, "t":timeStamp}
                 ]
        self.storeValues(values, deviceID)

    def storePower(self, deviceID, timeStamp, v):
        values = [
                  {"n":"power", "v":v, "t":timeStamp}
                 ]
        self.storeValues(values, deviceID)

    def storeBattery(self, deviceID, timeStamp, v):
        values = [
                  {"n":"battery", "v":v, "t":timeStamp}
                 ]
        self.storeValues(values, deviceID)

    def storeConnected(self, deviceID, timeStamp, v):
        values = [
                  {"n":"connected", "v":v, "t":timeStamp}
                 ]
        self.storeValues(values, deviceID)

class Accelerometer:
    def __init__(self, id):
        self.previous = [0.0, 0.0, 0.0]
        self.id = id

    def processAccel(self, resp):
        accel = [resp["data"]["x"], resp["data"]["y"], resp["data"]["z"]]
        timeStamp = resp["timeStamp"]
        event = False
        for a in range(3):
            if abs(accel[a] - self.previous[a]) > config["accel_min_change"]:
                event = True
                break
        if event:
            self.dm.storeAccel(self.id, timeStamp, accel)
            self.previous = accel

class TemperatureMeasure():
    """ Either send temp every minute or when it changes. """
    def __init__(self, id):
        # self.mode is either regular or on_change
        self.mode = "on_change"
        self.minChange = 0.2
        self.id = id
        epochTime = time.time()
        self.prevEpochMin = int(epochTime - epochTime%60)
        self.powerTemp = 0.0

    def processTemp (self, resp):
        timeStamp = resp["timeStamp"] 
        temp = resp["data"]
        if self.mode == "regular":
            epochMin = int(timeStamp - timeStamp%60)
            if epochMin != self.prevEpochMin:
                temp = resp["data"]
                self.dm.storeTemp(self.id, self.prevEpochMin, temp) 
                self.prevEpochMin = epochMin
        else:
            if abs(temp-self.powerTemp) >= config["temp_min_change"]:
                self.dm.storeTemp(self.id, timeStamp, temp) 
                self.powerTemp = temp

class IrTemperatureMeasure():
    """ Either send temp every minute or when it changes. """
    def __init__(self, id):
        # self.mode is either regular or on_change
        self.mode = "on_change"
        self.minChange = 0.2
        self.id = id
        epochTime = time.time()
        self.prevEpochMin = int(epochTime - epochTime%60)
        self.powerTemp = 0.0

    def processIrTemp (self, resp):
        timeStamp = resp["timeStamp"] 
        temp = resp["data"]
        if self.mode == "regular":
            epochMin = int(timeStamp - timeStamp%60)
            if epochMin != self.prevEpochMin:
                temp = resp["data"]
                self.dm.storeIrTemp(self.id, self.prevEpochMin, temp) 
                self.prevEpochMin = epochMin
        else:
            if abs(temp-self.powerTemp) >= config["irtemp_min_change"]:
                self.dm.storeIrTemp(self.id, timeStamp, temp) 
                self.powerTemp = temp

class Buttons():
    def __init__(self, id):
        self.id = id

    def processButtons(self, resp):
        timeStamp = resp["timeStamp"] 
        buttons = resp["data"]
        self.dm.storeButtons(self.id, timeStamp, buttons)

class Gyro():
    def __init__(self, id):
        self.id = id
        self.previous = [0.0, 0.0, 0.0]

    def processGyro(self, resp):
        gyro = [resp["data"]["x"], resp["data"]["y"], resp["data"]["z"]]
        timeStamp = resp["timeStamp"] 
        event = False
        for a in range(3):
            if abs(gyro[a] - self.previous[a]) > config["gyro_min_change"]:
                event = True
                break
        if event:
            self.dm.storeGyro(self.id, timeStamp, gyro)
            self.previous = gyro

class Magnet():
    def __init__(self, id):
        self.id = id
        self.previous = [0.0, 0.0, 0.0]

    def processMagnet(self, resp):
        mag = [resp["data"]["x"], resp["data"]["y"], resp["data"]["z"]]
        timeStamp = resp["timeStamp"] 
        event = False
        for a in range(3):
            if abs(mag[a] - self.previous[a]) > config["magnet_min_change"]:
                event = True
                break
        if event:
            self.dm.storeMagnet(self.id, timeStamp, mag)
            self.previous = mag

class Humid():
    """ Either send temp every minute or when it changes. """
    def __init__(self, id):
        self.id = id
        self.previous = 0.0

    def processHumidity (self, resp):
        h = resp["data"]
        timeStamp = resp["timeStamp"] 
        if abs(h-self.previous) >= config["humidity_min_change"]:
            self.dm.storeHumidity(self.id, timeStamp, h) 
            self.previous = h

class Binary():
    def __init__(self, id):
        self.id = id
        self.previous = 0

    def processBinary(self, resp):
        timeStamp = resp["timeStamp"] 
        b = resp["data"]
        if b == "on":
            bi = 1
        else:
            bi = 0
        if bi != self.previous:
            self.dm.storeBinary(self.id, timeStamp-1.0, self.previous)
            self.dm.storeBinary(self.id, timeStamp, bi)
            self.previous = bi

class Luminance():
    def __init__(self, id):
        self.id = id
        self.previous = 0

    def processLuminance(self, resp):
        v = resp["data"]
        timeStamp = resp["timeStamp"] 
        if abs(v-self.previous) >= config["luminance_min_change"]:
            self.dm.storeLuminance(self.id, timeStamp, v) 
            self.previous = v

class Power():
    def __init__(self, id):
        self.id = id
        self.previous = 0
        self.previousTime = time.time()

    def processPower(self, resp):
        v = resp["data"]
        timeStamp = resp["timeStamp"] 
        if abs(v-self.previous) >= config["power_min_change"]:
            if timeStamp - self.previousTime > 2:
                self.dm.storePower(self.id, timeStamp-1.0, self.previous)
            self.dm.storePower(self.id, timeStamp, v) 
            self.previous = v
            self.previousTime = timeStamp

class Battery():
    def __init__(self, id):
        self.id = id
        self.previous = 0

    def processBattery(self, resp):
        v = resp["data"]
        timeStamp = resp["timeStamp"] 
        if abs(v-self.previous) >= config["battery_min_change"]:
            self.dm.storeBattery(self.id, timeStamp, v) 
            self.previous = v

class Connected():
    def __init__(self, id):
        self.id = id
        self.previous = 0

    def processConnected(self, resp):
        v = resp["data"]
        timeStamp = resp["timeStamp"] 
        if v:
            b = 1
        else:
            b = 0
        if b != self.previous:
            self.dm.storeConnected(self.id, timeStamp-1.0, self.previous)
            self.dm.storeConnected(self.id, timeStamp, b) 
            self.previous = b

class App(CbApp):
    def __init__(self, argv):
        logging.basicConfig(filename=CB_LOGFILE,level=CB_LOGGING_LEVEL,format='%(asctime)s %(message)s')
        self.appClass = "monitor"
        self.state = "stopped"
        self.status = "ok"
        configFile = CB_CONFIG_DIR + "sch_app.config"
        global config
        try:
            with open(configFile, 'r') as f:
                newConfig = json.load(f)
                logging.info('%s Read sch_app.config', ModuleName)
                config.update(newConfig)
        except:
            logging.warning('%s sch_app.config does not exist or file is corrupt', ModuleName)
        for c in config:
            if c.lower in ("true", "t", "1"):
                config[c] = True
            elif c.lower in ("false", "f", "0"):
                config[c] = False
        logging.debug('%s Config: %s', ModuleName, config)
        self.accel = []
        self.gyro = []
        self.magnet = []
        self.temp = []
        self.irTemp = []
        self.buttons = []
        self.humidity = []
        self.binary = []
        self.luminance = []
        self.power = []
        self.battery = []
        self.connected = []
        self.devices = []
        self.devServices = [] 
        self.idToName = {} 
        #CbApp.__init__ MUST be called
        CbApp.__init__(self, argv)

    def setState(self, action):
        if action == "clear_error":
            self.state = "running"
        else:
            self.state = action
        logging.debug("%s state: %s", ModuleName, self.state)
        msg = {"id": self.id,
               "status": "state",
               "state": self.state}
        self.sendManagerMessage(msg)

    def onConcMessage(self, resp):
        #logging.debug("%s resp from conc: %s", ModuleName, resp)
        if resp["resp"] == "config":
            msg = {
               "msg": "req",
               "verb": "post",
               "channel": int(self.id[3:]),
               "body": {
                        "msg": "services",
                        "appID": self.id,
                        "idToName": self.idToName,
                        "services": self.devServices
                       }
                  }
            self.sendMessage(msg, "conc")
        else:
            msg = {"appID": self.id,
                   "msg": "error",
                   "message": "unrecognised response from concentrator"}
            self.sendMessage(msg, "conc")

    def onAdaptorData(self, message):
        """
        This method is called in a thread by cbcommslib so it will not cause
        problems if it takes some time to complete (other than to itself).
        """
        #logging.debug("%s onadaptorData, message: %s", ModuleName, message)
        if message["characteristic"] == "acceleration":
            for a in self.accel:
                if a.id == self.idToName[message["id"]]: 
                    a.processAccel(message)
                    break
        elif message["characteristic"] == "temperature":
            for t in self.temp:
                if t.id == self.idToName[message["id"]]:
                    t.processTemp(message)
                    break
        elif message["characteristic"] == "ir_temperature":
            for t in self.irTemp:
                if t.id == self.idToName[message["id"]]:
                    t.processIrTemp(message)
                    break
        elif message["characteristic"] == "gyro":
            for g in self.gyro:
                if g.id == self.idToName[message["id"]]:
                    g.processGyro(message)
                    break
        elif message["characteristic"] == "magnetometer":
            for g in self.magnet:
                if g.id == self.idToName[message["id"]]:
                    g.processMagnet(message)
                    break
        elif message["characteristic"] == "buttons":
            for b in self.buttons:
                if b.id == self.idToName[message["id"]]:
                    b.processButtons(message)
                    break
        elif message["characteristic"] == "humidity":
            for b in self.humidity:
                if b.id == self.idToName[message["id"]]:
                    b.processHumidity(message)
                    break
        elif message["characteristic"] == "binary_sensor":
            for b in self.binary:
                if b.id == self.idToName[message["id"]]:
                    b.processBinary(message)
                    break
        elif message["characteristic"] == "power":
            for b in self.power:
                if b.id == self.idToName[message["id"]]:
                    b.processPower(message)
                    break
        elif message["characteristic"] == "battery":
            for b in self.battery:
                if b.id == self.idToName[message["id"]]:
                    b.processBattery(message)
                    break
        elif message["characteristic"] == "connected":
            for b in self.connected:
                if b.id == self.idToName[message["id"]]:
                    b.processConnected(message)
                    break
        elif message["characteristic"] == "luminance":
            for b in self.luminance:
                if b.id == self.idToName[message["id"]]:
                    b.processLuminance(message)
                    break

    def onAdaptorService(self, message):
        #logging.debug("%s onAdaptorService, message: %s", ModuleName, message)
        self.devServices.append(message)
        serviceReq = []
        for p in message["service"]:
            # Based on services offered & whether we want to enable them
            if p["characteristic"] == "temperature":
                if config["temperature"] == 'True':
                    self.temp.append(TemperatureMeasure((self.idToName[message["id"]])))
                    self.temp[-1].dm = self.dm
                    serviceReq.append({"characteristic": "temperature",
                                       "interval": config["slow_polling_interval"]})
            elif p["characteristic"] == "ir_temperature":
                if config["irtemperature"] == 'True':
                    self.irTemp.append(IrTemperatureMeasure(self.idToName[message["id"]]))
                    self.irTemp[-1].dm = self.dm
                    serviceReq.append({"characteristic": "ir_temperature",
                                       "interval": config["slow_polling_interval"]})
            elif p["characteristic"] == "acceleration":
                if config["accel"] == 'True':
                    self.accel.append(Accelerometer((self.idToName[message["id"]])))
                    serviceReq.append({"characteristic": "acceleration",
                                       "interval": config["accel_polling_interval"]})
                    self.accel[-1].dm = self.dm
            elif p["characteristic"] == "gyro":
                if config["gyro"] == 'True':
                    self.gyro.append(Gyro(self.idToName[message["id"]]))
                    self.gyro[-1].dm = self.dm
                    serviceReq.append({"characteristic": "gyro",
                                       "interval": config["gyro_polling_interval"]})
            elif p["characteristic"] == "magnetometer":
                if config["magnet"] == 'True': 
                    self.magnet.append(Magnet(self.idToName[message["id"]]))
                    self.magnet[-1].dm = self.dm
                    serviceReq.append({"characteristic": "magnetometer",
                                       "interval": config["magnet_polling_interval"]})
            elif p["characteristic"] == "buttons":
                if config["buttons"] == 'True':
                    self.buttons.append(Buttons(self.idToName[message["id"]]))
                    self.buttons[-1].dm = self.dm
                    serviceReq.append({"characteristic": "buttons",
                                       "interval": 0})
            elif p["characteristic"] == "humidity":
                if config["humidity"] == 'True':
                    self.humidity.append(Humid(self.idToName[message["id"]]))
                    self.humidity[-1].dm = self.dm
                    serviceReq.append({"characteristic": "humidity",
                                       "interval": config["slow_polling_interval"]})
            elif p["characteristic"] == "binary_sensor":
                if config["binary"] == 'True':
                    self.binary.append(Binary(self.idToName[message["id"]]))
                    self.binary[-1].dm = self.dm
                    serviceReq.append({"characteristic": "binary_sensor",
                                       "interval": 0})
            elif p["characteristic"] == "power":
                if config["power"] == 'True':
                    self.power.append(Power(self.idToName[message["id"]]))
                    self.power[-1].dm = self.dm
                    serviceReq.append({"characteristic": "power",
                                       "interval": 0})
            elif p["characteristic"] == "battery":
                if config["battery"] == 'True':
                    self.battery.append(Battery(self.idToName[message["id"]]))
                    self.battery[-1].dm = self.dm
                    serviceReq.append({"characteristic": "battery",
                                       "interval": 0})
            elif p["characteristic"] == "connected":
                if config["connected"] == 'True':
                    self.connected.append(Connected(self.idToName[message["id"]]))
                    self.connected[-1].dm = self.dm
                    serviceReq.append({"characteristic": "connected",
                                       "interval": 0})
            elif p["characteristic"] == "luminance":
                if config["luminance"] == 'True':
                    self.luminance.append(Luminance(self.idToName[message["id"]]))
                    self.luminance[-1].dm = self.dm
                    serviceReq.append({"characteristic": "luminance",
                                       "interval": 0})
        msg = {"id": self.id,
               "request": "service",
               "service": serviceReq}
        self.sendMessage(msg, message["id"])
        self.setState("running")

    def onConfigureMessage(self, config):
        """ Config is based on what sensors are available """
        for adaptor in config["adaptors"]:
            adtID = adaptor["id"]
            if adtID not in self.devices:
                # Because configure may be re-called if devices are added
                name = adaptor["name"]
                friendly_name = adaptor["friendly_name"]
                logging.debug("%s Configure app. Adaptor name: %s", ModuleName, name)
                self.idToName[adtID] = friendly_name.replace(" ", "_")
                self.devices.append(adtID)
        self.dm = DataManager(self.bridge_id)
        self.setState("starting")

if __name__ == '__main__':
    App(sys.argv)
