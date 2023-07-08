"""
control - Module that handles control of the ssytem using
the SSD1306 OLED display and the front panel GPIOs
"""
import time
import math
import logging
import threading
import subprocess
import queue
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
import Adafruit_SSD1306
import gpios
import queueCmd



STATE_CLEAR_SCREEN = 0
STATE_SHOW_STATUS = 1
STATE_CHANNEL_SEL = 2
STATE_CHANNEL_STATUS = 3

def durationString(duration):
    # pylint: disable="invalid-name"
    """
    Convert a duration in seconds to a string
    for display in HH:MM:SS format
    """
    days,remainder = divmod(duration, 3600*24)
    hours, remainder = divmod(duration, 3600)
    minutes, seconds = divmod(remainder, 60)
    if days > 0:
        return f"{days}d{hours:02}:{minutes:02}:{seconds:02}"
    else:
        return f"{hours:02}:{minutes:02}:{seconds:02}"

def startTimeString(timestamp):
    # pylint: disable="invalid-name"
    """
    Convert a Unix timestamp date into a time of day string
    for display in HH:MM:SS format. 
    """
    currentTime = time.time()
    gmt = time.localtime(currentTime)
    startOfDay = math.trunc(currentTime - ((gmt.tm_hour * 3600 )+(gmt.tm_min*60)+gmt.tm_sec))
    if timestamp > startOfDay:
        duration = timestamp - startOfDay
    else:
        duration = 0
    return durationString(duration)

