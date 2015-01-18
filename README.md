shc_app
=======

This app monitors a range of characteristics and sends them to a cloud database. Currently, this database is the Geras time-series database. It also does some processing on the characteristics in order to recognise various activities. These are:

* Door entry/exit.
* Nighttime wandering.
* Pill taking.

The app is being further developed over time. Here are the details of the current version.

For every device that is connected to the app, the following characteristics may be sent to the cloud database:

* temperature
* ir_temperature
* humidity
* acceleration (3-axis accelerometer)
* magnet (3-axis magnetometer)
* gyro (3-axis gyroscope)
* luminance
* binary_sensor
* power
* battery
* connected

Sending Parameters
-----------------

Which parameters are actually sent and what processing is performed on them before they are sent is controlled from a file called sch_app.config in the /opt/cbridge/thisbridge directory of the bridge. Here is an example of such a file:

    {
        "temperature": "True",
        "temp_min_change": 0.2,
        "irtemperature": "True",
        "irtemp_min_change": 0.5,
        "humidity": "True",
        "humidity_min_change": 0.5,
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
        "slow_polling_interval": 300.0,
        "entry_exit": "True",
        "night_wandering": "True",
        "night_start": "00:30",
        "night_end": "07:00",
        "night_sensors": ["Sensor 1", "Sensor 2"],
        "pillbox": "True",
        "pillbox_start": ["06:00", "20:00"],
        "pillbox_end": ["08:00", "23:00"],
        "pillbox_sensors": {"Sensor 1": "magnet"},
        "geras_key": "f10fc4d820b1af9387ea9b91ffecb4f5"
    }

The file is in JSON format, but it is not important to understand this. Just copy the above and edit it. If a characteristic is not mentioned, the default will be used, which is True for temperature, humidity and binary and false for everything else. "Min change" values specify the minimum amount a characteristic needs to change by before it is sent to the database. In this example, temperature is not reported unless a reading is more than 0.2 deg C different from the previous reading These should be adjusted so that small changes, which are generally less than the accuracy of most devices anyway, are not sent. This prevents the database being filled with lots of spurious data. "Polling intervals" specify how often sensors for the particular characerisitc should be polled. In this example, if gyros were turned on, values would be polled every three seconds. Some of the characterisitcs do not have a unique polling interval, but instead using the "slow polling interval", in this case set to 300 seconds (5 minutes). The "geras_key" is a key for the geras database that data is to be sent to. You can find this in the API section after you have created a Geras account.

Entry-Exit
---------

If "entry_exit" is set to "True", door entries and exits will be monitored. For this feature to work, each door needs a magnetic switch to report when it is open and there needs to be a PIR sensor inside the door. The PIR does not need to point at the door, but it should be in a position where it is always active within 15 seconds of someone leaving the building or within 15 seconds of someone coming in the door. For this feature to work, the following naming convention must be adopted for the "friendly names" (see documentation on http://continuumbridge.readme.io/) of the devices associated with the doors:

* For the magnetic switch: MagSW??? Door_Name
* For the PIR:  PIR??? Inside Door_Name

The ??? indicates one of more arbitary characters. The app only matches on the "MagSW" and "PIR". The matches are not case-sensitive.

The word "Inside" must be used as the second word for the PIR. This allows for there also to be a PIR outside the door in a future modification to the app.

Both magnetic switch and PIR must use the same word for Door_Name. This name must not contain any spaces. For example, the door name may be Front_Door or Back_Door.

Once entry-exit montioring is enabled, the app sends four series to the database, as follows:

* Door_Name/came_in, indicating that it's likely that someone came in from outside.
* Door_Name/went_out, indicating that it's likely that someone left the building.
* Door_Name/answered_door, indicating that it's likely that someone inside the building answered the door and stayed inside.
* Door_Name/open_and_closed, indicating that it appears that someone opened and closed the door from outside, but did not go in.

Any of the above are likely to be fairly accurate for a single-occupancy building, but can not be relied upon if there are multiple people in the building. For example, movement may be detected in a hallway both before and after someone has gone out the door if one persion is saying goodbye to another at the door as they go out. This would be reported as "answered_door".

Night Wandering
---------------
This feature is designed for sending alerts if activity is detected between certain hours. The example above uses the following:

        "night_wandering": "True",
        "night_start": "00:30",
        "night_end": "07:00",
        "night_sensors": ["Sensor 1", "Sensor 2"],

Night wandering alerts have been switched on. An alert will be sent if any activity on Sensor 1 or Sensor 2 is detected between 00:30 and 07:00. Any senssor can be used that reports a binary_sensor characteristic. These include PIRs and Magnetic switches. If no night_sensors are listed, then the app will look for activity on any sensor with a binary_sensor characteristic. 

Pillbox Monitor
---------------
This feature will send alerts if activity hasn't been detected from a sensor within various time periods. This is controlled using the pillbox parameters in the config file:

        "pillbox": "True",
        "pillbox_start": ["06:00", "20:00"],
        "pillbox_end": ["08:00", "23:00"],
        "pillbox_sensors": {"Sensor 1": "magnet"},

If "pillbox" is set to "True", that "magnet" characteristic of Sensor 1 will be monitored. If this has not changed significantly between 06:00 and 08:00, an alert will be sent. The same will happen if there is not significant activity between 20:00 and 23:00 each day. Up to eight pairs of times may be specified.
