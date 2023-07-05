#!/usr/bin/env python3

import logging
import queue
import threading
import time
import sqlite3
import gpios
import control
import queueCmd
import math
import systemd_watchdog




def db_init():
    con = sqlite3.connect("gardenpi.sqlite")
    cur = con.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS configuration(channel INTEGER PRIMARY KEY, enabled INTEGER, period_s INTEGER, duration_s INTEGER, startTimeOfDay INTEGER, updated INTEGER)")
    res = cur.execute("SELECT count(channel) FROM configuration")
    if res.fetchone()[0] == 0:
        logging.info("DB empty, creating default configuration")
        res = cur.execute("INSERT INTO configuration VALUES(1,0,0,0,0,0),(2,0,0,0,0,0),(3,0,0,0,0,0),(4,0,0,0,0,0),(5,0,0,0,0,0),(6,0,0,0,0,0),(7,0,0,0,0,0),(8,0,0,0,0,0)")
    cur.execute("UPDATE configuration set updated=1")
    con.commit()    
    con.close()



class ChannelHandler(threading.Thread):
    def __init__(self, channel,ctrlThread, *args, **kwargs):
        self.q = queue.Queue(maxsize=1)
        self.ctrlThread = ctrlThread
        self.channel = channel
        self.enabled = 0
        self.periodSeconds = 0
        self.durationSeconds = 0
        self.startTimeOfDay = 0
        self.nextStartTime = 0
        self.nextEndTime = 0
        self.running = queueCmd.CHANNEL_OFF
        gpios.channelSetOff(self.channel)
        super().__init__(*args, **kwargs)
    def getQueue(self):
        return self.q     
    def run(self):
        try:
            logging.info("Channel %d thread starting",self.channel)
            while True:
                try:
                    cmd = self.q.get(block=True,timeout=1)
                    self.q.task_done()
                    if(cmd.getType() == queueCmd.CMD_CHANNEL_CFG):
                        self.enabled = cmd.getEnabled()
                        self.periodSeconds = cmd.getPeriod()
                        self.durationSeconds = cmd.getDuration()
                        self.startTimeOfDay = cmd.getStartTime()
                        logging.info("Channel %d New Config. Enabled %d. Period %d. Duration %d. Start %d", self.channel,self.enabled,self.periodSeconds,self.durationSeconds,self.startTimeOfDay)
                        if (self.enabled == 1):
                            currentTime = time.time()
                            gmt = time.localtime(currentTime)
                            startOfDay = math.trunc(currentTime - ((gmt.tm_hour * 3600 )+(gmt.tm_min*60)+gmt.tm_sec))
                            self.nextStartTime = startOfDay + self.startTimeOfDay
                            while self.nextStartTime < currentTime:
                                self.nextStartTime+=self.periodSeconds
                            self.running = queueCmd.CHANNEL_WAITING
                        else:
                            gpios.channelSetOff(self.channel)
                            self.running = queueCmd.CHANNEL_OFF
                        cmd.addStatus(self.running,self.nextStartTime)
                        self.ctrlThread.getQueue().put(cmd)
                    elif(cmd.getType() == queueCmd.CMD_QUIT):
                        logging.info("Channel %d thread exiting", self.channel)        
                        return
                except queue.Empty:
                    currentTime = time.time()
                    if (self.running == queueCmd.CHANNEL_WAITING):
                        if currentTime >= self.nextStartTime:
                            self.nextEndTime = self.nextStartTime + self.durationSeconds
                            logging.info("Channel %d is on. Ending at %s", self.channel,time.ctime(self.nextEndTime))        
                            gpios.channelSetOn(self.channel)
                            self.running = queueCmd.CHANNEL_ON
                            cmd = queueCmd.queueCommand(queueCmd.CMD_CHANNEL_CFG)
                            cmd.setConfig(self.channel,self.enabled,self.periodSeconds,self.durationSeconds,self.startTimeOfDay)
                            cmd.addStatus(self.running,self.nextEndTime)
                            self.ctrlThread.getQueue().put(cmd)
                    if (self.running == queueCmd.CHANNEL_ON):
                        if (currentTime >= self.nextEndTime):
                            self.nextStartTime+=self.periodSeconds
                            logging.info("Channel %d is off. Restarting at %s", self.channel,time.ctime(self.nextStartTime))        
                            gpios.channelSetOff(self.channel)
                            self.running = queueCmd.CHANNEL_WAITING
                            cmd = queueCmd.queueCommand(queueCmd.CMD_CHANNEL_CFG)
                            cmd.setConfig(self.channel,self.enabled,self.periodSeconds,self.durationSeconds,self.startTimeOfDay)
                            cmd.addStatus(self.running,self.nextStartTime)
                            self.ctrlThread.getQueue().put(cmd)
        except:
            logging.exception("Exception on channel %d thread",self.channel)
            queueCmd.globalExit = True
            return


