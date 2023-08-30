import requests
import fileinput
import json
import datetime
import base64
import sys
import mariadb
import logging
from logging.handlers import RotatingFileHandler


###### CMbSolarForecast  { ##############################################################################
class CMbSolarForecast:

   ###### __init__(self) ##############################################################################
   def __init__(self):
      print("Programmstart")

      logging.basicConfig(encoding='utf-8', level=logging.DEBUG,
                          style='{', datefmt='%Y-%m-%d %H:%M:%S', format='{asctime} {levelname} {filename}:{lineno}: {message}',
                          handlers=[RotatingFileHandler('./mb_pvpro.log', maxBytes=100000, backupCount=10)],)

      self.tNow = datetime.datetime.now()
      self.sNow = self.tNow.strftime("%Y-%m-%d-%H-%M")
      self.tJetztStunde = datetime.datetime( self.tNow.year, self.tNow.month, self.tNow.day, self.tNow.hour, 0)

      print(f'Jetzt: {self.tNow}, Jetzt: {self.tJetztStunde}')

      sCfgFile = "mb_pvpro.cfg" # sFile = "E:\\dev_priv\\python_svn\\solarprognose1\\webreq1\\mb_pvpro.cfg"
      try:
         f = open(sCfgFile, "r")
      except Exception as e:
         logging.error(f'Fehler in open({sCfgFile}): {e}')
         quit()

      try:
         Settings = json.load(f)
         f.close()
      except Exception as e:
         logging.error(f'Fehler in json.load(): {e}')
         quit()
      
      try:
         self.skWPeak = Settings['Moduldaten']['kWPeak']  # z.B. 1.4 Kilowattpeak der installierten Solarkollektoren
         self.sEffizienz = Settings['Moduldaten']['Effizienz'] # z.B. 0.95" #Effizienz der Solarmodule, 0.2 ...1

         self.iNeigung = Settings['Modulausrichtung']['Neigung'] # z.B. 30  Neigung der Solarmodule, z.B. 30 Grad
         self.iRichtung = Settings['Modulausrichtung']['Richtung'] # z.B. 210 Ausrichtung der Solarmodule, z.B. 180 (Süd)
         self.sLongi = Settings['Modulausrichtung']['Longi'] # z.B. "13.4" # Länge
         self.sLati = Settings['Modulausrichtung']['Lati'] # z.B. "52.6" # Breite

         self.sDateipfad = Settings['Datei']['Pfad'] # z.B. "E:\dev_priv\python_svn\solarprognose1\webreq1\meteoblue\mb_pvpro_"

         self.MariaIp = Settings['MariaDb']['IP']
         self.MariaUser = Settings['MariaDb']['User']
         sPwdCode = Settings['MariaDb']['PwdCode']
         self.MariaPwd = base64.b64decode(sPwdCode).decode("utf-8")

      except Exception as e:
         logging.error(f'Fehler beim Einlesen von: {sCfgFile}: {e}')
         quit()



   ###### vEndeNormal(self) ##############################################################################
   def vEndeNormal(self):
   #Script beenden und aufräumen
      self.Info2Log('mdb-close')
      self.mdb.close()
      self.mdbLog.close()
      print("Programmende")


   ###### vScriptAbbruch(self) ##############################################################################
   def vScriptAbbruch(self):
   #Script beenden und aufräumen
      self.Error2Log('Abbruch mit mdb-close')
      self.mdb.close()
      self.mdbLog.close()
 #$$ hier müsste noch eine email/sms verschickt werden!
      quit()


   ###### __Record2Log(self, eTyp, eLadeart, sText) ##############################################################################
   def __Record2Log(self, eTyp, sText):
   # Logeintrag in die Datenbank schreiben, bei Fehler auch in die Log-Datei
   #$$ stext auf 250 begrenzen, wenn länger -->Fehlermeldung und Text in die Logdatei
      cur = self.mdbLog.cursor()
      sStmt = f'insert into solar2023.t_prognose_log (tLog, eTyp, sText) values (sysdate(), "{eTyp}","{sText}")'
      try:
         cur.execute( sStmt)
         self.mdbLog.commit()
         print(f'Logeintrag: {eTyp}: {sText}')

      except Exception as e:
         logging.error(f'Fehler beim insert ({eTyp},{sText}) in mariadb.solar2023.t_charge_log: {e}')
         self.vScriptAbbruch()


   ###### Info2Log(self, sText) ##############################################################################
   def Info2Log(self, sText):
      self.__Record2Log( "info", sText)


   ###### Error2Log(self, sText) ##############################################################################
   def Error2Log(self, sText):
      self.__Record2Log( "error", sText)



   ###### VerbindeMitMariaDb(self) ##############################################################################
   # 2 Verbindungen zur MariaDB aufbauen
   def VerbindeMitMariaDb(self):
      
      bConn = False
      bConnLog = False
      for i in range(1,10+1):
         try:
            self.mdb = mariadb.connect( host=self.MariaIp, port=3306,user=self.MariaUser, password=self.MariaPwd)
            bConn = True
         except Exception as e:
            logging.error(f'Fehler in mariadb.connect(): {e}')

         try:
            self.mdbLog = mariadb.connect( host=self.MariaIp, port=3306,user=self.MariaUser, password=self.MariaPwd)
            bConnLog = True

         except Exception as e:
            logging.error(f'Fehler in mariadb.connect() fürs Logging: {e}')

         if bConnLog == True and bConn == True:
            break
         time.sleep(2)

      if bConnLog != True or bConn != True:
         logging.error(f'Fehler in VerbindeMitMariaDb(): Conn: {bConn}, ConnLog: {bConnLog}')
         self.vScriptAbbruch()


      # ab hier Logging in die MariaDb-Tabelle t_charge_log
      self.Info2Log('mdb-connect ok')


   def HolePrognose(self):
      print("Programmstart")

      try:

