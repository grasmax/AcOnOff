# Holt die Solarprognose von Meteoblue und speichert sie in die Datenbank

import requests
import fileinput
import json
import datetime
import base64
import sys
import mariadb
import logging
from logging.handlers import RotatingFileHandler
import time
from Crypto.Cipher import AES
from Crypto import Random
import smtplib
from email.mime.text import MIMEText


###### CAesCipher    ##############################################################################
#  https://stackoverflow.com/questions/12524994/encrypt-and-decrypt-using-pycrypto-aes-256 / 258
BS = 16
pad = lambda s: s + (BS - len(s) % BS) * chr(BS - len(s) % BS).encode()
unpad = lambda s: s[:-ord(s[len(s)-1:])]
class CAesCipher:

   def __init__( self, TestCode):
        self.key = bytes(TestCode, 'utf-8')

   def encrypt( self, Text ):
      encText = Text.encode()
      raw = pad(encText)

      iv = Random.new().read( AES.block_size )
      cipher = AES.new( self.key, AES.MODE_CBC, iv )

      ce = base64.b64encode( iv + cipher.encrypt( raw ) )
      print (ce)
      return ce

   def decrypt( self, Text ):
      enc = base64.b64decode(Text)
      iv = enc[:16]
      cipher = AES.new(self.key, AES.MODE_CBC, iv )
      dec = cipher.decrypt( enc[16:] )
      u = unpad(dec)
      return u.decode("utf-8") 


###### CMailVersand   ##############################################################################
class CMailVersand:
   def __init__(self, sSmtpUser, sSmtpPwdCode, Von, An):
      
      self.SmtpUser = sSmtpUser
      self.SmtpPwdCode = sSmtpPwdCode
      self.Von = Von
      self.An = An

   ###### EmailVersenden(self, sBetreff, sText) ##############################################################################
   def EmailVersenden(self, sBetreff, sText, sTestCode):

    server = smtplib.SMTP_SSL('smtp.ionos.de',465,)
    # server.set_debuglevel(1)

    a = CAesCipher( sTestCode)
    server.login( self.SmtpUser, a.decrypt(self.SmtpPwdCode))
    
    message = MIMEText(sText, 'plain')
    message['Subject'] = sBetreff
    message['From'] = self.Von
    message['To'] = ", ".join(self.An)
    
    server.sendmail( self.Von, self.An,  message.as_string())
    print(message.as_string()) 
    server.quit()

