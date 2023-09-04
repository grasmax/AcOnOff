#   Ziel: Nachladen der Solar-Puffer-Batterien in Abhängigkeit vom Batterie-State of Charge (SOC, Batterieladezustand),
#            der Solarprognose sowie dem prognostizierten Verbrauch einschließlich der Anlage selbst
#            durch Ein- und Ausschalten der Versorgung des MultiplusII-Chargers mit Stadtstrom an AC-IN
#
#             Bei Blackout-Gefahr: 
#             - SOC permanent bei 100% halten, keine Solarunterstützung, Laden mit Stadtstrom permanent ein
#             - Umsetzung nicht hier im Script, sondern mit Hardwareschalter (AC-IN permanent ein)
#
#             Bei Brownout-Gefahr, d.h. angekündigten Abschaltungen:
#             - Kapa vor der Abschaltung mit oder ohne Solarunterstützung auf 100% bringen
#             - Umsetzung: in Planung: Brownouts abfragen und in Tabelle eintragen, Versuchen, bis zum Beginn die SOC-Lücke bis 100% zu füllen
#
#             Unterscheiden: Nachladen(bis 90%) / Ausgleichsladen (ausreichend lange 100%, bis alle Batterien und -Zellen ausgeglichen sind)
#
#             Im Normalfall:
#             - Für den lt. Prognose zu erwartender Solar-Ertrag muss Kapa in der Batterie freigehalten werden.
#             - Ausgleichs- und Nachladen nur dann, wenn laut Solar-Prognose nicht mehr als 0,1kWh/h zu erwarten sind.
#             - Wenn das Ausgleichsladen begonnen hat, wird aber keine Rücksicht auf den eventuell zu erwartenden Solarertrag genommen.
#             - Das Nachladen wird aber abgebrochen, wenn Solarertrag zu erwarten ist.
#             - Der SOC wird beim Nachladen zwischen 21 und 85 Prozent gehalten.
#             - Wenn der SOC unter 20% fällt, sichert die Generatorregel im CerboGX das Einschalten des LAdestroms.
#             - Die Anzahl der Ein- und Ausschaltvorgänge soll minimiert werden, um die Schütze zu schonen.
#             - Das Nachladen soll im Idealfall nur nachts stattfinden, wenn nur die Grundlast (Kühlung, Heizung, Fritzbox) gebraucht wird.
#             - Die Prognose soll mit den historischen Verbrauchs-Werten rechnen, die im Tagesprofil gespeichert sind.
#             - In Planung: Das Tagesprofil soll Monate und oder Jahreszeiten unterscheiden können.
#             - Ablauf einer Berechnung:
#                 + Prüfen, ob Jetzt in Stunde mit Solarertrag:
#                 +    Ja: Nachladen nur dann einschalten, wenn die untere SOC-Grenze in der nächsten Stunde unterschritten würde
#                 +    Nein: 
#                 +        Array 48x3 anlegen für 48 Stunden, jeweils: Verbrauch (kWh), Solarertrag (kWh), SOC
#                 +        Array füllen und die maximale Unterschreitung des minimalen SOC ermitteln
#                 +           Achtung! der berechnete SOC geht bei viel Sonne über 100%! Das ist aber in der Praxis nicht so
#                 +              ab 89% beginnt die Absorbtionsphase, deren Verlauf nicht beschrieben ist!
#                 +              als muss der Algorithmus erst einmal annehmen, dass der SOC nur bis 89% kommt!
#                 +        Wird der SOC unterschritten?
#                 +           Nein: nichts tun
#                 +           Ja: Nachladen einschalten, Ausschalten, wenn wieder Solarertrag und wenn die Stundenprognose das zulässt
#
#              Der Solarertrag reduziert sich um den Eigenverbrauch der Anlage. In die SOC-Reichweitenberechnung gehen ein:
#                   + Solarprognose
#                   - Sofortverbrauch
#                   - Eigenverbrauch
#
#    Repository: https://github.com/grasmax/AcOnOff
#
#    Schaltprinzip:
#       mb_pvpro.py holt die Solarprognose von MeteoBlue und schreibt sie in die Tabelle t_prognose.
#       Hier umgesetzt: Dieses Script 
#        - liest über ssh/dbus Werte aus der Anlage und schreibt sie in die Tabelle t_victdbus_stunde: SOC, Solarertrag, Zählerstände
#        - liest, füllt und aktualisiert stündlich die Tabelle t_tagesprofil; darin sind für jede Stunde der Durchschnittsverbrauch gespeichert
#        - berechnet aus t_prognose, t_tagesprofil und t_victdbus_stunde, ob und wie lange die Batterien geladen werden sollen 
#        - schreibt in die Tabellen t_charge_state und t_charge_ticket
#       In Planung:
#       - SchalteGpio() (auf dem Master-Raspi) schaltet ein Relais1 auf dem Raspi-Relayboard 
#       - Relais1 schaltet 12VDC durch zu einem Stromstoßschalter. Der Stromstoßschalter schaltet 48VDC durch zum Klemmmenblock 3 im Verteilerkasten Solar
#         Dadurch schaltet der Schütz im Verteilerkasten Solar 230VAC durch zu AC-IN des MultiplusII.
#         Dadurch schaltet der MultiplussII das Ladegerät ein und versorgt alle an AC-Out1 angeschlossenen Verbraucher mit Stadtstrom.
#       - Der Schaltzustand des Stromstoßschalters wird erfasst mit einem KM12-Sensor, der seinerseits im eingeschalteten Zustand 3VDC zu einem GPIO-Pin schaltet, das
#         von HoleUndTesteGpioStatus() überwacht wird.
#
#        Das ursprüngliche Konzept sah ein weiteres Script vor, dass das GPIO-Pins schalten sollte und über Tickets von hier aus getriggert werden sollte.
#        Dabei ging ich davon aus, dass das GPIO-Pin solange auf high gehalten werden muss, wie der Leistungsschütz eingeschaltet sein soll.
#        Dafür hätte das Script für die Dauer des Ladevorgangs laufen müssen. Und das Relais hätte 48VDC schalten müssen, es ist aber nur für 30 VDC zugelassen.
#        Das aktuelle Konzept sieht deshalb einen zusätzlichen Stromstoßschalter vor, der über das Relais auf dem Raspi-Board mit 12VDC angesteuert wird.
#        Dazu ist nur ein 0.2ms-Impuls nötig, das Relais wird geschont und das Script muss nicht dauerhaft laufen. 
#        Das Schalten des GPIO-Pin 26 kann also hier gleich mit erledigt werden. (Pin 26 getestet in der Alarmanlage)
#        An den Stromstoßschalter ist ein KM12-Modul angedockt, das den Schaltzustand anzeigt. 
#        Dieser Schaltzustand wird über GPIO-Pin 22 abgefragt (mit 3,3V an Pin 22 und 23 schon an der Alarmanlage getestet)
#
#     Diese Berechung wird stündlich ausgeführt:
#          In welchem Zustand ist das Ladegerät?
#             AUS
#                Eintrag in t_charge_log
#                bIstAusgleichenNoetigUndMoeglich?
#                   ja: AusgleichEin, Ende
#                   nein:IstLadenNötig?
#                      ja: Ladenein, Ende
#                      nein: Ende
#
#             AUSGLEICHEN (bis 100%)
#                Eintrag in t_charge_log
#                IstAusgleichenAusMöglich?
#                   ja: AusgleichenAus, Ende
#                   nein: Ende
#
#             LADEN (bis 90%)
#                Eintrag in t_charge_log
#                IstLadenAusMöglich?
#                   ja: LadenAus, Ende  <-- wenn Ausgleichen nötig, wird dies erst eine Stunde später eingeschaltet
#                   nein: Ende
#
#
#      Detaillierte Beschreibung zu IstLadenNötig()
#       
#       Ladezustand und -verfahren wird in die DB-Tabelle t_charge_state gespeichert.
#       Alle Ein- und Ausschaltvorgänge werden in die DB-Tabellen t_charge_ticket und t_charge_log gespeichert.
#       Das Tagesprofil wird in der Tabelle t_tagesprofil gespeichert: 24 Datensätze, jeweils mit Haus: Durchschnittsverbrauch, Min, Max und Anlage: Durchschnittsverbrauch, Min, Max
#           Durchschnittsverbrauch, Min und Max werden täglich aktualisiert.
#           Mindestens 24 Datensätze für jeden Monat (im Idealfall für jeden Tag des Jahres, vernüftige Durchschnittswerte würden sehr lange dauern...)
#       Das berechnete Profil für die Berechnung: für die nächsten 48 Stunden: 48 Datensätze, jeweils mit Durchschnittsverbrauch (Haus und Anlage), Solarprognose, SOC
#
#          Randbedingungen:
#             SOC: 100% entsprechen 200Ah (4*50Ah)
#             in einer Stunde kann die Batteriekapa mit einem Ladestrom von 230VAC/9,5A (per Konfig und Kabel vorgegeben, entsprechen ca. 50VDC/40A, das sind 40Ah)
#                 16.6.23: Ladestrom war im MPII auf 5A begrenzt...auf 20A erhöht, kommt auch an...         
#                   -->20A/h SOC kann pro Stunde um 10% erhöht werden
#                Ladedauer von 20% auf 85%: 65% / 10% : 6,5h
#             Durchschnittlicher Verbrauch in 24h: 4kWh = 40%
#
#          Umsetzung:
#             stündlich prüfen
#             aktuellen SOC betrachten
#                SOC darf in der kommenden Stunde nicht unter 21% fallen
#                nachts, wenn niemand auf Fehler reagieren kann: SOC darf zwischen 2200 und 0800 nicht unter 21% fallen
#                nachts mit der 12h-Prognose rechnen, zwischen 9 und 17 mit den 6-3-1-Prognosen
#
#          Beispielrechnung 0900:
#             maximal möglicher Brutto-Solarertrag lt Prognose: 5kWh 
#                   minus Eigenverbrauch der Anlage von 1kWh, bleiben: 4kWh
#                   minus Sofortverbrauch im Haus von 1kWh, bleiben: 3kWh = 30% Netto-Solarertrag
#             Fazit: 0900 darf der SOC nicht über 55% liegen
#       
#          Beispielrechnung 1700:
#             maximal möglicher Brutto-Solarertrag lt Prognose für nächsten Tag: 5kWh 
#                   minus Eigenverbrauch der Anlage von 1kWh, bleiben: 4kWh
#                   minus Sofortverbrauch im Haus von 1kWh, bleiben: 3kWh = 30% Netto-Solarertrag
#             Fazit: 0900 darf der SOC nicht über 55% liegen
#             1700: SOC: 85%
#             1700-0900: 16h / 2/3 vom Durchschnittsverbrauch des Hauses: 2,7kWh sind 27%
#             Fazit: bis 0900 sinkt der SOC auf 58% 
#
#          Beispielrechnung 14.6.,1300: SOC: 66%, Prognose: 2,9kWh - 0,58 (Anlage)  - 0,7 (Haus) = ~1,6kWh = 16%
#             Fazit: 1700 SOC: 66+16=82% --> 3% fehlen zwar --> nicht einschalten
#
#          Beispielrechnung 15.6.,1500: SOC: 63%, Ymppt=256kWh Prognose: 0,97kWh/Ist:0,88 - 0,3? (Anlage)  - 0,7 (Haus) = -0,1kWh = -1%
#             Fazit: 1700 SOC: 63-1=62% --> es fehlen 23% bis Soll (85)
#             1700-0900: 16h / 2/3 vom Durchschnittsverbrauch des Hauses: 2,7kWh sind 27%
#             Annahme: bis 0900 sinkt der SOC auf 35% - wird knapp --> eigentlich kann sofort geladen werden
#             Ist 16.6. 0900: 43% , war also zu pessimistisch
#                   grau, keine Sonne, Prognose trotzdem 3kWh?? Batterien müssen geladen und ausgeglichen werden -->Paneele aus, MPII über Generator auf "Laden"
#          Neue Durchschnittswerte
#          Istwerte: Arbeitstag Homeoffice: 15.6. 0930-1630: 7h 1kWh Verbrauch 0,143kWh/h   SOC: 54-->65: +11%=1,1kWh Summe: 2,2kWh
#                     Abend/Nacht Grundlast: 15.6. 1630-16.6.0613 13h45 1,8kWh Verbrauch  0,131 kWh/h
#
#  Ausführung des Scripts
#     stündlich zur Minute 55
#        Beispiel: Start um 8 Uhr 55 
#           --> aktuelle Zählerstände werden dann für die nächste volle Stunde eingetragen, also 09:00
#           --> als Schaltzeit wird auch die nächste volle Stunde angenommen
#        als cronjob laufen lassen
#        http://www.raspberrypi-tutorials.de/software/cronjobs-auf-dem-raspberry-pi-erstelleneinrichten.html
#        sudo crontab -e
#        5 * * * * root /home/pi/mpIIAcOnOff.py
#
#
# Erledigt, ins Handbuch zu übernehmen
#    warum lädt der MPII nur mit 5A statt mit 40? Begrenzung, weil Generator? Nee, weil im MPII so eingestellt (egen Batterieeinzelladung...), aber nicht im Cerbo sichtbar!
#
#    warum funktioniert ssh über python nicht: Windows-Berechtigungsproblem bei system32\openssh Lösung: Verzeichnis nach e:\ verschoben
#    wie kann man den mppt über modbus-service com.victronenergy.solarcharger abfragen? mit ssh-spy den instanzierten Servicenamen ermitteln (+ttyS7....)
#    
#    MPPT-gesamtertrag mit in die victron-Tabelle speichern
#
#    Wie lange muss der SOC bei 100% gehalten werden, damit alle Batterien/Zellen ausgeglichen sind? Eine Stunde scheint auszureichen
#
#    MPPT-Gesamtertrag ermitteln mit MQTT
#     https://community.victronenergy.com/questions/63915/anyone-have-python-example-how-to-read-mqtt-values.html
#    zweite getrennte DB-Verbindung/Transaktion für das Log
#    Hilfsklasse für gpio unter Windows