class DbHandler(threading.Thread):
    def __init__(self, threadList, *args, **kwargs):
        self.q = queue.Queue(maxsize=1)
        self.threads = threadList
        super().__init__(*args, **kwargs)
    def getQueue(self):
        return self.q     
    def run(self):
        try:
            logging.info("DB check thread starting")
            con = sqlite3.connect("gardenpi.sqlite")
            cur = con.cursor()
            while True:
                try:
                    cmd = self.q.get(block=True,timeout=1)
                    self.q.task_done()
                    if(cmd.getType() == queueCmd.CMD_QUIT):
                        logging.info("DB check thread exiting")
                        con.close()        
                        return
                except queue.Empty:
                    cur = con.cursor()
                    res = cur.execute("SELECT * from configuration WHERE updated=1")
                    config = res.fetchall()
                    for row in config:
                        cmd = queueCmd.queueCommand(queueCmd.CMD_CHANNEL_CFG)
                        channel = row[0]
                        cmd.setConfig(channel,row[1],row[2],row[3],row[4])
                        self.threads[channel-1].getQueue().put(cmd)
                        cur.execute("UPDATE configuration set updated=0 WHERE channel=?",(channel,))
                        con.commit()
        except:
            logging.exception("Exception on DB check thread")
            con.close()
            queueCmd.globalExit = True
            return

if __name__ == "__main__":
    #format = "%(asctime)s: %(message)s"
    format = "%(message)s"
    logging.basicConfig(format=format, level=logging.INFO,
                        datefmt="%H:%M:%S")

    logging.info("Reading configuration")        
    try:
        db_init()
        gpios.gpio_init()

        wd = systemd_watchdog.watchdog()
        if not wd.is_enabled:
            logging.warning("Systemd watchdog not detected")
        else:
            wd.status("Starting...")

        exitStatus = 0
        
        logging.info("Launching threads")

        ctrlThread = control.DisplayHandler()
        ctrlThread.daemon = True
        ctrlThread.start()

        channelList = [ 1,2,3,4,5,6,7,8 ]
        thread_list = []
        for channel in channelList:
            thread_list.append(ChannelHandler(channel,ctrlThread))
            thread_list[-1].daemon = True
            thread_list[-1].start()

        dbThread = DbHandler(thread_list)
        dbThread.daemon = True
        dbThread.start()

        logging.info("Running")
        wd.ready()
        wd.status("Running")
        while not queueCmd.globalExit:
            time.sleep(60)
            if wd.is_enabled:
                wd.ping()

    except KeyboardInterrupt:
        logging.warning("Exiting due to keyboard interrupt")
    except:
        logging.exception("Exiting due to exception")
        exitStatus = 1

    for channel in channelList:
        thread_list[channel-1].getQueue().put(queueCmd.queueCommand(queueCmd.CMD_QUIT))
        thread_list[channel-1].join(30)
    ctrlThread.getQueue().put(queueCmd.queueCommand(queueCmd.CMD_QUIT))
    ctrlThread.join(30)
    dbThread.getQueue().put(queueCmd.queueCommand(queueCmd.CMD_QUIT))
    dbThread.join(30)

    gpios.gpio_end()
    
    exit(exitStatus)