#***********************************************************************************/
# meteoblue-API exemplary request
#***********************************************************************************/
# Data packages / weather maps / images: pvpro-1h
# https://docs.meteoblue.com/en/weather-apis/packages-api/forecast-data#pv-pro
# liefert 
# - PV power in kWh
# - GTI Global Tilted Irradiance (Radiation) in W/m2
# 4 Wochen Test-Abo:
#	API calls per day (number): maximum 25/day
#	Service expiry (date): 15.06.2023
#
# Differenz zwischen den _instant und _backward-Datenreihen siehe https://content.meteoblue.com/en/research-education/specifications/weather-variables/radiation
# „The backwards value will be the average…So, for production, the backwards value is definitely more useful.”
# 
         sPwd = "gibts bei MeteoBlue"
#OK api_url = "https://my.meteoblue.com/packages/pvpro-1h?apikey=********&lat=52.5244&lon=13.4105&asl=74&format=json&tz=Europe%2FBerlin&slope=30&kwp=1&facing=180&tracker=0&power_efficiency=0.85"

#Um Calls/Credits zu sparen kann das Script ab hier auch mit einer vorher gespeicherten Datei getestet werden:
#         tNow = datetime.datetime(2023,8,28,13,35)
#         sNow = tNow.strftime("%Y-%m-%d-%H-%M")
#         sFile = "E:\\dev_priv\\python_svn\\solarprognose1\\webreq1\\meteoblue\\mb_pvpro_2023-08-29-14-19.json"
#         f = open(sFile, "r")
#         data = json.load(f)
#         f.close()
         api_url = "https://my.meteoblue.com/packages/pvpro-1h?apikey=" + sPwd + "&lat=" + self.sLati + "&lon=" + self.sLongi + "&format=json&tz=Europe%2FBerlin&slope=" + str(self.iNeigung) + "&kwp=" + self.skWPeak + "&facing=" + str(self.iRichtung) + "&tracker=0&power_efficiency=" + self.sEffizienz
         response = requests.get(api_url)
         data = response.json()

         #für Vergleichszwecke auch noch als Datei speichern
         sPretty = json.dumps( data, sort_keys=True, indent=2)
         #sFile = "E:\\dev_priv\\python_svn\\solarprognose1\\webreq1\\meteoblue\\mb_pvpro_" + self.sNow + ".json"
         sFile = self.sDateipfad + self.sNow + ".json"
      
         f = open(sFile, "w")
         f.write( sPretty)
         f.close()

         modelrun = data['metadata']['modelrun_utc']
         modelrun_upd = data['metadata']['modelrun_updatetime_utc']

         # Metadaten der Abfrage speichern
         cur = self.mdb.cursor()
         stmt = "INSERT INTO solar2023.t_abfragen (tAbfrage, dLongitude, dLatitude, tModelRun, tModelRunUpdate, dkWPeak, iNeigung, iRichtung, dEffizienz) VALUES( CONVERT(%s,datetime), CONVERT(%s,double), CONVERT(%s,double), CONVERT(%s,datetime),CONVERT(%s,datetime),CONVERT(%s,double), %d, %d,CONVERT(%s,double))"
         values = ( self.sNow, self.sLongi, self.sLati, modelrun, modelrun_upd,self.skWPeak, self.iNeigung, self.iRichtung, self.sEffizienz)
         cur.execute( stmt,values)

 
         # Solarprognosedaten der Abfrage speichern
         for t in range(1,72): # bei 1 beginnen, weil der Durchschnitt (in der backward-Reihe) für [0]==00:00 nicht bekannt ist
                         # nur für die nächsten 48 Stunden speichern
                         # backwards-(Durchschnitts-)Reihe lesen (in der instant-Reihe steht der Momentanwert der vollen Stunden)
            sStunde = data['data_1h']['time'][t]
            tStunde = datetime.datetime.strptime(sStunde, '%Y-%m-%d %H:%M')

            if (tStunde <= self.tNow) :
               continue; # nur die Zukunft speichern

            if (tStunde.hour < 8 or 17 < tStunde.hour  ) :
               continue; # nur die für den Ertrag relevanten Stunden des Tages speichern

   
            tDiff = tStunde - self.tJetztStunde
            iStunden = (int)((tDiff.days * 86400 + tDiff.seconds) / 3600)
   
            sField = ""
            if iStunden >= 24:
               sField = "p24"
            elif iStunden >= 12:
               sField = "p12"
            elif iStunden >= 6:
               sField = "p6"
            elif iStunden >=3:
               sField = "p3"
            elif iStunden == 1:
               sField = "p1"
            else:
               continue

            dkWh = data['data_1h']['pvpower_backwards'][t]

            stmt = "insert into solar2023.t_prognose (stunde, " + sField + ") values(CONVERT('{0}',datetime), {1}) ON DUPLICATE KEY UPDATE " + sField + "={1}" 
            stmt = stmt.format(sStunde, dkWh)
            print(stmt)
            cur.execute( stmt)
           
      except Exception as e:
         self.Error2Log(f'Fehler in HolePrognose(): {e}')
         self.vScriptAbbruch()


###### CMbSolarForecast  } ##############################################################################

mf = CMbSolarForecast()                    # Konfigdatei lesen 

mf.VerbindeMitMariaDb()                   # Verbindung zur DB herstellen, zweite Verbindung fürs Log

mf.HolePrognose()                       # Prognose abfragen und speichern
mf.mdb.commit()
mf.Info2Log(f'DB aktualisiert')

mf.vEndeNormal()