# Offene Punkte:
#  bei Scriptabbruch Warn-Email verschicken
#  wieso wird der Anlagenverbrauch negativ?

#  raspi io-, cm4- und pci-Boards
#     Stromkabel mit J19 oder J20 Stecker fehlt noch 
#
#  Victron/Gavazzi-Zähler
#     erl. einbauen
#     erl. mit Cerbo verbinden
#     erl. Werte abfragen und in die DB-Speichern
#     erl. in den Auswertungen berücksichtigen
#
#  raspi-ioboard mit cm4 in Betrieb nehmen
#     rasp os lite installieren
#     feste IP in der Fritzbox hinterlegen
#     remotezugang installieren
#     samba installieren
#     sata karte mit 2TB-Platte in Betrieb nehmen
#     ssh Schlüssel erstellen und im Cerbo hinterlegen
#     mariadb installieren
#        mariadb sichern
#     python mit mariadb, gpio inst.
#  relaisboard in Betriebnehmen und verdrahten
#     pin26 - relais 1, schaltet 12VDC zum Stromstoßschalter
#     pin22 - 3,3VDC verbinden mit KM12
#  python-Scripte in Betrieb nehmen und testen
#     als stündlichen Cronjob eintragen
#
#  bessere Passwortverschlüsselung?


import os
import base64
import ctypes
import datetime
import subprocess
import logging
from logging.handlers import RotatingFileHandler
import json
from tokenize import Double
from xmlrpc.client import DateTime
import mariadb
import time

# ist unter Windows logischerweise nicht ausführbar (keine GPIO-Pins...)
# import RPi.GPIO as GPIO 
# für den Test unter windows liegt eine Hilfsklasse gleichen Namens in gpio.py:
from gpioersatz import GPIO


###### CPrognoseStunde { ##############################################################################
class CPrognoseStunde:
   def __init__(self, tNow, Stunde):

      self.tStunde = datetime.datetime(tNow.year,tNow.month,  tNow.day, tNow.hour+1) + datetime.timedelta(hours=Stunde)
      self.dVerbrauch  = 0.0  # Summe der Verbrauchswerte aus Tabelle t_tagesprofil
      self.dSolarPrognose  = 0.0  # Wert aus Tabelle t_prognose
      self.dSoc = 0.0   # auf Basis des aktuellen SOC, der voraussichtlichen Verbrauchswerte und der Solarvorhersage berechneter Wert


