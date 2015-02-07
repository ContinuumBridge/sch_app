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
from cbcommslib import CbApp
from cbconfig import *
import requests
import json
from twisted.internet import reactor
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# For entry/exit
IN_PIR_TO_DOOR_TIME               = 30   
DOOR_CLOSE_TO_IN_PIR_TIME         = 10
DOOR_OPEN_TO_IN_PIR_TIME          = 15
MAX_DOOR_OPEN_TIME                = 60

SEND_DELAY               = 20  # Time to gather values for a device before sending them
# Default values:
config = {
    "temperature": "True",
    "temp_min_change": 0.2,
    "irtemperature": "False",
    "irtemp_min_change": 0.5,
    "humidity": "True",
    "humidity_min_change": 0.2,
    "buttons": "False",
    "accel": "False",
    "accel_min_change": 0.02,
    "accel_polling_interval": 3.0,
    "gyro": "False",
    "gyro_min_change": 0.5,
    "gyro_polling_interval": 3.0,
    "magnet": "False",
    "magnet_min_change": 1.5,
    "magnet_polling_interval": 3.0,
    "binary": "True",
    "luminance": "True",
    "luminance_min_change": 1.0,
    "power": "True",
    "power_min_change": 1.0,
    "battery": "True",
    "battery_min_change": 1.0,
    "connected": "True",
    "slow_polling_interval": 600.0,
    "night_wandering": "False",
    "night_start": "00:30",
    "night_end": "07:00",
    "night_sensors": [],
    "night_ignore_time": 600,
    "cid": "none",
    "client_test": "False",
    "geras_key": "undefined"
}

def betweenTimes(t, t1, t2):
    # True if epoch t is between times of day t1 and t2 (in 24-hour clock format: "23:10")
    t1secs = (60*int(t1.split(":")[0]) + int(t1.split(":")[1])) * 60
    t2secs = (60*int(t2.split(":")[0]) + int(t2.split(":")[1])) * 60
    stamp = time.strftime("%Y %b %d %H:%M", time.localtime(t)).split()
    today = stamp
    today[3] = "00:00"
    today_e = time.mktime(time.strptime(" ".join(today), "%Y %b %d %H:%M"))
    yesterday_e = today_e - 24*3600
    #print "today_e: ", today_e, "yesterday_e: ", yesterday_e
    tt1 = [yesterday_e + t1secs, today_e + t1secs]
    tt2 = [yesterday_e + t2secs, today_e + t2secs]
    #print "tt1: ", tt1, " tt2: ", tt2
    smallest = 50000
    decision = False
    if t - tt1[0] < smallest and t - tt1[0] > 0:
        smallest = t - tt1[0]
        decision = True
    if t - tt2[0] < smallest and t -tt2[0] > 0:
        smallest = t - tt2[0]
        decision = False
    if t - tt1[1] < smallest and t -tt1[1] > 0:
        smallest = t - tt1[1]
        decision = True
    if t - tt2[1] < smallest and t - tt2[1] > 0:
        smallest = t - tt2[1]
        decision = False
    return decision

class DataManager:
    """ Managers data storage for all sensors """
    def __init__(self, bridge_id):
        self.baseurl = "http://geras.1248.io/series/" + bridge_id + "/"
        self.daurl = "http://geras.1248.io/series/" + "DA" + bridge_id[3:] + "/"
        self.s={}
        self.waiting=[]

    def sendValuesThread(self, values, deviceID, da):
        if da:
            url = self.daurl + deviceID
        else:
            url = self.baseurl + deviceID
        status = 0
        headers = {'Content-Type': 'application/json'}
        try:
            r = requests.post(url, auth=(config["geras_key"], ''), data=json.dumps({"e": values}), headers=headers)
            status = r.status_code
            success = True
        except Exception as inst:
            self.cbLog("warning", "sendValues failed: " + str(type(inst)) + " " + str(inst.args))
            success = False
        if status !=200 or not success:
            self.cbLog("debug", "sendValues failed, status: " + str(status))
            # On error, store the values that weren't sent ready to be sent again
            reactor.callFromThread(self.storeValues, values, deviceID)

    def sendValues(self, deviceID, da):
        values = self.s[deviceID]
        # Call in thread as it may take a second or two
        self.waiting.remove(deviceID)
        del self.s[deviceID]
        reactor.callInThread(self.sendValuesThread, values, deviceID, da)

    def storeValues(self, values, deviceID, da=False):
        if not deviceID in self.s:
            self.s[deviceID] = values
        else:
            self.s[deviceID].append(values)
        if not deviceID in self.waiting:
            reactor.callLater(SEND_DELAY, self.sendValues, deviceID, da)
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

    def storeEntryExit(self, location, timeStamp, action, v):
        values = [
                  {"n":action, "v":v, "t":timeStamp}
                 ]
        self.storeValues(values, location, True)

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
        if abs(self.previous) >= config["humidity_min_change"]:
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

