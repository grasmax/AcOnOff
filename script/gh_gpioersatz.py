

class GPIO:

   BCM = 'bmc'
   pinstat = 0 
   schaltstat = 0
   IN = 'in'
   OUT = 'out'
   HIGH = 'hi'
   LOW = 'low'

   def __init__(self):
      print('GPIO-Hilfsklasse')

   @staticmethod
   def setmode(mode):
      print (f'gpio-mode: {mode}')

   @staticmethod
   def setup( pin, mode):
      if mode == GPIO.OUT:
         GPIO.pinstat = GPIO.HIGH
      
      print (f'gpio.setup ({pin}, {mode})')

   @staticmethod
   def output( pin, ipinstat):
      if GPIO.pinstat == GPIO.HIGH and ipinstat == GPIO.LOW:
         if GPIO.schaltstat == 1:
            GPIO.schaltstat = 0
         else:
            GPIO.schaltstat = 1

      GPIO.pinstat = ipinstat
      print (f'gpio.output ({pin}: {GPIO.pinstat}, Schaltstat: {GPIO.schaltstat})')

   @staticmethod
   def input( pin):
      if GPIO.schaltstat == 1:
         print (f'gpio.input ({pin})==1')
         return 1
      else:
         print (f'gpio.input ({pin})==0')
         return 0
   
   @staticmethod
   def cleanup():
      print('gpio.cleanup')