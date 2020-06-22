

import logging
import socket
import threading
import datetime
import time
import math


from . import BPLMonitor, BPLCurtain, DATA_DOMAIN

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
        if isinstance (s,BPLCurtain) :
            sensors_to_add.append(s)
    add_entities(sensors_to_add)
