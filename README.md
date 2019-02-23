## Espalexa library for python
This is a port of the [Espalexa](https://github.com/Aircoookie/Espalexa) library (Version 2.3.4) by [@Aircoookie](https://github.com/Aircoookie) for **python 3 only**.
The library covers all functions/features included in the Espalexa library.

#### Installation
The library uses standard python libraries which should already be included in your python 3 installation.
Including the library is easy. Just paste the `espalexa.py` file into your exsisting project folder and include the library:
```python
from espalexa import Espalexa
```

#### Usage
First you want to create an espalexa object:
```python
espalexa = Espalexa()
```
If you want to extend the **default limit of 10 devices** or enable the debug mode, just add the corresponding arguments:
```python
espalexa = Espalexa(MAXDEVICES = 5, DEBUG = True)
```

Than you want to create some callback functions (every device needs its own function):
```python
# device WITHOUT color capabilities
def callback(brightness):
  # the brightness parameter contains the new device state (0:off, 255:on, 1-254:dimmed)
  # you can do whatever you'd like here (e.g. control an LED)
  print("Brighness: " + str(brightness))
  
# device WITH color capabilities
def callback(brightness, rgb):
  # the brightness parameter contains the new device state (0:off, 255:on, 1-254:dimmed)
  # calculate r, g and b value (0 - 255)
  r = int((rgb >> 16) & 0xFF)
  g = int((rgb >>  8) & 0xFF)
  b = int(rgb & 0xFF)
  # you can do whatever you'd like here (e.g. control an LED)
  print("Brighness: " + str(brightness))
  print("Red: " + str(r) + ", Green: " + str(g) + ", Blue: " + str(b))
```

Add the devices in your main function:
```python
# device WITHOUT color capabilities, e.g.
espalexa.addDevice("Light without color", callback, False)

# device WITH color capabilities, e.g.
espalexa.addDevice("Light with color", callback, True)
```
The first argument is a string with the invocation name of the light, the second is a callback function (which will be executed by Espalexa when the status of the device changes), the third is a boolean to enable color capabilities for the device.
If you want to set an initial brightness (value from 0-255) you have to add an additional argument, e.g.:
```python
espalexa.addDevice("Light with color", callback, True, initialValue = 100)
```

Below the device definitions add:
```
espalexa.begin()
```
This will initialize and setup the espalexa object.

You need to call the loop function of the espalexa object to allow it to update and respond to Alexa commands.
This can be done in two (or more) ways, e.g.:
```python
# you can call the loop function in a timed loop by yourself
espalexa.loop()

# or with a timed thread (this needs some additional imports in your main script)
import threading
import time

def loop(espalexa):
	while True:
		espalexa.loop()
    time.sleep(1)     # one second delay between calls is absolutely fine
    
espalexaThread = threading.Thread(target = loop, args = (espalexa,))
espalexaThread.daemon = True    # this makes sure that the espalexa thread gets killed with your main script
espalexaThread.start()
```

#### Changing values manualy
If you want to change the values of a device by yourself you can do this like this, e.g.:
```python
# you can get the device by index (not recommended)
device = espalexa.devices[0]

# or by name comparrison
device = None
for dev in espalexa.devices:
  if dev.getName() == "Light name":
    device = dev
    break
    
# than you can access the values of the device, e.g. setting the brightness:
if not device == None:
  device.setValue(100) # value from 0-255
  device.setPercent(50) # value from 0-100 (percent)
```

#### Why only 10 virtual devices?
The original library is designed for devices with an ESP chip which have far more limited resources than a Raspberry Pi for example.
Python allocates the memory dynamically so the maximum device count doesn't really do anything important in this port.
However, every added device takes up memory which should be concidered when using this library on a device with a small memory.
Running 20+ devices on a single Raspberry Pi 3 worked perfectly without any issues though.
(This option/limit maybe removed in a later update due to its unimportants)

#### How does this work?
Espalexa emulates parts of the SSDP protocol and the Philips hue API, just enough so it can be discovered and controlled by Alexa.
Espalexa only works with a genuine Echo device, it probably wont work with Echo emulators or RPi homebrew devices.