###### CLetzteStunde  { ##############################################################################
class CLetzteStunde:
   # Werte der letzten Stunde aus t_victdbus_stunde
   def __init__(self):
      self.tStunde = datetime.datetime(2022,1,1)
      
      #Absolutwerte der letzten Stunde
      self.dSoc = 0.0    # Batterie-SOC
      self.dErtrag = 0.0 # Solarertrag aus dem MPPT
      self.dEmL1  = 0.0  # Zähler EM540/L1
      self.dEmL2  = 0.0  # Zähler EM540/L2

      #Differenz der aktuellen Werte zu denen der letzten Stunde
      self.dSocDiff = 0.0    
      self.dErtragDiff = 0.0 
      self.dEmL1Diff  = 0.0  
      self.dEmL2Diff  = 0.0  
      

###### CAcOnOff  { ##############################################################################
class CAcOnOff:

   ###### __init__(self) ##############################################################################
   def __init__(self):
      print("Programmstart")

      # Konfiguration einlesen
      logging.basicConfig(encoding='utf-8', level=logging.DEBUG,
                          style='{', datefmt='%Y-%m-%d %H:%M:%S', format='{asctime} {levelname} {filename}:{lineno}: {message}',
                          handlers=[RotatingFileHandler('./mpIIAcOnOff.log', maxBytes=100000, backupCount=10)],)

      self.tNow = datetime.datetime.now()
      tZaehler = self.tNow + datetime.timedelta(hours=1)
      self.tZaehler = datetime.datetime( tZaehler.year, tZaehler.month, tZaehler.day, tZaehler.hour, 0)
      self.nZaehlerStunde = self.tZaehler.hour
      self.sZaehlerStunde = self.sHour2Str(self.tZaehler) 
      self.tLeer = datetime.datetime(2022,1,1)

      print(f'Jetzt: {self.tNow}, Zähler: {self.tZaehler}, Zählerstunde: {self.nZaehlerStunde}, Leer: {self.tLeer}')


      sCfgFile = "mpIIAcOnOff.cfg" # sFile = "E:\\dev_priv\\python_svn\\solarprognose1\\webreq1\\mpIIAcOnOff.cfg"
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
         self.sGefahrenstufe =  Settings['Allgemein']['Gefahrenstufe']
         self.sGefahrenstufeNormal =  Settings['Kommentare und Wertebereiche']['Gefahrenstufe_normal']
         self.sGefahrenstufeBrown =  Settings['Kommentare und Wertebereiche']['Gefahrenstufe_brown']
         self.sGefahrenstufeBlack =  Settings['Kommentare und Wertebereiche']['Gefahrenstufe_black']

         self.sLadeartAus =  Settings['Kommentare und Wertebereiche']['Ladeart_aus']
         self.sLadeartAusgleichen =  Settings['Kommentare und Wertebereiche']['Ladeart_ausgleichen']
         self.sLadeartNachladen =  Settings['Kommentare und Wertebereiche']['Ladeart_nachladen']

         self.sSchaltart_ein  =  Settings['Kommentare und Wertebereiche']['Schaltart_ein']
         self.sSchaltart_aus  =  Settings['Kommentare und Wertebereiche']['Schaltart_aus']

         self.nVerbotVon = Settings['Laden']['VerbotVon']
         self.nVerbotBis = Settings['Laden']['VerbotBis']
         self.dMinSolarPrognoseStunde = Settings['Laden']['MinSolarPrognoseStunde']

         self.nAusgleichAlleNWochen = Settings['Laden']['AusgleichAlleNWochen']
         self.dAbsorb100Dauer = float(Settings['Laden']['DauerAbsorbtion100'])

         self.nSocMin = Settings['Laden']['SocMin']
         self.nSocMax = Settings['Laden']['SocMax']
         self.nSocAbsorbtion = Settings['Laden']['SocAbsorbtion']
                                 
         self.nBattAnz = Settings['Laden']['BatterieAnzahl']
         self.nBattKapa = Settings['Laden']['BatterieKapa']
         self.nBattVolt = Settings['Laden']['BatterieSpannung']
         self.nMaxChargeCurr = Settings['Laden']['MaxLadestrom']
      
         self.dConsum = Settings['Laden']['NormalVerbrauch24']
         self.dEigenverbrauch = Settings['Laden']['EigenverbrauchAnlage24']

         self.SshCerboIP = Settings['Ssh']['CerboIP']
         self.SshCerboUser = Settings['Ssh']['CerboUser']
         self.SshDbusTempFile = Settings['Ssh']['DbusTempFile']
         self.SshDbusSolarServiceName  = Settings['Ssh']['DbusSolarServiceName']
         self.SshDbusEmServiceName  = Settings['Ssh']['DbusEmServiceName']

         self.iGpioPinActorAc = Settings['Gpio']['PinActorAc']
         self.iGpioPinSensorAc = Settings['Gpio']['PinSensorAc']
         self.sGpioPinEin = Settings['Kommentare und Wertebereiche']['Gpio_ein']
         self.sGpioPinAus = Settings['Kommentare und Wertebereiche']['Gpio_aus']
         self.sGpioPinUnklar = Settings['Kommentare und Wertebereiche']['Gpio_unklar']
 

         self.MariaIp = Settings['MariaDb']['IP']
         self.MariaUser = Settings['MariaDb']['User']
         sPwdCode = Settings['MariaDb']['PwdCode']

         self.MariaPwd = base64.b64decode(sPwdCode).decode("utf-8")

      except Exception as e:
         logging.error(f'Fehler beim Einlesen von: {sCfgFile}: {e}')
         quit()

      #berechnete Werte      
      self.dSoc = 0.0               # aktueller SOC aus der Anlage, abgefragt per dbus
      self.dErtragAbs = 0.0         # aktueller Gesamt-Solarertrag, abgefragt per dbus
      self.dEmL1Abs = 0.0           # aktueller Zählerstand EM540/L1, abgefragt per dbus
      self.dEmL2Abs = 0.0           # aktueller Zählerstand EM540/L2, abgefragt per dbus

      self.ls = CLetzteStunde()     # Soc, Ertrag, L1 und L2 der letzten Stunde aus t_victdbus_stunde
      
      self.sLadeart = ''            # None/Aus, Voll, Nach

      self.sAcSensor = ''
      
      self.tEin = self.tLeer
      self.tAus = self.tLeer
      self.tLetzterAusgleich = self.tLeer  # Zeitpunkt, wann der letzte Ausgleich abgeschlossen war

      self.nAnzStunden = 0 # Basis für die Durchschnittsberechnung im Tagesprofil

      self.a48h = [CPrognoseStunde(self.tNow, h) for h in range(48)]


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
   def __Record2Log(self, eTyp, eLadeart, sText):
   # Logeintrag in die Datenbank schreiben, bei Fehler auch in die Log-Datei
   #$$ stext auf 250 begrenzen, wenn länger -->Fehlermeldung und Text in die Logdatei
      cur = self.mdbLog.cursor()
      sStmt = f'insert into db1.t_charge_log (tLog, eTyp, eLadeart,sText) values (sysdate(), "{eTyp}","{eLadeart}","{sText}")'
      try:
         cur.execute( sStmt)
         self.mdbLog.commit()
         print(f'Logeintrag: {eTyp}: {eLadeart}: {sText}')

      except Exception as e:
         logging.error(f'Fehler beim insert ({eTyp},{eLadeart},{sText}) in mariadb.DB1.t_charge_log: {e}')
         self.vScriptAbbruch()


   ###### Info2Log(self, sText) ##############################################################################
   def Info2Log(self, sText):
      self.__Record2Log( "info", "", sText)


   ###### Error2Log(self, sText) ##############################################################################
   def Error2Log(self, sText):
      self.__Record2Log( "error", "", sText)


   ###### State2Log(self, eLadeart, sText) ##############################################################################
   def State2Log(self, eLadeart, sText):
      self.__Record2Log( "info", eLadeart, sText)


   ###### dSoc2Kwh(self, dSocDiff) ##############################################################################
   def dSoc2Kwh(self, dSocDiff):
         dKapa100 = self.nBattAnz * self.nBattKapa * self.nBattVolt / 1000 # Juni 2023: 4*50Ah*50V/1000 = 10kWh
         dSoc100 = 100.0
         dKapaDiff = round( dSocDiff * dKapa100 / dSoc100,2)
         return dKapaDiff


   ###### dKwh2Soc(self, dKapaDiff) ##############################################################################
   def dKwh2Soc(self, dKapaDiff):
         dKapa100 = self.nBattAnz * self.nBattKapa * self.nBattVolt / 1000 # Juni 2023: 4*50Ah*50V/1000 = 10kWh
         dSoc100 = 100.0
         dSocDiff = round(dKapaDiff * dSoc100 / dKapa100,2)
         return dSocDiff


   ###### sHour2Str( self, t) ##############################################################################
   # DateTime bis einschließlich Stunde in DB-Update/STR_TO_DATE-kompatible Zeichenkette umwandeln
   def sHour2Str( self, t):
        return f'{t.year}-{t.month}-{t.day} {t.hour}'
     

   ###### HoleDbusWertVomCerbo(self, sService, sPath) ##############################################################################
 #    :string sService: Name des Victron-dbus-Dienstes, ermittelt mit dbus-spy oder dbus -y
 #    :string sPath: Pfadname des Wertes aus https://github.com/victronenergy/venus/wiki/dbus
 #    SSH-Verbindung aufbauen und über Victron-Dbus folgende Werte abfragen:
 #     - den aktuellen SOC
 #     - den Gesamt-Solarertrag
 #    Achtung! der SOC steht über den system-Dienst zur Verfügung. Aber der Ertrag muss lt. Doku beim Dienst solarcharger abgefragt werden
 #            Diesen Dienst gibt es aber nicht!
 #              -->  dbus-spy oder dbus -y verwenden --> es werden die instanzierten Dienstnamen angezeigt, s.B solarcharger.ttyS7
 #     V1: https://www.photovoltaikforum.com/thread/148690-einfaches-php-beispiel-zum-auslesen-der-victron-vrm-echtzeit-daten/?pageNo=2
 #          https://www.victronenergy.com/live/ccgx:root_access
 #            https://github.com/victronenergy/venus/wiki/dbus
 #    vollständige Liste: https://github.com/victronenergy/dbus_modbustcp/blob/master/attributes.csv
 #     putty  und dann dbus -y com.victronenergy.system /Dc/Battery/Soc GetValue
 #      oder gleich so mit dem per ssh-keygen erzeugten Schlüsseldatei leno2venus: 
 #              C:\Users\Rainer>ssh -i leno2venus root@192.168.2.38 "dbus -y com.victronenergy.system /Dc/Battery/Soc GetValue"
 #               59
 #        dafür wurde auf dem Client (leno2018) ein ssh-Schlüsselpaar erzeugt und der öffentliche Schlüssel aus der pub-Datei 
 #           auf dem Cerbo in  root@einstein:~# nano ~/.ssh/authorized_keys  eingetragen
 #           habe dann noch ein Schlüsselpaar l2v erzeugt und mitssh-add registriert. Danach konnte ich ssh auch ohne -i ausführen.
   def HoleDbusWertVomCerbo(self, sService, sPath): 
          
      try:
         sDbusCmd = f'dbus -y {sService} {sPath} GetValue'

         #das Verzeichnis openssh musste von system32 nach e': kopiert werden, weil python/ssh darauf nicht zufgreifen können
         sSshCmd = f'e:\\dev_priv\\openssh\\ssh {self.SshCerboUser}@{self.SshCerboIP} "{sDbusCmd}">{self.SshDbusTempFile}'

         subprocess.Popen( sSshCmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
         try:
            f = open(self.SshDbusTempFile, "r")
            aLines = f.readlines()
            sLine = aLines[0]
            f.close()
         except Exception as e:
            self.Error2Log( f'Fehler beim Lesen von {sPath} aus der temp. Datei {self.SshDbusTempFile}: {e}')
            return ""
         sValue = sLine.replace("\r", "")
         sValue = sValue.replace("\n", "")
         sValue = sValue.replace("value =", "")

      except Exception as e:
         self.Error2Log( f'Fehler beim Lesen SSH/DBUS: {e}')
         return ""
         
      self.Info2Log(f'SSH/DBUS: {sService} {sPath}: {sValue}')
      return sValue


   ###### HoleDbusWerteVomCerbo(self) ##############################################################################
   def HoleDbusWerteVomCerbo(self): 
      self.dSoc = round(float(self.HoleDbusWertVomCerbo( "com.victronenergy.system", "/Dc/Battery/Soc")),2) 

      #Gesamt-Solarertrag aus dem MPPT-Solarregler
      self.dErtragAbs = round(float(self.HoleDbusWertVomCerbo( self.SshDbusSolarServiceName, "/Yield/System")),2)
      
      #Gesamtverbrauch aller Verbraucher im Solarteil der Hausinstallation (ohne Eigenverbrauch der Anlage)
      # gezählt wird alles, was aus dem Inverter kommt, egal ob aus der Batterie oder nur durchgeschleifter Stadtstrom beim Nachladen oder Ausgleichen
      self.dEmL1Abs = round(float(self.HoleDbusWertVomCerbo( self.SshDbusEmServiceName, "/Ac/L1/Energy/Forward")),2)

      # gezählt wird am MPII-AC-In, was an Stadtstrom reingeht, um die Batterie zu laden und während des Ladens alle Verbraucher im Solarteil der Hausinstallation zu versorgen
      self.dEmL2Abs = round(float(self.HoleDbusWertVomCerbo( self.SshDbusEmServiceName, "/Ac/L2/Energy/Forward")),2)
      

   ###### HoleLadeartAusDb(self) ##############################################################################
   def HoleLadeartAusDb(self):
      try:
         sStmt = f'select eLadeart, tLetzterAusgleich, nAnzStunden from db1.t_charge_state'
         cur = self.mdb.cursor()
         cur.execute( sStmt)
         rec = cur.fetchone()
         if rec == None:
            self.Error2Log(f'Fehler bei select eLadeart from mariadb.DB1.t_charge_state: rec == None')
            self.vScriptAbbruch()

         sArt = rec[0].replace("\r\n","",1)
         self.tLetzterAusgleich = rec[1]
         self.nAnzStunden = rec[2] + 1

         cur.close()

         if sArt == self.sLadeartAus or sArt == self.sLadeartAusgleichen or sArt == self.sLadeartNachladen:
            self.sLadeart = sArt
         else:
            self.Error2Log(f'Fehler beim Lesen der eLadeart from mariadb.DB1.t_charge_state: Unbekannte Ladeart: {sArt}')
            self.vScriptAbbruch()

         if self.tLetzterAusgleich == None:
            self.Error2Log(f'Fehler: t_charge_state.tLetzterAusgleich noch nicht initialisiert.')
            self.vScriptAbbruch()

         self.Info2Log(f'Ladeart: {self.sLadeart}')

      except Exception as e:
         self.Error2Log(f'Fehler bei select eLadeart from mariadb.DB1.t_charge_state: {e}')
         self.vScriptAbbruch()


   ###### HoleLetzteStundeAusDb(self) ##############################################################################
   def HoleLetzteStundeAusDb(self):

      try:
         self.ls.dSoc = self.dSoc
         self.ls.dErtrag = self.dErtragAbs
         self.ls.dEmL1 = self.dEmL1Abs
         self.ls.dEmL2 = self.dEmL2Abs
         self.ls.dKapaDiff = 0.0
         self.ls.dErtragDiff  = 0.0
         self.ls.dHausDiff  = 0.0
         self.ls.dStadtDiff  = 0.0

         cur = self.mdb.cursor()
         sStmt = f"select max(tStunde) from db1.t_victdbus_stunde WHERE tStunde <> STR_TO_DATE('{self.sZaehlerStunde}', '%Y-%m-%d %H')"
         cur.execute( sStmt)
         rec = cur.fetchone()
         if rec == None:
            self.ls.tStunde = self.tZaehler
         else: 
            self.ls.tStunde = rec[0]

         sLetzteStunde = self.sHour2Str(self.ls.tStunde)
         
         sStmt = f"select dSocAbs, dErtragAbs, dEmL1Abs, dEmL2Abs from db1.t_victdbus_stunde where tStunde = STR_TO_DATE('{sLetzteStunde}', '%Y-%m-%d %H')"
         cur.execute( sStmt)
         rec = cur.fetchone()
         if rec == None:
            self.Error2Log(f'Fehler beim Lesen der Zählerstände der letzten Stunde ausdb1.t_victdbus_stunde: rec==none')
            return

         self.ls.dSoc      = rec[0] 
         self.ls.dErtrag   = rec[1] 
         self.ls.dEmL1     = rec[2] 
         self.ls.dEmL2     = rec[3] 
         cur.close()

         #wenn der letzte Datensatz nicht von der letzten Stunde stammt, dann den Durchschnitt der letzten Stunden annehmen
         tDiff = self.tZaehler - self.ls.tStunde
         iStunden = (int)((tDiff.days * 86400 + tDiff.seconds) / 3600)

         self.ls.dSocDiff = round( (self.dSoc - self.ls.dSoc) / iStunden, 2)           # positiv: Batterie wurde geladen, negativ: Batterie wurde entladen
         self.ls.dErtragDiff = round((self.dErtragAbs - self.ls.dErtrag) / iStunden, 2)
         self.ls.dEmL1Diff = round((self.dEmL1Abs - self.ls.dEmL1) / iStunden, 2)
         self.ls.dEmL2Diff = round((self.dEmL2Abs - self.ls.dEmL2) / iStunden, 2)

      except Exception as e:
         self.Error2Log(f'Fehler beim Lesen der Zählerstände der letzten Stunde ausdb1.t_victdbus_stunde: {e}')


   ###### BerechneLadungsEnde(self, dSocSoll) ##############################################################################
   def BerechneLadungsEnde(self, dSocSoll):
      if self.nMaxChargeCurr == 0.0:
         self.Error2Log(f'Fehler bei select eLadeart from mariadb.DB1.t_charge_state: {e}')
         self.vScriptAbbruch()

      # Berechnung in Abhängigkeit von Anzahl Batterien, Ah der Batterien, SOC, Ladestrom und Eigenverbrauch
      nKapa100 = self.nBattAnz * self.nBattKapa # Juni 2023: 4*50Ah = 200Ah
      dGapProz = dSocSoll - self.dSoc # Lücke in % 22.6.23 1400 100-70=30%
      dGapAh = (float(nKapa100) * dGapProz) / 100.0
      dStunden = dGapAh / float(self.nMaxChargeCurr) # Juni 2023: Ladestrom 20A --> 60 / 20 = 3h
      
      #Eigenverbrauch vereinfacht dazunehmen, ohne die Verlängerung iterativ xmal zu berücksichtigen
      dEigenStundekWh = self.dEigenverbrauch / 24
      dEigenkWh =  dEigenStundekWh * dStunden
      dEigenAh = dEigenkWh / float(self.nBattVolt) # 50V angenommen
      dEigenStunden = dEigenAh / float(self.nMaxChargeCurr)

      tDau = datetime.timedelta(hours= int(dStunden + dEigenStunden) + 1)
      tEnde = self.tEin + tDau
      self.Info2Log(f'Berechnetes Ladungsende: {tEnde}')
      return tEnde


   ###### BerechneAusschaltzeitpunkt(self, tSollEnde) ##############################################################################
   def BerechneAusschaltzeitpunkt(self, tSollEnde):
      # von tEin bis tSollEnde prüfen, ob mit Solarertrag zu rechnen ist
      # dabei nicht mit den Verbotszeiten (self.nVerbotVon,self.nVerbotBis) arbeiten, sondern die Prognosetabelle abfragen

      sVon = self.sHour2Str(self.tEin)
      sBis = self.sHour2Str(tSollEnde)

      sStmt = f"select stunde,p1,p3,p6,p12,p24 from db1.t_prognose where Stunde BETWEEN  STR_TO_DATE('{sVon}', '%Y-%m-%d %H') AND STR_TO_DATE('{sBis}', '%Y-%m-%d %H')\
                     order by stunde"

      cur = self.mdb.cursor()
      try:
         cur.execute( sStmt)
         rec = cur.fetchone()
         if rec == None:
            self.Info2Log(f'Keine Prognosedaten gefunden in t_prognose für {sVon} bis {sBis}')
            self.tAus = tSollEnde # keine Einschränkung durch die Solarprognose
            return True           # es darf geladen werden

         while rec != None:
            dProg = 0.0
            for i in range(1,5+1):
               if rec[i] != None:
                  dProg = rec[i]
                  break

            if dProg > self.dMinSolarPrognoseStunde:               
               self.tAus = rec[0] # Einschränkung durch die Solarprognose
               if self.tEin == self.tAus:
                  self.Info2Log(f'Einschränkung durch die Solarprognose: es darf nicht geladen werden')
                  return False # es darf nicht geladen werden
               else:
                  self.Info2Log(f'Einschränkung durch die Solarprognose: es darf nur bis {self.tAus} geladen werden')
                  return True # es darf geladen werden
            else:
               rec = cur.fetchone()

         self.tAus = tSollEnde # keine Einschränkung für das Laden durch die Solarprognose
         self.Info2Log(f'Es darf geladen werden: Keine Einschränkung durch die Solarprognose')
         cur.close()
         return True           # es darf geladen werden

      except Exception as e:
         cur.close()
         self.Error2Log(f'Fehler beim Lesen der Prognosedaten aus t_prognose für {sVon} bis {sVon}: {e}')
         self.Info2Log(f'Es wird ohne Prognosedaten gerechnet und geladen')
         self.tAus = tSollEnde # keine Einschränkung durch die Solarprognose
         return True # es darf geladen werden


   ###### bIstAusgleichenNoetigUndMoeglich(self) ##############################################################################
   def bIstAusgleichenNoetigUndMoeglich(self):
      print(f'bIstAusgleichenNoetigUndMoeglich')
      diff = self.tNow - self.tLetzterAusgleich 
      if diff.days < self.nAusgleichAlleNWochen * 7 :
         return False # Ausgleich ist nicht nötig

      # Einschalten zur nächsten vollen Stunde
      self.tEin = self.tZaehler

      # Wie lange wird das Ausgleichen dauern? 
      tSollEnde = self.BerechneLadungsEnde( dSocSoll=100.0)

      # Ist Ausgleichen möglich? Ausgleichen ist verboten in Stunden, wo der Ertrag laut Prognose größer als 0,1kWh/h sein soll
      # D.h. prüfen: Wann kommt diese nächste Sonnenstunde? Ab da ist kein Laden möglich
      self.tAus = self.tLeer
      if self.BerechneAusschaltzeitpunkt(tSollEnde) == False:
         return False
      else:
         return True


   ###### LadenEinschalten(self, sLadeart ) ##############################################################################
   def LadenEinschalten(self, sLadeart ):
      # ein Ticket in t_charge_ticket eintragen, das Schalten übernimmt das Script mpIIAcOnOff.py/SchalteGpio()
      # ohne Rücksicht auf noch nicht abgearbeitete Tickets

      try:
         self.sLadeart = sLadeart

         sVonStunde = self.sHour2Str(self.tEin)
         sBisStunde = self.sHour2Str(self.tAus)

         sStmt = "insert into db1.t_charge_ticket (eSchaltart, tAnlDat, tSoll, sGrund, tSollAus)\
                   values ( '{0}', sysdate(), STR_TO_DATE('{1}', '%Y-%m-%d %H'), '{3}', STR_TO_DATE('{2}', '%Y-%m-%d %H') )"
         sStmt = sStmt.format( self.sSchaltart_ein,  sVonStunde, sBisStunde, self.sLadeart)

         cur = self.mdb.cursor()
         cur.execute( sStmt)
         cur.close()

         self.Info2Log(f'Schalt-Ticket in t_charge_ticket eingetragen: {self.sSchaltart_ein}, {self.sLadeart}, Ein: {sVonStunde}, Aus: {sBisStunde}')

      except Exception as e:
         self.Error2Log(f'Fehler beim insert in mariadb.DB1.t_charge_ticket mit ({self.sSchaltart_ein}, {self.sLadeart}, Ein: {sVonStunde}, Aus: {sBisStunde}): {e}')
         self.vScriptAbbruch()


   ###### LadenAusschalten(self) ##############################################################################
   def LadenAusschalten(self, sLadeart ):
      # ein Ticket in t_charge_ticket eintragen, das Schalten übernimmt das Script mpIIAcOnOff.py/SchalteGpio()
      # ohne Rücksicht auf noch nicht abgearbeitete Tickets

      try:
         self.sLadeart = self.sLadeartAus

         sAusStunde = self.sHour2Str(self.tZaehler)

         sStmt = "insert into db1.t_charge_ticket (eSchaltart, tAnlDat, tSoll )\
                   values ( '{0}', sysdate(), STR_TO_DATE('{1}', '%Y-%m-%d %H'))"
         sStmt = sStmt.format( self.sSchaltart_aus,  sAusStunde)

         cur = self.mdb.cursor()
         cur.execute( sStmt)
         cur.close()

         self.Info2Log(f'Schalt-Ticket in t_charge_ticket eingetragen: {self.sSchaltart_aus}, {self.sLadeart}, Aus: {sAusStunde}')

         if sLadeart == self.sLadeartAusgleichen:
            self.tLetzterAusgleich = self.tZaehler

      except Exception as e:
         self.Error2Log(f'Fehler beim insert in mariadb.DB1.t_charge_ticket mit ({self.sSchaltart_aus}, {self.sLadeart}, Aus: {sAusStunde}): {e}')
         self.vScriptAbbruch()


   ###### TagesprofilEinlesen(self, a24h) ##############################################################################
   def TagesprofilEinlesen(self, a24h):
         
         try:
            sStmt = f'select nStunde, dKwhHaus, dKwhanlage from db1.t_tagesprofil'
            cur = self.mdb.cursor()
            cur.execute( sStmt)

            rec = cur.fetchone()
            if rec == None:
               self.Error2Log(f'Kein Tagesprofil gefunden in t_tagesprofil')
               self.vScriptAbbruch()
            t = 0
            while rec != None:
               a24h[t] = rec[1] + rec[2]
               rec = cur.fetchone()
               t = t + 1
            cur.close()
   
         except Exception as e:
            self.Error2Log(f'Fehler in TagesprofilEinlesen(): {e}')


   ###### TagesprofilAktualisieren(self) ##############################################################################
   def TagesprofilAktualisieren(self):

         try:
            sStmt = f'select dKwhHaus,dKwhHausMin,dKwhHausMax, dKwhAnlage,dKwhAnlageMin,dKwhAnlageMax from db1.t_tagesprofil where nStunde = {self.nZaehlerStunde}'

            cur = self.mdb.cursor()
            cur.execute( sStmt)
            rec = cur.fetchone()

            # Haus-Verbrauchswerte können direkt vom EM540/L1 abgelesen werden:
            dKwhHaus = rec[0]
            dKwhHaus = round(( (self.nAnzStunden  * dKwhHaus) + self.ls.dEmL1Diff ) / (self.nAnzStunden + 1),2) # neuer Durchschnitt

            dKwhHausMin = rec[1]
            if self.ls.dEmL1Diff < dKwhHausMin and 0.0 < self.ls.dEmL1Diff:
               dKwhHausMin = round(self.ls.dEmL1Diff,2) # neuer Minwert

            dKwhHausMax = rec[2]
            if self.ls.dEmL1Diff > dKwhHausMax:
               dKwhHausMax = round(self.ls.dEmL1Diff,2) # neuer Maxwert

            # Verbrauchswerte der Anlage müssen erst  berechnet werden:
            # V1 kein Stadtstrom, reiner Wechselrichterbetrieb:   Anlagenverbrauch = Solarertrag - ((+)Hausverbrauch(L1) + (+/-)Batterie)
            # V2 Stadtstrom:                                      Anlagenverbrauch = ( Stadtstrom(L2) + Solarertrag ) - ( (+)Hausverbrauch(L1) + (+)Batterie )
            # Fazit: es genügt eine Formel: 
            #                                                     Anlagenverbrauch = ( Stadtstrom(L2) + Solarertrag ) - ( (+)Hausverbrauch(L1) + (+/-)Batterie )
            # Batterie-kWh muss aus SOC abgeleitet werden: 100% == 10kWh
            dKapaDiff = self.dSoc2Kwh(self.ls.dSocDiff)

            dEigen = (self.ls.dEmL2Diff + self.ls.dErtragDiff) - (self.ls.dEmL1Diff +  dKapaDiff)

            # dann erst neuen Durchschnitt und Min/Max neu berechnen
            dKwhAnlage = rec[3]
            dKwhAnlage = round(( (self.nAnzStunden  * dKwhAnlage) + dEigen) / (self.nAnzStunden + 1),2) # neuer Durchschnitt

            dKwhAnlageMin = rec[4]
            if dEigen < dKwhAnlageMin and 0.0 < dEigen:
               dKwhAnlageMin = round(dEigen,2) # neuer Minwert

            dKwhAnlageMax = rec[5]
            if dEigen < dKwhAnlageMax:
               dKwhAnlageMax = round(dEigen,2) # neuer Maxwert

            sStmt = f'update db1.t_tagesprofil set dKwhHaus={dKwhHaus},dKwhAnlage={dKwhAnlage},dKwhHausMin={dKwhHausMin},dKwhHausMax={dKwhHausMax},dKwhAnlageMin={dKwhAnlageMin},dKwhAnlageMax={dKwhAnlageMax}  where nStunde = {self.nZaehlerStunde}'
            cur.execute( sStmt)
            self.mdb.commit()
            cur.close()

         except Exception as e:
            self.Error2Log(f'Fehler in TagesprofilAktualisieren(): {e}')
         

   ###### SolarprognoseEinlesen(self) ##############################################################################
   def SolarprognoseEinlesen(self):

         try:
            sVon = self.sHour2Str(self.tEin)
            tEnd = self.tEin + datetime.timedelta(hours=48)
            sBis = self.sHour2Str(tEnd)
            sStmt = f"select stunde,p1,p3,p6,p12,p24 from db1.t_prognose where Stunde BETWEEN  STR_TO_DATE('{sVon}', '%Y-%m-%d %H') AND STR_TO_DATE('{sBis}', '%Y-%m-%d %H')\
                        order by stunde"

            cur = self.mdb.cursor()
            cur.execute( sStmt)
            rec = cur.fetchone()
            if rec == None:
               self.Info2Log(f'Fehler in SolarprognoseEinlesen(): Keine Prognosedaten gefunden in t_prognose für {sVon} bis {sBis}')
               return False

            while rec != None:
               dProg = 0.0
               for i in range(1,5+1):
                  if rec[i] != None:
                     dProg = rec[i]
                     break  
               tProgn = rec[0]
               tDiff = rec[0] - self.tEin
               iStunde = (int)((tDiff.days * 86400 + tDiff.seconds) / 3600)

               if iStunde < 48:
                  #print(f'Stunde: {iStunde}, Prognose: {dProg}')
                  self.a48h[iStunde].dSolarPrognose = dProg

               rec = cur.fetchone()
            cur.close()
            return True

         except Exception as e:
            self.Error2Log(f'Fehler in SolarprognoseEinlesen(): {e}')
         cur.close()
         return False


   ###### BerechneMaximaleSocUnterschreitung(self) ##############################################################################
   def BerechneMaximaleSocUnterschreitung(self):
      print('BerechneMaximaleSocUnterschreitung()')

      try:
         self.SolarprognoseEinlesen()  # Solarprognose einlesen, direkt nach a48h

         a24h = [0.0 for h in range(24)]
         self.TagesprofilEinlesen( a24h)

         # Tagesprofil ins 48h-Profil übertragen
         h48 = 0
         for h in range( self.tEin.hour, 23+1):
            #print(f'h48: {h48}, h: {h}, a24h[h]: {a24h[h]}')
            self.a48h[h48].dVerbrauch = a24h[h]
            h48 = h48 + 1
         for h in range( 0, 23+1):
            #print(f'h48: {h48}, h: {h}, a24h[h]: {a24h[h]}')
            self.a48h[h48].dVerbrauch = a24h[h]
            h48 = h48 + 1
         for h in range( 0, self.tEin.hour):
            #print(f'h48: {h48}, h: {h}, a24h[h]: {a24h[h]}')
            self.a48h[h48].dVerbrauch = a24h[h]
            h48 = h48 + 1

         # SOC-Prognose berechnen
         dKapa100 = self.nBattAnz * self.nBattKapa * self.nBattVolt / 1000 # Juni 2023: 4*50Ah*50V/1000 = 10kWh
         dSoc100 = 100.0
         dSocPrognose = self.dSoc
         dMaxSocUnterschreitung = 0.0
         for h in range( 48):
            dKapaDiff = self.a48h[h].dSolarPrognose - self.a48h[h].dVerbrauch
            dSocDiff = dKapaDiff * dSoc100 / dKapa100

            #$$ bei 89% beginnt Absorbtion, es gibt noch kein Modell für die Ladekurve in diesem Bereich
            dSocPrognose = min( float(self.nSocAbsorbtion), dSocPrognose + dSocDiff)

            self.a48h[h].dSoc = dSocPrognose
            print(f'a48h[{h}]: {self.a48h[h].tStunde}:  {self.a48h[h].dSoc}')

            if( self.a48h[h].dSoc < float(self.nSocMin)):
               dMaxSocUnterschreitung = float(self.nSocMin) - self.a48h[h].dSoc

      except Exception as e:
         self.Error2Log(f'Fehler in BerechneMaximaleSocUnterschreitung(): {e}')
         self.vScriptAbbruch()

      return dMaxSocUnterschreitung


   ###### bIstLadenNoetigUndMoeglich(self) ##############################################################################
   def bIstLadenNoetigUndMoeglich(self):
      print(f'bIstLadenNoetigUndMoeglich')

      if self.dSoc < float(self.nSocMin):
         return True # Nachladen nötig, wenn dann noch Sonne dazukommt, wird das toleriert

      # Einschalten zur nächsten vollen Stunde
      self.tEin = datetime.datetime(self.tNow.year,self.tNow.month,self.tNow.day,self.tNow.hour+1,0)

      # 48h-Vektor anlegen und füllen: 48 x Verbrauch(t_tagesprofil) + Solarertrag(t_prognose) + SOC(berechnet)
      # dabei die maximale Unterschreitung des SOCMin ermitteln und zurückliefern
      dSocMaxUnter = self.BerechneMaximaleSocUnterschreitung()

      if self.a48h[0].dSoc < float(self.nSocMin):
         self.Info2Log(f'Nachladen nötig, weil die untere SOC-Grenze innerhalb der nächsten Stunde unterschritten würde: {self.a48h[0].dSoc} < {self.nSocMin}')
         return True 

      if dSocMaxUnter == 0.0:
         self.Info2Log(f'Nachladen nicht nötig, weil die untere SOC-Grenze innerhalb der nächsten 48 Stunden nicht unterschritten wird')
         return False 

      self.Info2Log(f'Nachladen nötig, weil die untere SOC-Grenze innerhalb der nächsten 48 Stunden unterschritten würde: {self.nSocMin} --> {dSocMaxUnter}')

      # Wie lange wird das Nachladen dauern? 
      tSollEnde = self.BerechneLadungsEnde( dSocSoll=self.dSoc + dSocMaxUnter)

      # Laden ist verboten in Stunden, wo der Ertrag laut Prognose größer als 0,1kWh/h sein soll
      # D.h. prüfen: Wann kommt diese nächste Sonnenstunde? Ab da ist kein Laden möglich
      self.tAus = self.tLeer
      if self.BerechneAusschaltzeitpunkt(tSollEnde) == False:
         return False
      else:
         return True

      return False


   ###### bIstAusgleichenAusschaltenMoeglich(self) ##############################################################################
   # Möglich, wenn SOC mindestens <dAbsorb100Dauer> Stunden bei 100% war
   def bIstAusgleichenAusschaltenMoeglich(self):
      print("bIstAusgleichenAusschaltenMoeglich")

      try:
         cur = self.mdb.cursor()
         tVon = self.tZaehler - datetime.timedelta(hours=self.dAbsorb100Dauer)
         sVon = self.sHour2Str(tVon)
         sBis = self.sHour2Str(self.tZaehler)

         sStmt = f"SELECT MIN(s.dSocAbs) FROM db1.t_victdbus_stunde s WHERE s.tStunde BETWEEN STR_TO_DATE('{sVon}', '%Y-%m-%d %H') AND STR_TO_DATE('{sBis}', '%Y-%m-%d %H')"
         cur.execute( sStmt)
         rec = cur.fetchone()
         dSocMin = rec[0]
         cur.close()

         if rec == None:
            self.Error2Log(f'Fehler in bIstAusgleichenAusschaltenMoeglich: es kann nicht ermittelt werden, wie lange der SOC bei 100% war. Ausgleichen wird trotzdem ausgeschaltet.')
            return True

         if dSocMin < 100.0:
            self.Info2Log(f'Noch nicht lange genug ausgeglichen. Ausgleichsladen bleibt eingeschaltet')
            return False

         self.Info2Log(f'Ausgleichsladen kann ausgeschaltet werden')
         return True

      except Exception as e:
         self.Error2Log(f'Ausnahme in bIstAusgleichenAusschaltenMoeglich(): {e}. Ausgleichen wird trotzdem ausgeschaltet.')
      return True


   ###### bIstLadenAusschaltenMoeglichOderNoetig( self) ##############################################################################
   # Möglich, wenn SOC ausreichend hoch
   # Nötig, wenn Solarertrag zu erwarten ist
   def bIstLadenAusschaltenMoeglichOderNoetig( self):
      print("bIstLadenAusschaltenMoeglichOderNoetig")

      if self.bIstLadenNoetigUndMoeglich() == True:
         self.Info2Log(f'Nachladen wird nicht ausgeschaltet, weil bIstLadenNoetigUndMoeglich() == True')
         return False

      self.Info2Log(f'Nachladen kann ausgeschaltet werden')
      return True


   ###### SchreibeDbusWerteInMariaDb(self) ##############################################################################
   def SchreibeDbusWerteInMariaDb(self):
      
      try:
         sStmt = "insert into db1.t_victdbus_stunde (tStunde, dSocAbs, dSoc, dErtragAbs, dErtrag, dEmL1, dEmL2, dEmL1Abs, dEmL2Abs)\
                   values (STR_TO_DATE('{0}', '%Y-%m-%d %H'), {1}, {2}, {3}, {4}, {5}, {6}, {7}, {8}  ) \
                   ON DUPLICATE KEY UPDATE  dSocAbs={1}, dSoc={2}, dErtragAbs={3}, dErtrag={4}, dEmL1={5}, dEmL2={6}, dEmL1Abs={7}, dEmL2Abs={8}"
         sStmt = sStmt.format(self.sZaehlerStunde, self.dSoc, self.ls.dSocDiff, self.dErtragAbs, self.ls.dErtragDiff, self.ls.dEmL1Diff, self.ls.dEmL2Diff, self.dEmL1Abs, self.dEmL2Abs)

         cur = self.mdb.cursor()
         cur.execute( sStmt)
         self.mdb.commit()
         cur.close()
   
         self.Info2Log(f'Dbus-Werte in DB aktualisiert: {self.dSoc}, {self.dErtragAbs}, {self.dEmL1Abs}, {self.dEmL2Abs}')

      except Exception as e:
         self.Error2Log(f'Fehler beim insert inmariadb.DB1.t_victdbus_stunde mit {self.dSoc}, {self.dErtragAbs}, {self.dEmL1Abs}, {self.dEmL2Abs}: {e}')
         self.vScriptAbbruch()
         

   ###### HoleGpioStatus(self, iPin, bMitInit) ##############################################################################
   def HoleGpioStatus(self, iPin, bMitInit):
      # abfragen, in welchem Zustand sich der KM12-Sensor am Stromstoßschalter befindet und mit Ladeart aus DB vergleichen
      # ist unter Windows nicht ausführbar!
      try:
         if bMitInit:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.iGpioPinSensorAc, GPIO.IN)
      
         iStat1 = GPIO.input(self.iGpioPinSensorAc); time.sleep(0.3) 
         iStat2 = GPIO.input(self.iGpioPinSensorAc); time.sleep(0.3) 
         iStat3 = GPIO.input(self.iGpioPinSensorAc); 

         if bMitInit:
            GPIO.cleanup()

         sPinStat = ''
         if iStat1 == iStat2 and iStat1 == iStat3:
            if iStat1 == 1:
               sPinStat = self.sGpioPinEin;
            elif iStat1 == 0:
               sPinStat = self.sGpioPinAus;
            else:
               sPinStat = self.sGpioPinUnklar;
            print(f'Pin {self.iGpioPinSensorAc} hat Wert {iStat1}-->{sPinStat}')
            return sPinStat
         else:
            self.Error2Log(f'GPIO-Status Pin {self.iGpioPinSensorAc} nicht eindeutig:  Versuch1: {iStat1}, Versuch2: {iStat2}, Versuch3: {iStat3},')
         self.vScriptAbbruch()

      except Exception as e:
         self.Error2Log(f'Fehler in HoleGpioStatus(): {e}')