class Client():
    def __init__(self, aid):
        self.aid = aid
        self.count = 0
        self.messages = []

    def send(self, message):
        message["body"]["n"] = self.count
        self.count += 1
        self.messages.append(message)
        self.sendMessage(message, "conc")

    def receive(self, message):
        self.cbLog("debug", "Message from client: " + str(message))
        if "body" in message:
            if "n" in message["body"]:
                self.cbLog("debug", "Received ack from client: " + str(message["body"]["n"]))
                for m in self.messages:
                    if m["body"]["n"] == m:
                        self.messages.remove(m)
                        self.cbLog("debug", "Removed message " + str(m) + " from queue")
        else:
            self.cbLog("warning", "Received message from client with no body")

class pillbox():
    def __init__(self):
        self.magnet_av = [0.0, 0.0, 0.0]

    def updateMagnet(self, mag):
        self.current = mag

    def calcAverage(self):
        points_to_average = 16

class NightWander():
    def __init__(self, aid):
        global config
        self.aid = aid
        self.lastActive = 0
        if config["client_test"] == 'True':
            reactor.callLater(30, self.clientTest)

    def clientTest(self):
        self.cbLog("debug", "clientTest")
        msg = {
               "source": self.aid,
               "destination": config["cid"],
               "body": {"m": "alarm",
                        "s": "Test",
                        "t": time.time()
                       }
              }
        self.client.send(msg)
        reactor.callLater(20, self.clientTest)

    def setNames(self, idToName):
        self.idToName = idToName
        if config["night_wandering"]:
            if config["night_sensors"] == []:
                for d in idToName:
                    config["night_sensors"].append(d)
            else:
                for n in config["night_sensors"]:
                    found = False
                    for d in idToName:
                        self.cbLog("debug", "NightWander. Matching n: " + n + " with d: " + d + " , idToName[d]: " + idToName[d])
                        if n == idToName[d]:
                            loc = config["night_sensors"].index(n) 
                            config["night_sensors"][loc] = d
                            found = True
                            break
                    if not found:
                        self.cbLog("info", "NightWander. Sensor name does not exist: " + n)
            self.cbLog("debug", "NightWander. night sensors: " + str(config["night_sensors"]))

    def onChange(self, devID, timeStamp, value):
        self.cbLog("debug", "Night Wander onChange, devID: " + devID + " value: " + value)
        if value == "on":
            alarm = betweenTimes(timeStamp, config["night_start"], config["night_end"])
            if alarm:
                if timeStamp - self.lastActive > config["night_ignore_time"]:
                    self.cbLog("debug", "Night Wander: " + str(alarm) + ": " + str(time.asctime(time.localtime(timeStamp))))
                    msg = {
                           "source": self.aid,
                           "destination": config["cid"],
                           "body": {"m": "alarm",
                                    "s": self.idToName[devID],
                                    "t": timeStamp
                                   }
                          }
                    self.client.send(msg)
                self.lastActive = timeStamp

