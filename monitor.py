

import logging
import socket
import threading
import datetime
import time
import math

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
                elif state == 'EV_CURTAIN_OPEN' :
                    sensor.open_cover()
                elif state =='EV_CURTAIN_CLOSE' :
                    sensor.close_cover()
                elif state == 'EV_CURTAIN_STOP' :
                    sensor.stop_cover()
