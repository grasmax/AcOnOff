# Liest Daten aus Victron Cerbo GX via ModbusTCP
# frei nach https://community.victronenergy.com/questions/190594/need-help-with-python-modbus-queery.html
# https://www.victronenergy.com/live/ccgx:modbustcp_faq
# https://www.victronenergy.com/support-and-downloads/technical-information
#   https://www.victronenergy.com/upload/documents/CCGX-Modbus-TCP-register-list-3.30.xlsx
# https://pymodbus.readthedocs.io/en/latest/source/library/pymodbus.html


from pymodbus.constants import Endian
from pymodbus.client import ModbusTcpClient as ModbusClient
from pymodbus.payload import BinaryPayloadDecoder


class CModbus:
   def __init__(self):

      self.BattID = 225 # ID der Pylontec-Batterien aus der Cerbo-Remote-Konsole: Modbus TCP Services
      self.MPPT = 226 # ID des Victron MPPT 250/60 aus der Cerbo-Remote-Konsole: Modbus TCP Services

      self.ip = "xxx.xxx.xxx.xxx" # der Cerbo im LAN
      self.client = None


   def GetUIntValue(self, address, slave, ScaleFactor):
      try:
         msg     = self.client.read_holding_registers(address,  slave=slave)
         #print(msg.registers)
       
         decoder = BinaryPayloadDecoder.fromRegisters(msg.registers, byteorder=Endian.BIG)
    
         msg     = decoder.decode_16bit_uint() / ScaleFactor
         return msg
      except Exception as e:
         print(f'Ausnahme in GetUIntValue({address}, {slave}, {ScaleFactor}):  {e}')    
    
   def GetStringValue(self, address, slave, nChars):
     try: 
         msg     = self.client.read_holding_registers(address, nChars, slave=slave)
         #print(msg.registers)

         decoder = BinaryPayloadDecoder.fromRegisters(msg.registers, byteorder=Endian.BIG)
    
         msg     = decoder.decode_string(nChars).decode('ascii')
         return msg
     except Exception as e:
         print(f'Ausnahme in GetStringValue({address}, {slave}, {nChars}):  {e}')    

try:
   mb = CModbus() 

   mb.client = ModbusClient(mb.ip, port='502')
   mb.client.connect()                           # connect to device, reconnect automatically
   print(f'Verbunden mit {mb.ip}') 

   BatterySOC  = mb.GetUIntValue(266, mb.BattID, 10.0)  # war dbus "com.victronenergy.system", "/Dc/Battery/Soc"
   print(f"BatterySOC {BatterySOC}")

   YieldUser = mb.GetUIntValue(790, mb.MPPT, 10.0) #/Yield/User weil Adresse für /Yield/System (bei DBUS ok) nicht gefunden
   print(f"YieldUser {YieldUser}")

   pvv = mb.GetUIntValue(776, mb.MPPT, 100.0) #/Pv/V
   print(f"pv-v {pvv}")

   #gibts auch nicht: 
         #  /History/Overall/MaxPvVoltage  dbus: 178,97
         # Abfrage der LEDs am MPII:
         # dbus -y com.victronenergy.vebus.ttyS4 /Leds/Inverter GetValue
         # dbus -y com.victronenergy.vebus.ttyS4 /Leds/Absorption GetValue
         
         #Abfrage der installierten Batteriekapa:
         #  dbus -y com.victronenergy.battery.socketcan_can1 /InstalledCapacity GetValue


   battv = mb.GetUIntValue(259, mb.BattID, 100.0) #war dbus "com.victronenergy.battery.socketcan_can1" "/Dc/0/Voltage"
   print(f"battv {battv}")

   battoffl = mb.GetUIntValue(1302, mb.BattID, 1.0) #war dbus "com.victronenergy.battery.socketcan_can1" "/System/NrOfModulesOffline"
   print(f"battoffl {battoffl}")
   
   # ist vorhanden, liefert aber nur 0 mit mb.BattID, mit ID=100 kommt Fehlermeldung
   #battcells = mb.GetUIntValue(1289, 100, 1.0) #war dbus "com.victronenergy.battery.socketcan_can1" "/System/NrOfCellsPerBattery"
   #print(f"battcells {battcells}")


   mincv = mb.GetUIntValue(1290, mb.BattID, 100.0) #war dbus "com.victronenergy.battery.socketcan_can1" "/System/MinCellVoltage"
   print(f"mincv {mincv}")
   maxcv = mb.GetUIntValue(1291, mb.BattID, 100.0) #war dbus "com.victronenergy.battery.socketcan_can1" "/System/MaxCellVoltage"
   print(f"maxcv {maxcv}")

   minct = mb.GetUIntValue(318, mb.BattID, 10.0) #war dbus "com.victronenergy.battery.socketcan_can1" "/System/MinCellTemperature"
   print(f"minct {minct}")
   maxct = mb.GetUIntValue(319, mb.BattID, 10.0) #war dbus "com.victronenergy.battery.socketcan_can1" "/System/MaxCellTemperature"
   print(f"maxct {maxct}")

   mincvi = mb.GetStringValue(1306, mb.BattID, 4)  #war dbus "com.victronenergy.battery.socketcan_can1" "/System/MinVoltageCellId"
   print(f"mincvi {mincvi}")
   maxcvi = mb.GetStringValue(1310, mb.BattID, 4)  #war dbus "com.victronenergy.battery.socketcan_can1" "/System/MaxVoltageCellId"
   print(f"maxcvi {maxcvi}")

   mincti = mb.GetStringValue(1314, mb.BattID, 4) #war dbus "com.victronenergy.battery.socketcan_can1" "/System/MinTemperatureCellId"
   print(f"mincti {mincti}")
   maxcti = mb.GetStringValue(1318, mb.BattID, 4)  #war dbus "com.victronenergy.battery.socketcan_can1" "/System/MaxTemperatureCellId"
   print(f"maxcti {maxcti}")




   mb.client.close()
   print(f'Abgemeldet...') 

except Exception as e:
         print(f'Ausnahme in CModbus():  {e}')    