class EntryExit():
    def __init__(self):
        self.inside_triggered = False
        self.inside_pir_on = False
        self.door_open = False
        self.action = "nothing"
        self.locations = []
        self.checkExit = {}

    def initExits(self, idToName):
        self.idToName = idToName
        splits = {}
        for d in idToName:
            splits[d] = idToName[d].split(" ")
            if len(splits[d]) == 1:
                splits[d] = idToName[d].split("-")
        for d in splits:
            self.cbLog("debug", "initExits, device: " + d + " name: " + str(splits[d]))
            self.cbLog("debug", "initExits, magsw test: " + splits[d][0][:5].lower())
            if splits[d][0][:5].lower() == "magsw":
                location = splits[d][2].lower()
                self.cbLog("debug", "initExits, location: " + location)
                for d2 in splits:
                    self.cbLog("debug", "initExits, d2: " + str(d2))
                    if splits[d2][0][:3].lower() == "pir" and splits[d2][1].lower() == "inside":
                        self.cbLog("debug", "initExits, pir: " + str(splits[d2]))
                        if splits[d2][2].lower() == location:
                            loc = {"location": splits[d][2],
                                   "magsw": d,
                                   "ipir": d2}
                            self.locations.append(loc)
                            break
        self.cbLog("debug", "initExits, locations: " + str(self.locations))
        devs = []
        for l in self.locations:
            self.checkExit[l["location"]] = CheckExit(l["location"])
            self.checkExit[l["location"]].cbLog = self.cbLog
            self.checkExit[l["location"]].dm = self.dm
            devs.append(l["magsw"])
            devs.append(l["ipir"])
        return devs

    def onChange(self, devID, timeStamp, value):
        for l in self.locations:
            if devID == l["magsw"]:
                self.checkExit[l["location"]].onChange("magsw", timeStamp, value)
            elif devID == l["ipir"]:
                self.checkExit[l["location"]].onChange("ipir", timeStamp, value)

class CheckExit():
    def __init__(self, location):
        self.location = location
        self.inside_pir_on_time = 0
        self.inside_pir_off_time = 0
        self.inside_pir_on = False
        self.door_open = False
        self.door_open_time = 0
        self.door_close_time = 0
        self.state = "idle"
        reactor.callLater(10, self.fsm)

    def onChange(self, sensor, timeStamp, value):
        self.cbLog("debug", "CheckExit, onChange. loc: " + self.location + " sensor: " + sensor)
        if sensor == "ipir":
            if value == "on":
                self.inside_pir_on_time = timeStamp
                self.inside_pir_on = True
            else:
                self.inside_pir_off_time = timeStamp
                self.inside_pir_on = False
        if sensor == "magsw":
            if value == "on":
                self.door_open = True
                self.door_open_time = timeStamp
            else:
                self.door_open = False
                self.door_close_time = timeStamp
              
    def fsm(self):
        # This method is called every second
        prev_state = self.state
        action = "none"
        if self.state == "idle":
            if self.door_open:
                if self.door_open_time - self.inside_pir_on_time < IN_PIR_TO_DOOR_TIME or self.inside_pir_on:
                    self.state = "check_going_out"
                else:
                    self.state = "check_coming_in"
        elif self.state == "check_going_out":
            if not self.door_open:
                self.state = "check_went_out"
        elif self.state == "check_went_out":
            t = time.time()
            if t - self.door_close_time > DOOR_CLOSE_TO_IN_PIR_TIME:
                if self.inside_pir_on or t - self.inside_pir_off_time < DOOR_CLOSE_TO_IN_PIR_TIME - 4:
                    action = "answered_door"
                    self.state = "idle"
                else:
                    action = "went_out"
                    self.state = "idle"
        elif self.state == "check_coming_in":
            if self.inside_pir_on:
                action = "came_in"
                self.state = "wait_door_close"
            elif time.time() - self.door_open_time > DOOR_OPEN_TO_IN_PIR_TIME:
                action = "open_and_close"
                self.state = "wait_door_close"
        elif self.state == "wait_door_close":
            if not self.door_open:
                self.state = "idle"
            elif time.time() - self.door_open_time > MAX_DOOR_OPEN_TIME:
                action = "door_open_too_long"
                self.state = "wait_long_door_open"
        elif self.state == "wait_door_close":
            if not self.door_open:
                self.state = "idle"
        else:
            self.cbLog("warning", "self.door algorithm imposssible self.state")
            self.state = "idle"
        if self.state != prev_state:
            self.cbLog("debug", "checkExits, new state: " + self.state)
        if action != "none":
            self.cbLog("debug", "checkExits, action: " + action) 
            self.dm.storeEntryExit(self.location, self.door_open_time, action, 0)
            self.dm.storeEntryExit(self.location, self.door_open_time + 1, action, 1)
            self.dm.storeEntryExit(self.location, self.door_open_time + 2, action, 0)
        reactor.callLater(1, self.fsm)

