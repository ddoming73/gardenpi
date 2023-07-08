"""
gpios - module for initialization and control of the GPIOs used
by the system. 
"""
import time
import threading
import RPi.GPIO as gpio

CH1_GPIO = 5
CH2_GPIO = 6
CH3_GPIO = 13
CH4_GPIO = 16
CH5_GPIO = 19
CH6_GPIO = 20
CH7_GPIO = 21
CH8_GPIO = 26

UP_GPIO = 14
DOWN_GPIO = 18
SEL_GPIO = 15
RST_GPIO = 23

relayGpios = [CH1_GPIO,CH2_GPIO,CH3_GPIO,CH4_GPIO,CH5_GPIO,CH6_GPIO,CH7_GPIO,CH8_GPIO]
ctrlGpios = [UP_GPIO,DOWN_GPIO,SEL_GPIO,RST_GPIO]

channelOnMutex = threading.Lock()

def gpio_init():
    gpio.setmode(gpio.BCM)
    gpio.setup(relayGpios, gpio.OUT, initial=gpio.HIGH)
    gpio.setup(ctrlGpios, gpio.IN, pull_up_down=gpio.PUD_UP)

def gpio_end():
    gpio.cleanup(relayGpios)
    gpio.cleanup(ctrlGpios)

def channelSetOn(channel):
    # Use the mutex to keep channels from turning on
    # simultaneously, to keep inrush current down
    with channelOnMutex:
        gpio.output(relayGpios[channel - 1],gpio.LOW)
        time.sleep(1)

def channelSetOff(channel):
    gpio.output(relayGpios[channel - 1],gpio.HIGH)

def upButtonPressed():
    return not gpio.input(UP_GPIO)

def downButtonPressed():
    return not gpio.input(DOWN_GPIO)

def selButtonPressed():
    return not gpio.input(SEL_GPIO)

def rstButtonPressed():
    return not gpio.input(RST_GPIO)

def addUpButtonCallback(callback_fn):
    gpio.add_event_detect(UP_GPIO, gpio.FALLING,callback=callback_fn, bouncetime=200)

def addDownButtonCallback(callback_fn):
    gpio.add_event_detect(DOWN_GPIO, gpio.FALLING,callback=callback_fn, bouncetime=200)

def addSelButtonCallback(callback_fn):
    gpio.add_event_detect(SEL_GPIO, gpio.FALLING,callback=callback_fn, bouncetime=200)