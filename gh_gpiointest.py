# Mit diesem Script kann geprüft werden, ob das Anlegen von 3,3VDC an einem GPIO-Pin mit python erkannt wird

import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)

aPin = [17,27,22,5,6,23,24,25,16]

for p in aPin:
   GPIO.setup(p, GPIO.IN, GPIO.PUD_DOWN) # den internen pulldown-Widerstand aktivieren

bTest = 1
while bTest == 1:  
   for p in aPin:
      if GPIO.input(16) == 1:
         print('Ende')
         bTest = 0
         break;

      if GPIO.input(p) == 1:
         print(f'Pin {p} is high')
      time.sleep(0.2) 



GPIO.cleanup()


