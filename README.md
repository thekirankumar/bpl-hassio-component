# Introduction
A home assistant (hassio) component for bidirectional communication with BPL IQ home automation controller.
Use it to integrate hassio with BPL home automation, the biggest benefit being google home / alexa automation.

My setup is a raspberry pi 3b running Hass OS, connecting to the BPL controller via a local TCP socket.

Its a raw implementation, just to get things working. Lets call this v0.9 to being with. Things are not stable yet.

# Setup
For setting up, set the DEFAULT_HOST to the IP of the controller.
Then Set the sensors array to the all the lights and fans at home.

Every sensor requires a bpl_id to be set correctly.
To get bpl_id connect to your controller via FTP and download this file ftp://bpl@192.168.1.10/home/root/db/sysdb.xml, default password is 123. 
-`bpl_id` is the endpoint attribute present in smarthome/zone/device/endpoint in the sysdb.xml file
-`unique_id` is the ID which will be the entity id hassio will use.
- `name` is the friendly name of the entity.

Copy all the files (init,light.py,manifest etc) present in this repo to custom_components/bpl folder in hassio.

# Conclusion
Once you have successfully got this up and running, you can uninstall the crappy BPL app and use HA app instead :)
