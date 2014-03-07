import threading
import os
import time
import random
import datetime
import logging

from collections import deque
from configurator import cfg
from entropygenerator import EntropyGenerator

log = logging.getLogger(__name__)

try:
    import RPi.GPIO as GPIO
    gpio_available = True
except ImportError:
    log.info("+---------------------------------------------------------------------------+")
    log.info("|              Could not import RPi.GPIO python module.                     |")
    log.info("|   I'm assuming you are in development/show mode on another host system    |")
    log.info("| If this is a Raspberry PI/PiGI and you want real counts, install RPi.GPIO |")
    log.info("+---------------------------------------------------------------------------+")
    log.info("Engaging TickSimulator with an avg. radiation level of %(edr)s uSv/h instead" % {"edr": cfg.getfloat('geigercounter','sim_dose_rate')})
    gpio_available = False

class TickSimulator (threading.Thread):
    def __init__(self, geiger):
        threading.Thread.__init__(self)
        self.daemon = True
        self.geiger = geiger
        log.info("Starting tick simulator")

    def run(self):
        while True:
            ratefactor = cfg.getfloat('geigercounter','tube_rate_factor')
            simrate = cfg.getfloat('geigercounter','sim_dose_rate')
            rate = simrate/ratefactor
            time.sleep(random.random()/rate*120)
            self.geiger.tick()


class Geigercounter (threading.Thread):
    def __init__(self,total=0,total_dtc=0):
        log.info("Starting geigercounter")
        threading.Thread.__init__(self)
        self.daemon = True
        self.socket = None
        self.totalcount=total
        self.totalcount_dtc=total_dtc

        if cfg.getboolean('entropy','enable'):
            self.entropygenerator = EntropyGenerator(cfg.get('entropy','filename'))
        else:
            self.entropygenerator = None


        self.reset()
        self.start()

    def reset(self):
        self.count=0
        self.cps=0
        self.cpm=0
        self.edr=0

    def tick(self, pin=None):
        self.count += 1
        self.totalcount += 1
        if self.entropygenerator:
            self.entropygenerator.tick()

    def run(self):
        if gpio_available:
            GPIO.setmode(GPIO.BCM)
            gpio_port = cfg.getint('geigercounter','gpio_port')
            GPIO.setup(gpio_port,GPIO.IN)
            GPIO.add_event_detect(gpio_port,GPIO.FALLING)
            GPIO.add_event_callback(gpio_port,self.tick)
        else:
            TickSimulator(self).start()

        cpm_fifo = deque([],60)
        while True:
            time.sleep(1)

            # Statistical correction of tube dead-time
            if gpio_available:
                deadtime = cfg.getfloat('geigercounter','tube_dead_time')
                self.count = int(self.count/(1-(self.count*deadtime)))

            cpm_fifo.appendleft(self.count)

            self.cpm = int(sum(cpm_fifo)*60.0/len(cpm_fifo))
            self.cps = self.count
            ratefactor = cfg.getfloat('geigercounter','tube_rate_factor')
            self.edr = round(self.cpm * ratefactor,2)

            self.count = 0
            log.debug(self.get_state())

    def get_state(self):
        msg = {
                "type": "status",
                "node_uuid": cfg.get('node','uuid'),
                "timestamp": int(datetime.datetime.now().strftime("%s")),
                "geostamp": {
                    "lat": 48.00,
                    "lon": 11.00,
                    "alt": 560
                },
                "parameters": {
                    "tube_id": cfg.get('geigercounter','tube_id'),
                    "dead_time": cfg.getfloat('geigercounter','tube_dead_time'),
                    "tube_factor": cfg.getfloat('geigercounter','tube_rate_factor'),
                    "opmode": "stationary",
                    "window": "abc"
                },
                "data": {
                "source": "test",
                "cps": self.cps,
                "cps_dtc": self.cps,
                "cpm": self.cpm,
                "cpm_dtc": self.cpm,
                "totalcount": self.totalcount,
                "totalcount_dtc": self.totalcount,
                "edr": self.edr
                },
                "annotation": ""

            }
        return msg
