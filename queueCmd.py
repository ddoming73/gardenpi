"""
queueCmd - definitions for thread communications
and system state
"""

CMD_CHANNEL_CFG = 0
CMD_WAKE_UP = 1
CMD_QUIT = 2

CHANNEL_OFF = 0
CHANNEL_WAITING = 1
CHANNEL_ON = 2

globalExit = False



class QueueCommand():
    # pylint: disable="invalid-name"
    """ 
       This is the command structure passed on to all
       system threads for configuration and status
       reporting. The type of action requested is defined
       by the type parameter
    """
    def __init__(self,cmdType):
        self.type = cmdType
        self.channel = 0
        self.enabled = 0
        self.periodSeconds = 0
        self.durationSeconds = 0
        self.startTimeOfDay = 0
        self.state = CHANNEL_OFF
        self.nextTransition = 0
    def setConfig(self,channel,enabled,period,duration,startTime):
        self.channel = channel
        self.enabled = enabled
        self.periodSeconds = period
        self.durationSeconds = duration
        self.startTimeOfDay = startTime
    def addStatus(self,state,nextTransition):
        self.state = state
        self.nextTransition = nextTransition
    def getType(self):
        return self.type
    def getChannel(self):
        return self.channel
    def getEnabled(self):
        return self.enabled
    def getPeriod(self):
        return self.periodSeconds
    def getDuration(self):
        return self.durationSeconds
    def getStartTime(self):
        return self.startTimeOfDay
    def getState(self):
        return self.state
    def getNextTransition(self):
        return self.nextTransition
    