#$$      self.vScriptAbbruch()
         return -1


   ###### HoleUndTesteGpioStatus(self) ##############################################################################
   def HoleUndTesteGpioStatus(self):
   # abfragen, in welchem Zustand sich der KM12-Sensor am Stromstoßschalter befindet und mit Ladeart aus DB vergleichen

      self.sAcSensor = self.HoleGpioStatus( self.iGpioPinSensorAc, bMitInit=True)

      if (self.sAcSensor == self.sGpioPinEin and (self.sLadeart == self.sLadeartAusgleichen or self.sLadeart == self.sLadeartNachladen)) \
         or (self.sAcSensor == self.sGpioPinAus and (self.sLadeart == self.sLadeartAus)):
         print(f'GPIO-Status Pin {self.iGpioPinSensorAc} stimmt mit aktueller Ladeart überein: GPIO: {self.sAcSensor}, Ladeart: {self.sLadeart}')

      else:
         self.Error2Log(f'Status ({self.sAcSensor}) GPIO-Pin {self.iGpioPinSensorAc} passt nicht zur Ladeart: {self.sLadeart}')
       

   ###### GpioSendeSchaltimpuls(self, sEinAus) ##############################################################################
   def GpioSendeSchaltimpuls(self, sEinAus):

      #https://projects.raspberrypi.org/en/projects/physical-computing/1
      # ist unter Windows nicht ausführbar!
      try:
         GPIO.setmode(GPIO.BCM)
         GPIO.setup(self.iGpioPinSensorAc, GPIO.IN) # hier nur das Sensor-Pin initialisieren, das Actor-Pin wird unten erledigt

         v = 1
         bErledigt = False
         sPinStat = self.sGpioPinUnklar
         while v <= 3:

            if v == 1:
               GPIO.setup(self.iGpioPinActorAc, GPIO.OUT) #schaltet das Relais bereits ein (anders als das China-8-Kanal-Board)
            else:
               GPIO.output(self.iGpioPinActorAc, GPIO.HIGH)
            time.sleep(0.2) # 200ms reichen aus, um einen 12VDC-Eltako-Stromstoßschalter umzuschalten
            GPIO.output(self.iGpioPinActorAc, GPIO.LOW)
      
            time.sleep(0.5) # warten, bis der Stromstoßschalter umgeschaltet hat
            sPinStat = self.HoleGpioStatus( self.iGpioPinSensorAc, bMitInit=False)
            if sEinAus == self.sSchaltart_ein and sPinStat == self.sGpioPinEin\
               or sEinAus == self.sSchaltart_aus and sPinStat == self.sGpioPinAus:
               bErledigt = True
               break;

         GPIO.cleanup()

         if bErledigt == True:
            self.Info2Log(f'Neuer Status Stromstoßschalter/Pin {self.iGpioPinSensorAc}: {sPinStat}')
         else:
            self.Error2Log(f'Fehler in GpioSendeSchaltimpuls(): Falscher Status des Stromstoßschalters: Soll: {sEinAus}, Ist: {sPinStat}')
            self.vScriptAbbruch()

      except Exception as e:
         self.Error2Log(f'Fehler in GpioSendeSchaltimpuls():  {e}')
         self.vScriptAbbruch()


   ###### SchalteGpio(self) ##############################################################################
   def SchalteGpio(self):

      if self.sLadeart == self.sLadeartAusgleichen or  self.sLadeart == self.sLadeartNachladen:
         if self.sAcSensor == self.sSchaltart_ein:
            self.Info2Log(f'Keine GPIO-Änderung, AC ist bereits eingeschaltet')
         else:
            self.GpioSendeSchaltimpuls(self.sSchaltart_ein)
      
      elif self.sLadeart == self.sLadeartAus:
         if self.sAcSensor == self.sSchaltart_aus:
            self.Info2Log(f'Keine GPIO-Änderung, AC ist bereits ausgeschaltet')
         else:
            self.GpioSendeSchaltimpuls(self.sSchaltart_aus)

      else:
         self.Error2Log(f'Fehler in SchalteGpio: Unbekannte Ladeart: {self.sLadeart}:  {e}')
         self.vScriptAbbruch()


   ###### BerechneEinAus(self) ##############################################################################
   def BerechneEinAus(self):

      if ac.sLadeart == ac.sLadeartAus:
         if ac.bIstAusgleichenNoetigUndMoeglich():           
            ac.LadenEinschalten( self.sLadeartAusgleichen )
         else:
            if ac.bIstLadenNoetigUndMoeglich():
               ac.LadenEinschalten( self.sLadeartNachladen )

      elif ac.sLadeart == ac.sLadeartAusgleichen:    
         if ac.bIstAusgleichenAusschaltenMoeglich():
            ac.LadenAusschalten(self.sLadeartAusgleichen)
          
      elif ac.sLadeart == ac.sLadeartNachladen:    
         if ac.bIstLadenAusschaltenMoeglichOderNoetig():
            ac.LadenAusschalten(self.sLadeartNachladen)

      else:
           self.Error2Log(f'Fehler: Unbekannte Ladeart: {ac.sLadeart}')

   ###### SchreibeStatusInMariaDb(self) ##############################################################################
   def SchreibeStatusInMariaDb(self):

      try:
         sLetzterAusgleich = self.sHour2Str( self.tLetzterAusgleich)

         sStmt = f"update db1.t_charge_state set eLadeart='{self.sLadeart}', tAendDat=sysdate() , nAnzStunden={self.nAnzStunden},\
                                                tLetzterAusgleich=STR_TO_DATE('{sLetzterAusgleich}', '%Y-%m-%d %H')"

         cur = self.mdb.cursor()
         cur.execute( sStmt)
         cur.close()

      except Exception as e:
         self.Error2Log(f'Fehler beim update von mariadb.DB1.t_charge_state mit ({self.sLadeart}): {e}')
         self.vScriptAbbruch()


