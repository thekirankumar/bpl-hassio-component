"""BPL Hassio Integration"""


import logging
import socket
import threading
import datetime
import time
import math

_LOGGER = logging.getLogger(__name__)

#delay between reconnects
INTERVAL_RECONNECT = 2

#send heartbeat packet to controller every x seconds
SEND_HEARTBEAT_SECONDS = 15

# after these many retries, component gives up
CONNECT_RETRIES = 5

#receive heartbeat packet from controller every x seconds
#if not heartbeat received, connection will be restarted
RECEIVE_HEARTBEAT_TIMEOUT = 60

from homeassistant.components.sensor import PLATFORM_SCHEMA
#from homeassistant.const import (CONF_HOST, CONF_PORT, CONF_NAME)
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.cover import CoverEntity
from homeassistant.components.light import LightEntity

from homeassistant.const import (
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING
)


_LOGGER = logging.getLogger(__name__)
DEFAULT_HOST = '192.168.1.10' 
DEFAULT_PORT = 30001
CONF_HOST = "host"
CONF_PORT = "port"
DOMAIN = "bpl"
DATA_DOMAIN = DOMAIN


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
               #vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
                #vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
            }
        )
    }, extra=vol.ALLOW_EXTRA
)


def setup(hass, config):
    host = DEFAULT_HOST
    port = DEFAULT_PORT

    sensors = [
        BPLLight(name="Living room Ceiling light", bpl_id=2, unique_id='living_room_ceiling_light'),
        BPLLight(name="Living room Chandelier", bpl_id=1, unique_id='living_room_chandelier'),
        BPLLight(name="Dining Chandelier", bpl_id=34, unique_id='dining_room_chandelier'),
        BPLLight(name="Dining Fan", bpl_id=35, unique_id='dining_room_ceiling_light'),
        BPLLight(name="Master bedroom light 1", bpl_id=12, unique_id='mbr_light_1'),
        BPLLight(name="Master bedroom light 2", bpl_id=13, unique_id='mbr_light_2'),
        BPLLight(name="Master bedroom light 3", bpl_id=15, unique_id='mbr_light_3'),
        BPLLight(name="Master bedroom light 4", bpl_id=16, unique_id='mbr_light_4'),
        BPLLight(name="Kids room fan", bpl_id=32, unique_id='kids_fan'),
        BPLLight(name="Kids room light", bpl_id=33, unique_id='kids_light'),
        BPLLight(name="Guest room light 1", bpl_id=21, unique_id='guest_light_1'),
        BPLLight(name="Guest room light 2", bpl_id=22, unique_id='guest_light_2'),
        BPLLight(name="Entertainment room light 1", bpl_id=19, unique_id='entertainment_light_1'),
        BPLLight(name="Entertainment room light 2", bpl_id=20, unique_id='entertainment_light_2'),
        BPLCurtain(name="Living room curtain", bpl_id=3, unique_id='living_curtain')

    ]



    monitor = BPLMonitor(host=host, port=port, sensors=sensors)

    hass.data[DOMAIN] = {
        'sensors':sensors,
        'monitor':monitor
    }

    _LOGGER.debug("loading bpl sensor platforms")
    hass.helpers.discovery.load_platform('light', DOMAIN, {}, config)
    hass.helpers.discovery.load_platform('cover', DOMAIN, {}, config)


    for sensor in sensors:
        sensor.set_monitor(monitor)


    monitor.connect()

    if monitor.sock is None:
        return False
    else:
        return True




class BPLCurtain(CoverEntity) :
    def __init__(self, name, bpl_id, unique_id):
        """Initialize the sensor."""
        self._state = STATE_CLOSED
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

    def open_cover(self, **kwargs) -> None:
        """Open the cover."""
        self._state = STATE_OPENING
        _LOGGER.debug("command to set cover to open")
        if self.hass is not None:
            self.schedule_update_ha_state()

    def close_cover(self, **kwargs) -> None:
        """Close cover."""
        self._state = STATE_CLOSING
        _LOGGER.debug("command to set cover to close")
        if self.hass is not None:
            self.schedule_update_ha_state()

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self._state = STATE_CLOSED
        _LOGGER.debug("command to stop cover")
        if self.hass is not None:
            self.schedule_update_ha_state()


    async def async_added_to_hass(self):
        self.schedule_update_ha_state()

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        return self._state == STATE_OPENING

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        return self._state == STATE_CLOSING

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        return self._state == STATE_CLOSED

    def set_monitor(self, monitor):
        _LOGGER.debug("set monitor")

class BPLLight(LightEntity):
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
        if self.hass is not None:
            self.schedule_update_ha_state()

    def set_monitor(self, monitor):
        self._monitor = monitor
        # now get latest state

    async def async_added_to_hass(self):
        self.schedule_update_ha_state()





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
        self.connect_count = 0

    def connect(self):

        if self.connect_count > CONNECT_RETRIES :
            _LOGGER.debug("Gave up connection retry after "+self.connect_count+" times")
            return
        else :
            self.connect_count+=1
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
        self.connect_count = 0
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
        if  time_since_last_ack> RECEIVE_HEARTBEAT_TIMEOUT :
            # this means we havent got a ack in last x seconds
            # could be a bad state in sock, hence reconnect
            _LOGGER.error("possible bad state sock, no ackowledgment response since "+str(time_since_last_ack)+" seconds, forcing reconnect")
            self.reconnect()
        else :
            time_since_last_heartbeat = time.time() - self.last_request_time
            if time_since_last_heartbeat > SEND_HEARTBEAT_SECONDS :
                _LOGGER.debug("sending HEARTBEAT, time since ack = "+str(math.floor(time_since_last_ack))+" seconds")
                self.send_command(0,"HEARTBEAT")


    def send_command(self, id, cmd):
        try:
                if not (self.sock is None) :
                    cmdstr = ':'+str(self.counter)+':'+str(id)+':0:'+cmd+':0:'
                    
                    self.sock.send(cmdstr.encode())
                    self.last_request_time = time.time()
                    self.counter+=1
                    time.sleep(0.1) # hack to avoid sending bulk commands which dont work with BPL
                else :
                    self.connect()
        except :
                self.sock = None
                self.connect()

        

    def _parse(self, line):
        """Parse the information and set the sensor states."""
        pieces = line.split(":")
        if pieces[1].isnumeric():
            device = int(pieces[1])
            if device > 0 :
                state = pieces[3]
                sensor = next((sensor for sensor in self._sensors if sensor.bplid == device), None)
                if not sensor :
                    _LOGGER.warning("Device not understood :"+str(device)+", ignoring state update :"+state)
                    return
                if state == 'CMD_ON' :
                    sensor.set_state(True)
                elif state == 'CMD_OFF':
                    sensor.set_state(False)
                elif state == 'EV_CURTAIN_OPEN' :
                    sensor.open_cover()
                elif state =='EV_CURTAIN_CLOSE' :
                    sensor.close_cover()
                elif state == 'EV_CURTAIN_STOP' :
                    sensor.stop_cover()
                else :
                    _LOGGER.warning("Command not understand command "+line+" for device :"+str(device))
