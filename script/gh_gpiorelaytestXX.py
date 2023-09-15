# Mit diesem Script kann geprüft werden, ob ein https://www.waveshare.com/wiki/RPi_Relay_Board mit Python geschaltet wird
# Jedes der 3 Relais wird dreimal für 0,2 Sekunden eingeschaltet
# Damit wird ein Impuls erzeugt, der einen Eltako-Stromstossschalter umschalten kann

import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)

c = 20

GPIO.setup(c, GPIO.OUT)
GPIO.output(c, GPIO.LOW)

print(f'Impuls {c}')
GPIO.output(c, GPIO.HIGH)
time.sleep(0.2) # 200ms reichen aus, um einen 12VDC-Eltako-Stromstossschalter umzuschalten
GPIO.output(c, GPIO.LOW)
time.sleep(1)

GPIO.cleanup()