###### CAcOnOff  } ##############################################################################

ac = CAcOnOff()                    # Konfigdatei lesen 

ac.VerbindeMitMariaDb()                   # Verbindung zur DB herstellen, zweite Verbindung fürs Log

ac.HoleDbusWerteVomCerbo()                # Werte aus der Anlage lesen   
ac.HoleLadeartAusDb()                     # In welchem Zustand ist das Ladegerät?
ac.HoleLetzteStundeAusDb()                # Zählerständer der letzten Stunde für Differenzermittlung lesen
ac.TagesprofilAktualisieren()             # aktuelle Zählerwerte in die passende Stunde des Tagesprofil schreiben, hat eigenes Commit
ac.SchreibeDbusWerteInMariaDb()           # hat eigenes Commit

ac.HoleUndTesteGpioStatus()               # über GPIO abfragen, in welchem Zustand sich der KM12-Sensor am Stromstoßschalter befindet
                                          # und mit DB-Status vergleichen

#Alles in einer Transaktion:
ac.BerechneEinAus()                       # Prüfen, ob ausgeglichen oder nachgeladen oder ausgeschaltet werden muss und Zeitpunkte berechnen
ac.SchalteGpio()                          # Gpio-Pin schalten und Ergebnis prüfen
ac.SchreibeStatusInMariaDb()
ac.mdb.commit()
ac.Info2Log(f'DB aktualisiert: {ac.sLadeart}')

ac.vEndeNormal()