###### CMbSolarForecast  { ##############################################################################
class CMbSolarForecast:

   ###### __init__(self) ##############################################################################
   def __init__(self):
      print("Programmstart")

      logging.basicConfig(encoding='utf-8', level=logging.INFO, # absteigend: DEBUG, INFO, WARNING,ERROR, CRITICAL
                          # DEBUG führt dazu, dass der HTTP-Request samt Passwörtern und APIKeys geloggt wird!
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
         self.sSpeichernVon = Settings['Moduldaten']['SpeichernVon'] # erste Stunde
         self.sSpeichernBis = Settings['Moduldaten']['SpeichernBis'] # letzte Stunde

         self.sDateipfad = Settings['Datei']['Pfad'] # z.B. "E:\dev_priv\python_svn\solarprognose1\webreq1\meteoblue\mb_pvpro_"

         self.MariaIp = Settings['MariaDb']['IP']
         self.MariaUserCode = Settings['MariaDb']['User']
         self.MariaPwdCode = Settings['Pwd']['MariaDb']
         
         self.TestCode = Settings['Pwd']['Test']
         self.aes = CAesCipher(self.TestCode)
         self.MbApiKeyCode = Settings['Pwd']['mb']

         self.mail = CMailVersand( Settings['Mail']['User'], Settings['Pwd']['Smtp'], Settings['Mail']['Von'],Settings['Mail']['An'])

         self.CfgMp = Settings['MehrfachPrognose']

         self.CfgMd = Settings['Moduldaten']
         self.iPvFelder = 0
         fl = self.CfgMd['Felder']
         for sFeldId in fl:
            if fl[sFeldId]['Aktiv'] == 'ja':
               self.iPvFelder += 1



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
      self.mail.EmailVersenden(f'Problem beim Abholen der Solarprognose. Script abgebrochen!', f'Grund:', self.TestCode)
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
         if eTyp == "info":
            logging.info(sText)
         else:
            logging.error(sText)
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
            self.mdb = mariadb.connect( host=self.MariaIp, port=3306,user=str(self.aes.decrypt(self.MariaUserCode)), password=str(self.aes.decrypt(self.MariaPwdCode)))
            bConn = True
         except Exception as e:
            self.log.error(f'Fehler in mariadb.connect(): {e}')

         try:
            self.mdbLog = mariadb.connect( host=self.MariaIp, port=3306,user=str(self.aes.decrypt(self.MariaUserCode)), password=str(self.aes.decrypt(self.MariaPwdCode)))
            bConnLog = True

         except Exception as e:
            self.log.error(f'Fehler in mariadb.connect() fürs Logging: {e}')

         if bConnLog == True and bConn == True:
            break
         time.sleep(2)

      if bConnLog != True or bConn != True:
         logging.error(f'Fehler in VerbindeMitMariaDb(): Conn: {bConn}, ConnLog: {bConnLog}')
         self.vScriptAbbruch()


      # ab hier Logging in die MariaDb-Tabelle t_charge_log
      self.Info2Log('mdb-connect ok')

   ###### HoleMehrfachPrognose(self)  #####################################################################
   def HoleMehrfachPrognose(self, iKwPeak, iRichtung, iNeigung, dataCfg):
      try:

         sLongi = str(dataCfg['Länge'])
         sLati = str(dataCfg['Breite'])
         sKwPeak = str(iKwPeak)
         sEffizienz = '0.95'
#         api_url = "https://my.meteoblue.com/packages/pvpro-1h?apikey=" + self.aes.decrypt(self.MbApiKeyCode) + "&lat=" + sLati \
 #                 + "&lon=" + sLongi + "&format=json&tz=Europe%2FBerlin&slope=" + str(iNeigung) + "&kwp=" + sKwPeak + "&facing=" \
  #               + str(iRichtung) + "&tracker=0&power_efficiency=" + sEffizienz
   #      response = requests.get(api_url)
         #data = response.json()

    # für Testzwecke:
         sFile = "E:\\dev_priv\\python_svn\\solarprognose1\\webreq1\\meteoblue\\mb_pvpro_2023-10-18-12-36_b_45_sud_1_4.json"
         f = open(sFile, "r")
         data = json.load(f)
         f.close()

         dkwhGesamt = 0.0
         times = data['data_1h']['time']
         hours = len(times)

         dataCfg['Von'] = data['data_1h']['time'][0]
         dataCfg['Bis'] = data['data_1h']['time'][hours-1]

         for t in range(1,hours): # bei 1 beginnen weil in backwards-Reihe der erste Wert  0 ist
            sStunde = data['data_1h']['time'][t]
            tStunde = datetime.datetime.strptime(sStunde, '%Y-%m-%d %H:%M')
            dkWh = round(data['data_1h']['pvpower_backwards'][t] , 2)
            dkwhGesamt = round(dkwhGesamt + dkWh, 2)
            print (f'{sStunde}: {dkWh} --> {dkwhGesamt}')
         return dkwhGesamt

      except Exception as e:
         self.Error2Log(f'Fehler in HoleMehrfachPrognose(): {e}')
         self.vScriptAbbruch()

   ###### MehrfachPrognose(self) ##############################################################################
   def MehrfachPrognose(self):
      print( "MehrfachPrognose")

      try:

         jdata = {}
         sjId = 'Solar-Mehrfachprognose'
         jdata[sjId ] = {}

         dataCfg = {}
         dataCfg['Zeitpunkt'] = self.sNow
         dataCfg['Länge'] = self.CfgMp['Longi']
         dataCfg['Breite'] = self.CfgMp['Lati']
         dataCfg['Einheiten'] = 'Richtung: Grad, Neigung: Grad, Daten: kWh'

         data = {}
         fl = self.CfgMp['Felder']
         for feld in fl:
            iRichtung  = fl[feld]['Richtung']
            iNeigung = fl[feld]['Neigung']
            iKwPeak = fl[feld]['KwPeak']
            sP = f'{iRichtung}-{iNeigung}-{iKwPeak}'
            data[sP] = self.HoleMehrfachPrognose( iKwPeak, iRichtung, iNeigung , dataCfg)

         jdata[sjId]['Konfiguration'] = dataCfg
         jdata[sjId]['Daten'] = data

         sFile = self.sDateipfad + "_mp_" + self.sNow + ".json"
         f = open(sFile, "w", encoding='utf-8')
         json.dump(jdata, f, ensure_ascii=False, indent=4)
         f.close()
          
      except Exception as e:
         self.Error2Log(f'Fehler in HoleMehrfachPrognose(): {e}')
         self.vScriptAbbruch()




   ###### HoleEinePrognose ##############################################################################
   def HoleEinePrognose(self, sFeldId, dLongi, dLati, dKwPeak, dEff, iNeigung, iRichtung ):
      print(f'HoleEinePrognose({sFeldId}, {dLongi}, {dLati}, {dKwPeak}, {dEff},{iNeigung}, {iRichtung})')

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

         #OK api_url = "https://my.meteoblue.com/packages/pvpro-1h?apikey=********&lat=52.5244&lon=13.4105&asl=74&format=json&tz=Europe%2FBerlin&slope=30&kwp=1&facing=180&tracker=0&power_efficiency=0.85"

         #Um Calls/Credits zu sparen kann das Script ab hier auch mit einer vorher gespeicherten Datei getestet werden:
#         tNow = datetime.datetime(2023,8,28,13,35)
#         sNow = tNow.strftime("%Y-%m-%d-%H-%M")
         sFile = "E:\\dev_priv\\python_svn\\solarprognose1\\webreq1\\meteoblue\\mb_pvpro_2023-10-19-14-31.json"
         f = open(sFile, "r")
         data = json.load(f)
         f.close()
     
         sLati = str(dLati)
         sLongi = str(dLongi)
         sEff = str(dEff)
         sKwPeak = str(dKwPeak)
         sRichtung = str(iRichtung)
         sNeigung = str(iNeigung)
         a = CAesCipher(self.TestCode)
         api_url = "https://my.meteoblue.com/packages/pvpro-1h?apikey=" + a.decrypt(self.MbApiKeyCode) \
            + "&lat=" + sLati + "&lon=" + sLongi + "&format=json&tz=Europe%2FBerlin&slope=" \
            + sNeigung + "&kwp=" + sKwPeak + "&facing=" + sRichtung + "&tracker=0&power_efficiency=" + sEff
#         response = requests.get(api_url)
 #        data = response.json()


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
         stmt = "INSERT INTO solar2023.t_abfragen (tAbfrage, sFeldname, dLongitude, dLatitude, tModelRun, tModelRunUpdate, dkWPeak, iNeigung, iRichtung, dEffizienz) \
            VALUES( CONVERT(%s,datetime), %s, CONVERT(%s,double), CONVERT(%s,double), CONVERT(%s,datetime),CONVERT(%s,datetime),CONVERT(%s,double), CONVERT(%s,int), CONVERT(%s,int),CONVERT(%s,double))"
         values = ( self.sNow, sFeldId, sLongi, sLati, modelrun, modelrun_upd, sKwPeak, sNeigung, sRichtung, sEff)
         cur.execute( stmt,values)

 
         # Solarprognosedaten der Abfrage speichern
         for t in range(1,72): # bei 1 beginnen, weil der Durchschnitt (in der backward-Reihe) für [0]==00:00 nicht bekannt ist
                         # nur für die nächsten 48 Stunden speichern
                         # backwards-(Durchschnitts-)Reihe lesen (in der instant-Reihe steht der Momentanwert der vollen Stunden)
            sStunde = data['data_1h']['time'][t]
            tStunde = datetime.datetime.strptime(sStunde, '%Y-%m-%d %H:%M')

            if (tStunde <= self.tNow) :
               continue; # nur die Zukunft speichern

            if (tStunde.hour < self.sSpeichernVon or self.sSpeichernBis < tStunde.hour  ) :
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

            dkWh = data['data_1h']['pvpower_backwards'][t] # backwards-Stunde scheint nach Auskunft von Meteoblue vom 17.5.2023 zu bedeuten "Ertrag bis zu dieser Stunde"

            stmt = "insert into solar2023.t_prognose (Stunde, Feldname, " + sField + ") values(CONVERT('{0}', datetime), '{1}', {2}) ON DUPLICATE KEY UPDATE " + sField + "={2}" 
            stmt = stmt.format(sStunde, sFeldId, dkWh )
            print(stmt)
            cur.execute( stmt)

          
      except Exception as e:
         self.Error2Log(f'Fehler in HolePrognose(): {e}')
         self.vScriptAbbruch()

   ###### HolePrognosen(self)  ##############################################################################
   def HolePrognosen(self):
         dLongi = self.CfgMd['Longi']
         dLati = self.CfgMd['Lati']

         fl = self.CfgMd['Felder']
         for sFeldId in fl:
            if fl[sFeldId]['Aktiv'] != 'ja':
               continue
            iRichtung  = fl[sFeldId]['Richtung']
            iNeigung = fl[sFeldId]['Neigung']
            dKwPeak = fl[sFeldId]['KwPeak']
            dEff = fl[sFeldId]['Effizienz']
            self.HoleEinePrognose( sFeldId, dLongi, dLati, dKwPeak, dEff, iRichtung, iNeigung)


###### PruefeStunde(self)  ##############################################################################
# Sicherstellen, dass die täglich erlaubten 25 meteoblue-Calls eingehalten werden
# nachts darf nicht nachgeladen werden --> keine calls sinnvoll
# 25 aufteilen auf alle Flächen: aktuell 2 --> 12 Calls
   def PruefeStunde(self):     
      if self.iPvFelder == 1:
         return True #bei nur einem Feld alle Calls anschöpfen

      if self.tNow.hour in (1,5,6,7,8,9,10,11,12,13,14,18):
         return True
      
      self.Info2Log('Prognose kann nicht abgeholt werden, weil in dieser Stunde kein Call möglich ist.')      
      return False

###### CMbSolarForecast  } ##############################################################################

mf = CMbSolarForecast()                    # Konfigdatei lesen 

mf.VerbindeMitMariaDb()                   # Verbindung zur DB herstellen, zweite Verbindung fürs Log

if mf.CfgMp['Aktiv'] == 'ja':
   mf.MehrfachPrognose()
   mf.vEndeNormal()
   quit()

if mf.PruefeStunde() == False:           # Sicherstellen, dass die täglich erlaubten 25 meteoblue-Calls eingehalten werden
   mf.vEndeNormal()
   quit()

mf.HolePrognosen()                       # Prognose abfragen und speichern
mf.mdb.commit()
mf.Info2Log(f'DB aktualisiert')

mf.vEndeNormal()




