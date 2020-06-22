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


from . import BPLMonitor, BPLLight, DATA_DOMAIN
from homeassistant.helpers.entity import Entity
_LOGGER = logging.getLogger(__name__)

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""
    # We only want this platform to be set up via discovery.
    if discovery_info is None:
        return

    sensors = hass.data[DATA_DOMAIN]['sensors']
    sensors_to_add = []
    for s in sensors :
        if isinstance (s, BPLLight) :
            sensors_to_add.append(s)
    add_entities(sensors_to_add)