class DisplayHandler(threading.Thread):
    # pylint: disable="invalid-name"
    """
    Thread that monitors the GPIOs connected to the front panel buttons
    and controls the SSD1306 OLED display.
    """
    def __init__(self, *args, **kwargs):
        self.q = queue.Queue(maxsize=20)
        # 128x64 display with hardware I2C:
        # Note you can change the I2C address by passing an i2c_address parameter like:
        # disp = Adafruit_SSD1306.SSD1306_128_64(rst=RST, i2c_address=0x3C)
        self.disp = Adafruit_SSD1306.SSD1306_128_64(rst=None)
        # Load default font.
        # Alternatively load a TTF font.
        # Make sure the .ttf font file is in the same directory as the python script!
        # Some other nice fonts to try: http://www.dafont.com/bitmap.php
        # font = ImageFont.truetype('Minecraftia.ttf', 8)
        # Draw a black filled box to clear the image.
        self.font = ImageFont.load_default()
        self.startLine = 0
        self.currentLine = 0
        self.state = STATE_CLEAR_SCREEN
        self.endscreen = 0
        self.selChannel = 0

        self.chConfigs = []
        for ch in range(1,9):
            config = queueCmd.QueueCommand(queueCmd.CMD_CHANNEL_CFG)
            config.setConfig(ch,0,0,0,0)
            config.addStatus(queueCmd.CHANNEL_OFF,0)
            self.chConfigs.insert(ch-1,config)
        super().__init__(*args, **kwargs)
    def getQueue(self):
        """
        Return thread queue
        """
        return self.q
    def clearScreen(self):
        """
        Function to clear the OLED display.
        """
        self.disp.clear()
        self.disp.display()
    def statusScreen(self):
        """
        Function to render the system status screen.
        """
        # Create blank image for drawing.
        # Make sure to create image with mode '1' for 1-bit color.
        width = self.disp.width
        height = self.disp.height
        image = Image.new('1', (width, height))
        # Get drawing object to draw on image.
        draw = ImageDraw.Draw(image)
        # Draw a black filled box to clear the image.
        draw.rectangle((0,0,width,height), outline=0, fill=0)
        # First define some constants to allow easy resizing of shapes.
        padding = -2
        top = padding
        #bottom = height-padding
        # Move left to right keeping track of the current x position for drawing shapes.
        x = 0

        # Shell scripts for system monitoring from here :
        # https://unix.stackexchange.com/questions/119126/command-to-display-memory-usage-disk-usage-and-cpu-load
        #
        #cmd = "top -bn1 | grep load | awk '{printf \"CPU Load: %.2f\", $(NF-2)}'"
        #cmd = "free -m | awk 'NR==2{printf \"Mem: %s/%sMB %.2f%%\", $3,$2,$3*100/$2 }'"
        #cmd = "df -h | awk '$NF==\"/\"{printf \"Disk: %d/%dGB %s\", $3,$2,$5}'"
        cmd = "./stats.sh time"
        Time = subprocess.check_output(cmd, shell = True )
        cmd = "./stats.sh ip"
        host = subprocess.check_output(cmd, shell = True )
        cmd = "./stats.sh ssid"
        wifi = subprocess.check_output(cmd, shell = True )
        cmd = "./stats.sh signal"
        signal = subprocess.check_output(cmd, shell = True )

        draw.text((x, top),       str(Time.decode('utf-8')), font=self.font, fill=255)
        draw.text((x, top+10),    str(host.decode('utf-8')), font=self.font, fill=255)
        draw.text((x, top+20),    str(wifi.decode('utf-8')), font=self.font, fill=255)
        draw.text((x, top+30),    str(signal.decode('utf-8')), font=self.font, fill=255)

        # Display image.
        self.disp.image(image)
        self.disp.display()

    def channelSelScreen(self):
        """
        Function to render the channel selection screen.
        """
        # Create blank image for drawing.
        # Make sure to create image with mode '1' for 1-bit color.
        width = self.disp.width
        height = self.disp.height
        image = Image.new('1', (width, height))
        # Get drawing object to draw on image.
        draw = ImageDraw.Draw(image)
        # Draw a black filled box to clear the image.
        draw.rectangle((0,0,width,height), outline=0, fill=0)
        # First define some constants to allow easy resizing of shapes.
        padding = -2
        top = padding
        #bottom = height-padding
        # Move left to right keeping track of the current x position for drawing shapes.
        x = 0
        draw.text((x, top),       str("Select Channel:"), font=self.font, fill=255)
        draw.line([(x,top+10),(width,top+10)], fill=255)
        y = top+12
        for ch in range(self.startLine,self.startLine+5):
            config = self.chConfigs[ch-1]
            if config.getEnabled():
                state = "OFF til" if config.getState() == queueCmd.CHANNEL_WAITING else "ON til"
                state+= f" {startTimeString(config.getNextTransition())}"
            else:
                state = "DISABLED"
            line = f"CH{ch} {state}"
            if ch == self.currentLine:
                draw.rectangle((x,y,width,y+10), outline=0, fill=255)
                draw.text((x+1, y), line, font=self.font, fill=0)
            else:
                draw.text((x+1, y), line, font=self.font, fill=255)
            y+= 10

        # Display image.
        self.disp.image(image)
        self.disp.display()

    def channelStatusScreen(self):
        """
        Function to render the channel status screen.
        """
        config = self.chConfigs[self.selChannel-1]
        # Create blank image for drawing.
        # Make sure to create image with mode '1' for 1-bit color.
        width = self.disp.width
        height = self.disp.height
        image = Image.new('1', (width, height))
        # Get drawing object to draw on image.
        draw = ImageDraw.Draw(image)
        # Draw a black filled box to clear the image.
        draw.rectangle((0,0,width,height), outline=0, fill=0)
        # First define some constants to allow easy resizing of shapes.
        padding = -2
        top = padding
        #bottom = height-padding
        # Move left to right keeping track of the current x position for drawing shapes.
        x = 0
        if config.getEnabled():
            state = "OFF til" if config.getState() == queueCmd.CHANNEL_WAITING else "ON til"
            state+= f" {startTimeString(config.getNextTransition())}"
        else:
            state = ""
        line = f"CH{self.selChannel}: {state}"
        draw.text((x, top), line, font=self.font, fill=255)
        draw.line([(x,top+10),(width,top+10)], fill=255)
        y = top+12
        enabled = config.getEnabled()!=0
        for prop in range(1,6):
            if prop == 1:
                line = f"Enabled:  {'YES' if enabled else 'NO'}"
            elif prop == 2:
                line = f"Interval: {durationString(config.getPeriod()) if enabled else '---'}"
            elif prop == 3:
                line = f"Duration: {durationString(config.getDuration()) if enabled else '---'}"
            elif prop == 4:
                line = f"Start at: {durationString(config.getStartTime()) if enabled else '---'}"
            elif prop == 5:
                line = "Back"
            else:
                line = ""
            if prop == self.currentLine:
                draw.rectangle((x,y,width,y+10), outline=0, fill=255)
                draw.text((x+1, y), line, font=self.font, fill=0)
            else:
                draw.text((x+1, y), line, font=self.font, fill=255)
            y+= 10

        # Display image.
        self.disp.image(image)
        self.disp.display()

    def nextState(self,channel):
        """
        Function that is called when a front panel button
        is pressed.
        It handles the state machine that decides which 
        screen must be shown and for how long.
        
        WARNING: This function does not run in the
                 context of this class, it is called
                 by the thread created by the gpio
                 library to handle callbacks
        """
        if channel == gpios.UP_GPIO:
            if self.state == STATE_CLEAR_SCREEN:
                self.state = STATE_SHOW_STATUS
                self.endscreen = time.time() + 30
            elif self.state == STATE_SHOW_STATUS:
                self.endscreen = time.time() + 30
            elif self.state == STATE_CHANNEL_SEL:
                if self.currentLine > 1:
                    self.currentLine-=1
                    if self.currentLine < self.startLine:
                        self.startLine = self.currentLine
                self.endscreen = time.time() + 120
            elif self.state == STATE_CHANNEL_STATUS:
                if self.currentLine > 1:
                    self.currentLine-=1
                    if self.currentLine < self.startLine:
                        self.startLine = self.currentLine
                self.endscreen = time.time() + 120
        elif channel == gpios.DOWN_GPIO:
            if self.state == STATE_CLEAR_SCREEN:
                self.state = STATE_SHOW_STATUS
                self.endscreen = time.time() + 30
            elif self.state == STATE_SHOW_STATUS:
                self.endscreen = time.time() + 30
            elif self.state == STATE_CHANNEL_SEL:
                if self.currentLine < 8:
                    self.currentLine+=1
                    if (self.startLine + 4) < self.currentLine:
                        self.startLine = self.currentLine-4
                self.endscreen = time.time() + 120
            elif self.state == STATE_CHANNEL_STATUS:
                if self.currentLine < 5:
                    self.currentLine+=1
                    if (self.startLine + 4) < self.currentLine:
                        self.startLine = self.currentLine-4
                self.endscreen = time.time() + 120
        elif channel == gpios.SEL_GPIO:
            if self.state == STATE_CLEAR_SCREEN:
                self.state = STATE_SHOW_STATUS
                self.endscreen = time.time() + 30
            elif self.state == STATE_SHOW_STATUS:
                self.state = STATE_CHANNEL_SEL
                self.startLine = 1
                self.currentLine = 1
                self.endscreen = time.time() + 120
            elif self.state == STATE_CHANNEL_SEL:
                self.state = STATE_CHANNEL_STATUS
                self.selChannel = self.currentLine
                self.startLine = 1
                self.currentLine = 1
                self.endscreen = time.time() + 120
            elif self.state == STATE_CHANNEL_STATUS:
                if self.currentLine == 5:
                    self.state = STATE_CHANNEL_SEL
                    self.currentLine = self.selChannel
                    if (self.startLine + 4) < self.currentLine:
                        self.startLine = self.currentLine-4
                self.endscreen = time.time() + 120
        else:
            logging.error("Wrong button")
        self.q.put(queueCmd.QueueCommand(queueCmd.CMD_WAKE_UP))

    def screenStateMachine(self):
        """
        Function that handles the actual rendering of screens
        It is called every second when the thread's queue timeouts,
        therefore each screen is refreshed at least every second.
        It is also called in response to a wake up command, so the
        screen responds inmediately to button presses and configuration/status
        changes.
        """
        currentTime = time.time()
        if((self.endscreen != 0) and (self.endscreen <= currentTime) ):
            self.clearScreen()
            self.endscreen = 0
            self.state = STATE_CLEAR_SCREEN
        elif self.state == STATE_SHOW_STATUS:
            self.statusScreen()
        elif self.state == STATE_CHANNEL_SEL:
            self.channelSelScreen()
        elif self.state == STATE_CHANNEL_STATUS:
            self.channelStatusScreen()

    def run(self):
        try:
            logging.info("Display thread starting")
            # Initialize library.
            self.disp.begin()
            self.clearScreen()
            self.state = STATE_SHOW_STATUS
            self.endscreen = time.time() + 30

            gpios.addUpButtonCallback(self.nextState)
            gpios.addDownButtonCallback(self.nextState)
            gpios.addSelButtonCallback(self.nextState)
            while True:
                try:
                    cmd = self.q.get(block=True,timeout=1)
                    self.q.task_done()
                    if cmd.getType() == queueCmd.CMD_CHANNEL_CFG:
                        index = cmd.getChannel()-1
                        self.chConfigs.pop(index)
                        self.chConfigs.insert(index,cmd)
                    elif cmd.getType() == queueCmd.CMD_WAKE_UP:
                        self.screenStateMachine()
                    elif cmd.getType() == queueCmd.CMD_QUIT:
                        self.disp.clear()
                        self.disp.display()
                        logging.warning("Display thread exiting")
                        return
                except queue.Empty:
                    self.screenStateMachine()
        except Exception:  # pylint: disable="broad-exception-caught"
            logging.exception("Exception on display thread")
            self.disp.clear()
            self.disp.display()
            queueCmd.globalExit = True
            return
