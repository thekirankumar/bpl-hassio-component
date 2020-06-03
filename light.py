"""

For setting up, set the DEFAULT_HOST to the IP of the controller.
Then Set the sensors array to the all the lights and fans at home.

Every sensor requires a bpl_id to be set correctly.
To get bpl_id connect to your controller via FTP and download this file ftp://bpl@192.168.1.10/home/root/db/sysdb.xml, default password is 123. 
-`bpl_id` is the endpoint attribute present in smarthome/zone/device/endpoint in the sysdb.xml file
-`unique_id` is the ID which will be the entity id hassio will use.
- `name` is the friendly name of the entity.

Copy all the files (init,light.py,manifest etc) present in this repo to custom_components/bpl folder in hassio.


"""
import logging
import socket
import threading
import datetime
import time
import math

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_HOST, CONF_PORT, CONF_NAME)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.components.light import Light

_LOGGER = logging.getLogger(__name__)
DEFAULT_NAME = 'BPL Controller'
DEFAULT_HOST = '192.168.1.10' 
DEFAULT_PORT = 30001

INTERVAL_RECONNECT = 2

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})


async def async_setup_platform(hass, config, add_devices, discovery_info=None):
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)

    sensors = [
        BPLLight(name="Living room Ceiling light", bpl_id=2, unique_id='living_room_ceiling_light'),
        BPLLight(name="Living room Chandelier", bpl_id=1, unique_id='living_room_chandelier'),
        BPLLight(name="Dining Chandelier", bpl_id=34, unique_id='dining_room_chandelier'),
        BPLLight(name="Dining Fan", bpl_id=35, unique_id='dining_room_ceiling_light'),
        BPLLight(name="Master bedroom light 1", bpl_id=17, unique_id='mbr_light_1'),
        BPLLight(name="Master bedroom light 2", bpl_id=18, unique_id='mbr_light_2'),
        BPLLight(name="Kids room fan", bpl_id=32, unique_id='kids_fan'),
        BPLLight(name="Kids room light", bpl_id=33, unique_id='kids_light'),
        BPLLight(name="Guest room light 1", bpl_id=21, unique_id='guest_light_1'),
        BPLLight(name="Guest room light 2", bpl_id=22, unique_id='guest_light_2'),
        BPLLight(name="Entertainment room light 1", bpl_id=19, unique_id='entertainment_light_1'),
        BPLLight(name="Entertainment room light 2", bpl_id=20, unique_id='entertainment_light_2')
    ]

    add_devices(sensors)

    monitor = BPLMonitor(host=host, port=port, sensors=sensors)
    monitor.connect()

    for sensor in sensors:
        sensor.set_monitor(monitor)


    if monitor.sock is None:
        return False
    else:
        return True


class BPLLight(Light):
    """Implementation of a Fritz!Box call monitor."""

    def __init__(self, name, bpl_id, unique_id):
        """Initialize the sensor."""
        self._state = False
        self._attributes = {}
        self._name = name
        self.bplid = bpl_id
        self._unique_id = unique_id

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def is_on(self):
        """Return true if it is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the light on."""
        self._state = True
        _LOGGER.debug("command to turn on, sending to controller")
        self._monitor.send_command(self.bplid, 'CMD_ON')

    def turn_off(self, **kwargs):
        """Turn the light off."""
        self._state = False
        self._monitor.send_command(self.bplid, 'CMD_OFF')
        _LOGGER.debug("command to turn off, sending to controller")

    def set_state(self, state):
        self._state = state
        self.schedule_update_ha_state()

    def set_monitor(self, monitor):
        self._monitor = monitor
        # now get latest state



class BPLMonitor(object):
    """Event listener to monitor controller."""

    def __init__(self, host, port, sensors):
        """Initialize BPL monitor instance."""
        self.host = host
        self.port = port
        self.sock = None
        self._sensors = sensors
        self.counter = 1
        self.last_response_time = 0
        self.last_request_time = 0
        self.got_first_response = False

    def connect(self):

        if self.sock is None :
            """Connect to the BPL"""
            self.counter = 1
            _LOGGER.debug("starting connect to %s on port %s",self.host, self.port)
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            self.got_first_response = False
            try:
                self.sock.connect((self.host, self.port))
                threading.Thread(target=self._listen, daemon=True).start()
            except :
                self.sock = None
                _LOGGER.error("Cannot connect to %s on port %s",
                              self.host, self.port)
                time.sleep(INTERVAL_RECONNECT)
                self.connect()


    def reconnect(self):
        if not (self.sock is None) :
            self.sock.close()
            self.connect()

    def _listen(self):
        """Listen to changes"""
        _LOGGER.debug("BPL Connection success, now listening")
        while True:
            try:
                response = self.sock.recv(2048)
            except socket.timeout:
                # if no response after 10 seconds, just recv again
                if not (self.sock is None) :
                    self.check_and_send_heartbeat()
                continue
            except :
                continue

            response = str(response, "utf-8")

            if not response:
                # if the response is empty, the connection has been lost.
                # try to reconnect
                _LOGGER.error("response from controller empty, possible broken socket")
                self.sock = None
                while self.sock is None:
                    self.connect()
                    time.sleep(INTERVAL_RECONNECT)
                break
            else:
                _LOGGER.debug("received message from controller %s",response)
                self.last_response_time = time.time()
                lines = response.splitlines()
                for line in lines:
                    self._parse(line)
                time.sleep(1)
                if not self.got_first_response :
                    self.got_first_response = True
                    self.process_states_on_connect()
                self.check_and_send_heartbeat()
        return

    def process_states_on_connect(self) :
        for sensor in self._sensors :
            self.send_command(sensor.bplid,"GET_STATE")
            

    def check_and_send_heartbeat(self) :
        time_since_last_ack = time.time() - self.last_response_time
        if  time_since_last_ack> 60 :
            # this means we havent got a ack in last x seconds
            # could be a bad state in sock, hence reconnect
            _LOGGER.error("possible bad state sock, no ackowledgment response since "+str(time_since_last_ack)+" seconds, forcing reconnect")
            self.reconnect()
        else :
            time_since_last_heartbeat = time.time() - self.last_request_time
            if time_since_last_heartbeat > 10 :
                _LOGGER.debug("sending HEARTBEAT, time since ack = "+str(math.floor(time_since_last_ack))+" seconds")
                self.send_command(0,"HEARTBEAT")


    def send_command(self, id, cmd):
        if not (self.sock is None) :
            cmdstr = ':'+str(self.counter)+':'+str(id)+':0:'+cmd+':0:'
            _LOGGER.debug("sending COMMAND "+cmdstr)
            self.sock.send(cmdstr.encode())
            self.last_request_time = time.time()
            self.counter+=1
            time.sleep(0.1) # hack to avoid sending bulk commands which dont work with BPL
        else :
            self.connect()

    def _parse(self, line):
        """Parse the information and set the sensor states."""
        pieces = line.split(":")
        if pieces[1].isnumeric():
            device = int(pieces[1])
            if device > 0 :
                sensor = next((sensor for sensor in self._sensors if sensor.bplid == device), None)
                if not sensor :
                    _LOGGER.warning("Device with id = "+str(device)+" not found, ignoring")
                    return

                state = pieces[3]
                if state == 'CMD_ON' :
                    sensor.set_state(True)
                elif state == 'CMD_OFF':
                    sensor.set_state(False)