class App(CbApp):
    def __init__(self, argv):
        self.appClass = "monitor"
        self.state = "stopped"
        self.status = "ok"
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
        self.entryExitIDs = []
        #CbApp.__init__ MUST be called
        CbApp.__init__(self, argv)

    def setState(self, action):
        if action == "clear_error":
            self.state = "running"
        else:
            self.state = action
        msg = {"id": self.id,
               "status": "state",
               "state": self.state}
        self.sendManagerMessage(msg)

    def onConcMessage(self, message):
        self.client.receive(message)

    def onAdaptorData(self, message):
        """
        This method is called in a thread by cbcommslib so it will not cause
        problems if it takes some time to complete (other than to itself).
        """
        #self.cbLog("debug", "onadaptorData, message: " + str(message))
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
            for n in self.entryExitIDs:
                if n == message["id"]:
                    self.entryExit.onChange(message["id"], message["timeStamp"], message["data"])
            for n in config["night_sensors"]:
                if n == message["id"]:
                    self.nightWander.onChange(message["id"], message["timeStamp"], message["data"])
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
        #self.cbLog("debug", "onAdaptorService, message: " + str(message))
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

    def onConfigureMessage(self, managerConfig):
        global config
        configFile = CB_CONFIG_DIR + "sch_app.config"
        try:
            with open(configFile, 'r') as f:
                newConfig = json.load(f)
                self.cbLog("debug", "Read sch_app.config")
                config.update(newConfig)
        except Exception as ex:
            self.cbLog("warning", "sch_app.config does not exist or file is corrupt")
            self.cbLog("warning", "Exception: " + str(type(ex)) + str(ex.args))
        for c in config:
            if c.lower in ("true", "t", "1"):
                config[c] = True
            elif c.lower in ("false", "f", "0"):
                config[c] = False
        self.cbLog("debug", "Config: " + str(config))
        idToName2 = {}
        for adaptor in managerConfig["adaptors"]:
            adtID = adaptor["id"]
            if adtID not in self.devices:
                # Because managerConfigure may be re-called if devices are added
                name = adaptor["name"]
                friendly_name = adaptor["friendly_name"]
                self.cbLog("debug", "managerConfigure app. Adaptor id: " +  adtID + " name: " + name + " friendly_name: " + friendly_name)
                idToName2[adtID] = friendly_name
                self.idToName[adtID] = friendly_name.replace(" ", "_")
                self.devices.append(adtID)
        self.dm = DataManager(self.bridge_id)
        self.dm.cbLog = self.cbLog
        self.client = Client(self.bridge_id)
        self.client.sendMessage = self.sendMessage
        self.client.cbLog = self.cbLog
        self.entryExit = EntryExit()
        self.entryExit.cbLog = self.cbLog
        self.entryExit.dm = self.dm
        self.entryExitIDs = self.entryExit.initExits(idToName2)
        self.cbLog("debug", "onConfigureMessage, entryExitIDs: " + str(self.entryExitIDs))
        self.nightWander = NightWander(self.id)
        self.nightWander.cbLog = self.cbLog
        self.nightWander.client = self.client
        self.nightWander.setNames(idToName2)
        self.setState("starting")

if __name__ == '__main__':
    App(sys.argv)
