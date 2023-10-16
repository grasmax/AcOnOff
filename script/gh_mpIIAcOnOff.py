#   Ziel:    Nachladen oder Ausgleichen der Solar-Puffer-Batterien in Abhängigkeit vom Batterie-State of Charge (SOC, Batterieladezustand),
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
#             Nachladen/Ausgleichen
#             Unterscheiden: Nachladen(bis 90%) von Ausgleichsladen: ausreichend lange 100%, bis alle Batterien und -Zellen ausgeglichen sind
#
#             Im Normalfall:
#             Für den lt. Prognose zu erwartender Solar-Ertrag muss Kapa in der Batterie freigehalten werden.
#             Ausgleichs- und Nachladen nur dann, wenn laut Solar-Prognose nicht mehr als 0,1kWh/h zu erwarten sind.
#             Wenn das Ausgleichsladen begonnen hat, wird aber keine Rücksicht auf den eventuell zu erwartenden Solarertrag genommen.
#             Das Nachladen wird aber abgebrochen, wenn Solarertrag zu erwarten ist.
#             Der SOC wird beim Nachladen zwischen 22 und 85 Prozent gehalten.
#             (Wenn der SOC unter 20% fällt, sichert die Generatorregel im Victron CerboGX-Steuergerät das Einschalten des Ladestroms.)
#             Die Anzahl der Ein- und Ausschaltvorgänge soll minimiert werden, um die Schütze zu schonen.
#             Das Nachladen soll im Idealfall nur nachts stattfinden, wenn nur die Grundlast (Kühlung, Heizung, Fritzbox) gebraucht wird.
#             Die Prognose soll mit den historischen Verbrauchs-Werten rechnen, die im Tagesprofil (Tabelle t_tagesprofil) gespeichert sind.
#             Oktober 2023: Das Tagesprofil ist nun monatsgenau und speichert auch den Maximalwert des Solarertrags in dieser Stunde des Monats für
#             die Beschattungsberechnung. Mit der Beschattungsberechnung wird tagesgenau der Zeitbereich berechnet, in dem die von Meteoblue
#             gelieferten Werte bei der Schaltprognose berücksicht werden.
#
#             Ablauf einer Berechnung:
#                 + Prüfen, ob Jetzt in Stunde mit Solarertrag:
#                 +    Ja: Nachladen nur dann einschalten, wenn die untere SOC-Grenze in der nächsten Stunde unterschritten würde
#                 +    Nein: 
#                 +        Array {self.nAnzPrognoseStunden} x3 anlegen für {self.nAnzPrognoseStunden} Stunden, jeweils: Verbrauch (kWh), Solarertrag (kWh), SOC
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
#  
#       - SchalteGpio() schaltet ein Relais1 auf dem Raspi-Relayboard 
#       - Relais 1 schaltet 12 VDC durch zu einem Stromstoßschalter. 
#         Der Stromstoßschalter schaltet 48VDC durch zum Klemmmenblock 3 im Verteilerkasten Solar
#         Dadurch schaltet der Schütz im Verteilerkasten Solar 230 VAC durch zu AC-IN des MultiplusII.
#         Dadurch schaltet der MultiplusII das Ladegerät ein und versorgt alle an AC-Out1 angeschlossenen Verbraucher mit Stadtstrom.
#       - Der Schaltzustand des Stromstoßschalters wird erfasst mit einem KM12-Sensor, der seinerseits im eingeschalteten Zustand 3 VDC zu einem GPIO-Pin schaltet, das
#         von HoleUndTesteGpioStatus() überwacht wird.
#
#        Das ursprüngliche Konzept sah ein weiteres Script vor, dass das GPIO-Pins schalten sollte und über Tickets von hier aus getriggert werden sollte.
#        Dabei ging ich davon aus, dass das GPIO-Pin solange auf high gehalten werden muss, wie der Leistungsschütz eingeschaltet sein soll.
#        Dafür hätte das Script für die Dauer des Ladevorgangs laufen müssen. Und das Relais hätte 48VDC schalten müssen, es ist aber nur für 30 VDC zugelassen.
#        Das aktuelle Konzept sieht deshalb einen zusätzlichen Stromstoßschalter vor, der über das Relais auf dem Raspi-Board mit 12 VDC angesteuert wird.
#        Dazu ist nur ein 0.2 ms-Impuls nötig; das Relais wird geschont und das Script muss nicht dauerhaft laufen. 
#        Das Schalten des GPIO-Pin 20 kann also hier gleich mit erledigt werden. (Pin 26 getestet in der Alarmanlage)
#        An den Stromstoßschalter ist ein KM12-Modul angedockt, das den Schaltzustand anzeigt. 
#        Dieser Schaltzustand wird über GPIO-Pin 22 abgefragt (mit 3,3 VDC an Pin 22 schon an der Alarmanlage getestet)
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
#       Das berechnete Profil für die Berechnung: für die nächsten {self.nAnzPrognoseStunden} Stunden: {self.nAnzPrognoseStunden} Datensätze, jeweils mit Durchschnittsverbrauch (Haus und Anlage), Solarprognose, SOC
#
#          Randbedingungen der Anlage:
#             SOC: 100% entsprechen 200Ah (4*50Ah)
#             in einer Stunde kann die Batteriekapa mit einem Ladestrom von 230VAC/9,5A (per Konfig und Kabel vorgegeben, entsprechen ca. 50VDC/40A, das sind 40Ah)
#                 16.6.23: Ladestrom war im MPII auf 5A begrenzt...auf 20A erhöht, kommt auch an...         
#                   -->20A/h SOC kann pro Stunde um 10% erhöht werden
#                Ladedauer von 20% auf 85%: 65% / 10% : 6,5h
#             Durchschnittlicher Verbrauch in 24h: 4kWh = 40%
#
#          Umsetzung:
#             stündlich prüfen in Minute 55
#             Beispiel: Start des SCripts um 8 Uhr 55 
#               --> aktuelle Zählerstände werden dann für die nächste volle Stunde eingetragen, also 09:00
#               --> als Schaltzeit wird auch die nächste volle Stunde angenommen
#
#             aktuellen SOC, Prognose-Ertrag und historischen Verbrauch betrachten
#             damit den Verlauf für die nächsten {self.nAnzPrognoseStunden} Stunden berechnen
#             Laden einschalten, wenn der SOC in den nächsten {self.nAnzPrognoseStunden} Stunden unter 22% fallen sollte --> Parallelverschiebung der Kurve nach oben
#             Ausschalten, wenn die {self.nAnzPrognoseStunden}-Stunden Kurve nicht mehr unter 22% fällt oder mit Solarertrag gerechnet werden kann.
#
#          Beispielrechnung 0900:
#             maximal möglicher Brutto-Solarertrag lt Prognose: 5kWh 
#                   minus Eigenverbrauch der Anlage von 1kWh, bleiben: 4kWh
#                   minus Sofortverbrauch im Haus von 1kWh, bleiben: 3kWh = 30% Netto-Solarertrag
#       
#          Beispielrechnung 1700:
#             1700: SOC: 85%
#             1700-0900: 16h / 2/3 vom Durchschnittsverbrauch des Hauses: 2,7kWh sind 27%
#             Fazit: bis 0900 sinkt der SOC auf 58% 
#
#          Beispielrechnung 14.6.,1300: 
#              SOC: 66%, Prognose: 2,9kWh - 0,58 (Anlage)  - 0,7 (Haus) = ~1,6kWh = 16%
#             Fazit: 1700 SOC: 66+16=82% 
#
#          Beispielrechnung 15.6.,1500: 
#             SOC: 63%, Ymppt=256kWh Prognose: 0,97kWh/Ist:0,88 - 0,3? (Anlage)  - 0,7 (Haus) = -0,1kWh = -1%
#             Fazit: 1700 SOC: 63-1=62% 

#          Neue Durchschnittswerte
#          Istwerte: Arbeitstag Homeoffice: 15.6. 0930-1630: 7h 1kWh Verbrauch 0,143kWh/h   SOC: 54-->65: +11%=1,1kWh Summe: 2,2kWh
#                     Abend/Nacht Grundlast: 15.6. 1630-16.6.0613 13h45 1,8kWh Verbrauch  0,131 kWh/h
#
#  Ausführung der beiden Scripts (dieses und das für die Beschaffung der Prognose)
#        als cronjob (des angemeldeten Users, nicht root!) laufen lassen
#        http://www.raspberrypi-tutorials.de/software/cronjobs-auf-dem-raspberry-pi-erstelleneinrichten.html
#        crontab -e
#
#        # von 8-20 Uhr in Minute 50 das Prognose-Script ausfuehren
#        50 8-20 * * * sh /mnt/wd2tb/script/meteoblue_forecast/mb_pvpro.sh
#
#        # stuendlich in Minute 55 das Schaltscript ausfuehren
#        55 * * * * sh /mnt/wd2tb/script/mpIIaconoff/mpIIAcOnOff.sh
#
#


import base64
import datetime
import subprocess
import logging
from logging.handlers import RotatingFileHandler
import json
import mariadb
import time

# ist unter Windows logischerweise nicht ausführbar (keine GPIO-Pins...)
#import RPi.GPIO as GPIO 
# für den Test unter windows liegt eine Hilfsklasse gleichen Namens in gpioersatz.py:
from gpioersatz import GPIO
# für den Relaistest stehen die beiden Scriptdateien gpiorelaytest*.py zur Verfügung
# Die GPIO-IN-Pins können mit dem Script in gpiointest.py abgefragt werden

###### CPrognoseStunde { ##############################################################################
class CPrognoseStunde:
   def __init__(self, tStart, Stunde):

      self.tStunde = datetime.datetime(tStart.year,tStart.month,  tStart.day, tStart.hour) + datetime.timedelta(hours=Stunde)
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
      self.dAnlagenVerbrauch = 0.0

      #Differenz der aktuellen Werte zu denen der letzten Stunde
      self.dSocDiff = 0.0    
      self.dErtragDiff = 0.0 
      self.dEmL1Diff  = 0.0  
      self.dEmL2Diff  = 0.0  
      

###### CAcOnOff  { ##############################################################################
class CAcOnOff:

   ###### setup_logger ##############################################################################
   # Idee aus https://stackoverflow.com/questions/11232230/logging-to-two-files-with-different-settings, leicht erweitert auf rotating und um vernüftige Formatierung
   def setup_logger(self, logger_name, log_file, level=logging.INFO):
      try:
         l = logging.getLogger(logger_name)

         fileHandler = RotatingFileHandler(log_file, maxBytes=100000, backupCount=10, encoding='utf-8')

         formatter = logging.Formatter(style='{',datefmt='%Y-%m-%d %H:%M:%S', fmt='{asctime} {levelname} {filename}:{lineno}: {message}')
         fileHandler.setFormatter(formatter)

         streamHandler = logging.StreamHandler()
         streamHandler.setFormatter(formatter)

         l.setLevel(level)
         l.addHandler(fileHandler)
         l.addHandler(streamHandler)  

      except Exception as e:
         self.log.error(f'Fehler in json.load(): {e}')
         quit()



   ###### __init__(self) ##############################################################################
   def __init__(self):

      # Logging: dieses Script wird per sh gerufen, der gesamte Output der Scriptausführung, einschließlich
      # streamHandler und print wird in einer Textdatei mit dem Zeitstempel der Ausführung gesammelt
      # Gelogggt wird eigentlich in die MariaDb.
      # Das Datei war gedacht für den Fall, dass es Probleme mit dem Verbindungsaufbau zur MariaDB gibt.
      # Es hat sich aber herausgestellt, dass man von einem Mobilgerät (Handy..) einfacher auf eine Textdatei,
      # als auf eine Datenbank zugreifen kann. Deswegen werden alle Logeinträge auch in eine Textdatei geschrieben.
      # Ab Oktober 2023 werden auch die Schalttickets zusätzlich in eine Textdatei geschrieben.
      # Detaillierte Daten, die nur temporär wichtig sind, werden nur mit print ausgegeben.

      # 2 Logdateien anlegen, Dateiendung txt, damit das Öffnen in Chrome möglich wird
      self.setup_logger('log1', './log/mpIIAcOnOff.txt')
      self.setup_logger('log2', './log/mpIIAcOnOffTicket.txt')
      self.log = logging.getLogger('log1')
      self.log4Tickets = logging.getLogger('log2')
      
      self.log.info('Programmstart')


      # Zählerstunde initialisieren
      self.tNow = datetime.datetime.now()
      # Debughilfe: 
      #self.tNow = datetime.datetime( 2023,9,21,23, 55)

      tZaehler = self.tNow + datetime.timedelta(hours=1)
      self.tZaehler = datetime.datetime( tZaehler.year, tZaehler.month, tZaehler.day, tZaehler.hour, 0)
      self.nZaehlerStunde = self.tZaehler.hour # 00:00 hat Zählerstunde 0, muss vor Zugriff auf t_tagesprofil auf 24 gesetzt werden
      self.sZaehlerStunde = self.sDate2Str(self.tZaehler) 
      self.tLeer = datetime.datetime(2022,1,1)
      self.nMonat = tZaehler.month


      sJetzt = f'Jetzt: {self.tNow}, Zähler: {self.tZaehler}, Zählerstunde: {self.nZaehlerStunde}, Leer: {self.tLeer}'
      self.log.info( sJetzt)

      # Konfiguration einlesen
      sCfgFile = "mpIIAcOnOff.cfg" # sFile = "E:\\dev_priv\\python_svn\\solarprognose1\\webreq1\\mpIIAcOnOff.cfg"
      try:
         f = open(sCfgFile, "r")
      except Exception as e:
         self.log.error(f'Fehler in open({sCfgFile}): {e}')
         quit()

      try:
         Settings = json.load(f)
         f.close()
      except Exception as e:
         self.log.error(f'Fehler in json.load(): {e}')
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
         if self.nVerbotVon < self.nVerbotBis:
            self.tVerbotVon = datetime.datetime( self.tNow.year, self.tNow.month, self.tNow.day, self.nVerbotVon, 0)
            self.tVerbotBis = datetime.datetime( self.tNow.year, self.tNow.month, self.tNow.day, self.nVerbotBis, 0)
            self.tVerbotVon2 = self.tLeer
            self.tVerbotBis2 = self.tLeer
         else:
            self.tVerbotVon = datetime.datetime( self.tNow.year, self.tNow.month, self.tNow.day, 0, 0)
            self.tVerbotBis = datetime.datetime( self.tNow.year, self.tNow.month, self.tNow.day, self.nVerbotBis, 0)
            self.tVerbotVon2 = datetime.datetime( self.tNow.year, self.tNow.month, self.tNow.day, self.nVerbotVon, 0)
            self.tVerbotBis2 = datetime.datetime( self.tNow.year, self.tNow.month, self.tNow.day, 23, 0)
            self.tVerbotBis2 = self.tVerbotBis2 + datetime.timedelta( hours=1)

         self.nAnzPrognoseStunden = Settings['Laden']['AnzPrognoseStunden']
         self.dMinSolarPrognoseStunde = Settings['Laden']['MinSolarPrognoseStunde']

         self.nAusgleichAlleNWochen = Settings['Laden']['AusgleichAlleNWochen']
         self.dAusgleichStunden = float(Settings['Laden']['AusgleichStundenAbsorbtion100'])

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
         self.SshCmd = Settings['Ssh']['SshCmd']
         self.SshDbusTempFile = Settings['Ssh']['DbusTempFile']
         self.SshDbusSolarServiceName  = Settings['Ssh']['DbusSolarServiceName']
         self.SshDbusEmServiceName  = Settings['Ssh']['DbusEmServiceName']
         self.SshDbusBattServiceName  = Settings['Ssh']['DbusBattServiceName']

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
         self.log.error(f'Fehler beim Einlesen von: {sCfgFile}: {e}')
         quit()

      #berechnete Werte initialisieren     

      self.bMitHypoSocRechnen = False     # wenn die aktuellen Werte nicht per ssh/dbus aus dem Cerbo gelesen werden konnten, mit einem hyp. SOC weiterrechnen
      self.dSoc = 0.0               # aktueller SOC aus der Anlage, abgefragt per dbus
      self.dErtragAbs = 0.0         # aktueller Gesamt-Solarertrag, abgefragt per dbus
      self.dEmL1Abs = 0.0           # aktueller Zählerstand EM540/L1, abgefragt per dbus
      self.dEmL2Abs = 0.0           # aktueller Zählerstand EM540/L2, abgefragt per dbus
      self.sMinCellV = 0.0          # minimale Zellspannung, abgefragt per dbus
      self.sMaxCellV = 0.0          # maximale Zellspannung, abgefragt per dbus
      self.sMinCellT = 0.0          # minimale Zelltemperatur, abgefragt per dbus
      self.sMaxCellT = 0.0          # maximale Zelltemperatur, abgefragt per dbus
      self.sMinCellVCellId = ""     # Batterie-ID der minimale Zellspannung, abgefragt per dbus
      self.sMaxCellVCellId = ""     # Batterie-ID der maximale Zellspannung, abgefragt per dbus
      self.sMinCellTCellId = ""     # Batterie-ID der minimale Zelltemperatur, abgefragt per dbus
      self.sMaxCellTCellId = ""     # Batterie-ID der maximale Zelltemperatur, abgefragt per dbus


      self.nAnzStunden = 0 # Basis für die Durchschnittsberechnung im Tagesprofil

      self.ls = CLetzteStunde()     # Soc, Ertrag, L1 und L2 der letzten Stunde aus t_victdbus_stunde
      
      self.sLadeart = ''            # None/Aus, Voll, Nach

      self.sAcSensor = ''
      
      self.tEin = self.tLeer
      self.tAus = self.tLeer
      self.tLetzterAusgleich = self.tLeer  # Zeitpunkt, wann der letzte Ausgleich abgeschlossen war

      self.nAnzPrognoseStunden += 1 # weil auf [0] nur der aktuelle SOC liegt
      self.aProgStd = [CPrognoseStunde(self.tZaehler, h) for h in range(self.nAnzPrognoseStunden)]

   
   ###### WerteInsLog(self) ##############################################################################
   # Wichtige Werte ins Log schreiben
   def WerteInsLog(self):

      self.Info2Log(f'Untere SOC-Grenze: {self.nSocMin} %')
      self.Info2Log(f'AusgleichAlleNWochen: {self.nAusgleichAlleNWochen} Wochen')
      self.Info2Log(f'AusgleichStundenAbsorbtion100: {self.dAusgleichStunden} Stunden')


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
            self.log.error(f'Fehler in mariadb.connect(): {e}')

         try:
            self.mdbLog = mariadb.connect( host=self.MariaIp, port=3306,user=self.MariaUser, password=self.MariaPwd)
            bConnLog = True

         except Exception as e:
            self.log.error(f'Fehler in mariadb.connect() fürs Logging: {e}')

         if bConnLog == True and bConn == True:
            break
         time.sleep(2)

      if bConnLog != True or bConn != True:
         self.log.error(f'Fehler in VerbindeMitMariaDb(): Conn: {bConn}, ConnLog: {bConnLog}')
         self.vScriptAbbruch()


      # ab hier Logging in die MariaDb-Tabelle t_charge_log
      self.Info2Log('mdb-connect ok')


   ###### vEndeNormal(self) ##############################################################################
   def vEndeNormal(self):
   #Script beenden und aufräumen
      self.Info2Log('mdb-close')
      self.mdb.close()
      self.mdbLog.close()
      self.log.info("Programmende")


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
      cur = self.mdbLog.cursor()
      sStmt = f'insert into solar2023.t_charge_log (tLog, eTyp, eLadeart,sText) values (sysdate(), "{eTyp}","{eLadeart}","{sText}")'
      try:
         cur.execute( sStmt)
         self.mdbLog.commit()
         sOut = f'Logeintrag: {eTyp}: {eLadeart}: {sText}'
         self.log.info(sOut)
         print(sOut)
         

      except Exception as e:
         self.log.error(f'Fehler beim insert ({eTyp},{eLadeart},{sText}) in t_charge_log: {e}')
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


   ###### sDate2Str( self, t) ##############################################################################
   # DateTime bis einschließlich Stunde in DB-Update/STR_TO_DATE-kompatible Zeichenkette umwandeln
   def sDate2Str( self, t, bMinSec=False):
      if bMinSec == False:
        return f'{t.year}-{t.month}-{t.day} {t.hour}'
      else:
        return f'{t.year}-{t.month}-{t.day} {t.hour}:{t.minute}:{t.second}'
     

   def iGetHours( self, dau):
      return (int)((dau.days * 86400 + dau.seconds) / 3600)



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
 #        Windows-PC: dafür wurde auf dem Client (leno2018) ein ssh-Schlüsselpaar erzeugt und der öffentliche Schlüssel aus der pub-Datei 
 #           auf dem Cerbo in  root@einstein:~# nano ~/.ssh/authorized_keys  eingetragen
 #           habe dann noch ein Schlüsselpaar l2v erzeugt und mitssh-add registriert. Danach konnte ich ssh auch ohne -i ausführen.
 #       Solar-Raspi: Schlüsselpaar mit ssh-keygen auf dem Raspi erzeugt
 #           Schlüssel aus \\192.168.2.28\SambaHome\admin2\sshkey_solarraspi.pub eingetragen im Cerbo mit
 #              root@einstein:~# nano ~/.ssh/authorized_keys
            
   def HoleDbusWertVomCerbo(self, sService, sPath): 
          
      try:
         sDbusCmd = f'dbus -y {sService} {sPath} GetValue'

         #Windows: das Verzeichnis openssh musste von system32 nach e': kopiert werden, weil python/ssh darauf nicht zufgreifen können
         sSshCmd = f'{self.SshCmd} {self.SshCerboUser}@{self.SshCerboIP} "{sDbusCmd}">{self.SshDbusTempFile}'

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
         self.Error2Log( f'Fehler beim Lesen SSH/DBUS: {sService} {sPath}: {e}')
         return ""
         
      self.Info2Log(f'SSH/DBUS: {sService} {sPath}: {sValue}')
      return sValue


   ###### HoleDbusWerteVomCerbo(self) ##############################################################################
   # Werte aus der Anlage lesen, wenn das nicht möglich ist, die Prognose ab dem letzten bekannten SOC rechnen
   def HoleDbusWerteVomCerbo(self): 
      
      try:
         sSoc = self.HoleDbusWertVomCerbo( "com.victronenergy.system", "/Dc/Battery/Soc")
         if len(sSoc) <= 0:
            self.bMitHypoSocRechnen = True
            self.Error2Log( f'Fehler beim Lesen SSH/DBUS - Prognose wird mit dem letzten bekannten Wert für SOC gerechnet.')
         else:
            self.dSoc = round(float(sSoc),2) 

         #Gesamt-Solarertrag aus dem MPPT-Solarregler
         sY = self.HoleDbusWertVomCerbo( self.SshDbusSolarServiceName, "/Yield/System")
         if len(sY) <= 0:
            self.bMitHypoSocRechnen = True
            self.Error2Log( f'Fehler beim Lesen SSH/DBUS - Prognose wird mit dem letzten bekannten Wert für Ertrag gerechnet.')
         else:
            self.dErtragAbs = round(float(sY),2)
      
         #Gesamtverbrauch aller Verbraucher im Solarteil der Hausinstallation (ohne Eigenverbrauch der Anlage)
         # gezählt wird alles, was aus dem Inverter kommt, egal ob aus der Batterie oder nur durchgeschleifter Stadtstrom beim Nachladen oder Ausgleichen
         sL1 = self.HoleDbusWertVomCerbo( self.SshDbusEmServiceName, "/Ac/L1/Energy/Forward")
         if len(sL1) <= 0:
            self.bMitHypoSocRechnen = True
            self.Error2Log( f'Fehler beim Lesen SSH/DBUS - Prognose wird mit dem letzten bekannten Wert für L1 gerechnet.')
         else:
            self.dEmL1Abs = round(float(sL1),2)

         # gezählt wird am MPII-AC-In, was an Stadtstrom reingeht, um die Batterie zu laden und während des Ladens alle Verbraucher im Solarteil der Hausinstallation zu versorgen
         sL2 = self.HoleDbusWertVomCerbo( self.SshDbusEmServiceName, "/Ac/L2/Energy/Forward")
         if len(sL2) <= 0:
            self.bMitHypoSocRechnen = True
            self.Error2Log( f'Fehler beim Lesen SSH/DBUS - Prognose wird mit dem letzten bekannten Wert für L2 gerechnet.')
         else:
            self.dEmL2Abs = round(float(sL2),2)


         sMinCellV = self.HoleDbusWertVomCerbo( self.SshDbusBattServiceName, "/System/MinCellVoltage")
         if len(sMinCellV) <= 0:
            self.Error2Log( f'Fehler beim Lesen SSH/DBUS/MinCellVoltage.')
         else:
            self.sMinCellV = round(float(sMinCellV),2)

         sMaxCellV = self.HoleDbusWertVomCerbo( self.SshDbusBattServiceName, "/System/MaxCellVoltage")
         if len(sMaxCellV) <= 0:
            self.Error2Log( f'Fehler beim Lesen SSH/DBUS/MaxCellVoltage.')
         else:
            self.sMaxCellV = round(float(sMaxCellV),2)

         sMinCellT = self.HoleDbusWertVomCerbo( self.SshDbusBattServiceName, "/System/MinCellTemperature")
         if len(sMinCellT) <= 0:
            self.Error2Log( f'Fehler beim Lesen SSH/DBUS/MinCellTemperature.')
         else:
            self.sMinCellT = round(float(sMinCellT),2)

         sMaxCellT = self.HoleDbusWertVomCerbo( self.SshDbusBattServiceName, "/System/MaxCellTemperature")
         if len(sMaxCellT) <= 0:
            self.Error2Log( f'Fehler beim Lesen SSH/DBUS/MaxCellTemperature.')
         else:
            self.sMaxCellT = round(float(sMaxCellT),2)

         sVal = self.HoleDbusWertVomCerbo( self.SshDbusBattServiceName, "/System/MinVoltageCellId")
         if len(sVal) <= 0:
            self.Error2Log( f'Fehler beim Lesen SSH/DBUS/MinVoltageCellId.')
         else:
            self.sMinCellVCellId = sVal

         sVal = self.HoleDbusWertVomCerbo( self.SshDbusBattServiceName, "/System/MaxVoltageCellId")
         if len(sVal) <= 0:
            self.Error2Log( f'Fehler beim Lesen SSH/DBUS/MaxVoltageCellId.')
         else:
            self.sMaxCellVCellId = sVal

         sVal = self.HoleDbusWertVomCerbo( self.SshDbusBattServiceName, "/System/MinTemperatureCellId")
         if len(sVal) <= 0:
            self.Error2Log( f'Fehler beim Lesen SSH/DBUS/MinTemperatureCellId.')
         else:
            self.sMinCellTCellId = sVal

         sVal = self.HoleDbusWertVomCerbo( self.SshDbusBattServiceName, "/System/MaxTemperatureCellId")
         if len(sVal) <= 0:
            self.Error2Log( f'Fehler beim Lesen SSH/DBUS/MaxTemperatureCellId.')
         else:
            self.sMaxCellTCellId = sVal


         # Abfrage der LEDs am MPII:
         # dbus -y com.victronenergy.vebus.ttyS4 /Leds/Inverter GetValue
         # dbus -y com.victronenergy.vebus.ttyS4 /Leds/Absorption GetValue
         
         #Abfrage der installierten Batteriekapa:
         #  dbus -y com.victronenergy.battery.socketcan_can1 /InstalledCapacity GetValue

         # minimale Zellspannung und Temp
         # dbus -y com.victronenergy.battery.socketcan_can1 /System/MinCellVoltage GetValue
         # dbus -y com.victronenergy.battery.socketcan_can1 /System/MinCellTemperature GetValue

         # Anzahl offline
         # dbus -y com.victronenergy.battery.socketcan_can1 /System/NrOfModulesOffline GetValue

         #  Batt-Spannung
         #  dbus -y com.victronenergy.battery.socketcan_can1 /Dc/0/Voltage GetValue

         # maximale PV-Spannung
         # dbus -y com.victronenergy.solarcharger.ttyS7 /History/Overall/MaxPvVoltage GetValue
         # aktuelle PV-Spannung
         # dbus -y com.victronenergy.solarcharger.ttyS7 /Pv/V GetValue


         # Abfrage weiterer Dienste
         # dbus -y
         # Abfrage aller Werte zum Dienst, Bsp: vebus:
         # dbus -y com.victronenergy.vebus.ttyS4


      except Exception as e:
         self.Error2Log( f'Fehler in HoleDbusWerteVomCerbo(): {e}')
      

   ###### HoleLadeartAusDb(self) ##############################################################################
   def HoleLadeartAusDb(self):
      try:
         sStmt = f'select eLadeart, tLetzterAusgleich, nAnzStunden from solar2023.t_charge_state'
         cur = self.mdb.cursor()
         cur.execute( sStmt)
         rec = cur.fetchone()
         if rec == None:
            self.Error2Log(f'Fehler bei select eLadeart from t_charge_state: rec == None')
            self.vScriptAbbruch()

         sArt = rec[0].replace("\r\n","",1)
         self.tLetzterAusgleich = rec[1]
         self.nAnzStunden = rec[2]

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
         self.Error2Log(f'Fehler bei select eLadeart from t_charge_state: {e}')
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
         sStmt = f"select max(tStunde) from solar2023.t_victdbus_stunde WHERE dSoc is not null and tStunde <> STR_TO_DATE('{self.sZaehlerStunde}', '%Y-%m-%d %H')"
         cur.execute( sStmt)
         rec = cur.fetchone()
         if rec == None:
            self.ls.tStunde = self.tZaehler
         else: 
            self.ls.tStunde = rec[0]

         sLetzteStunde = self.sDate2Str(self.ls.tStunde)
         
         sStmt = f"select dSocAbs, dErtragAbs, dEmL1Abs, dEmL2Abs from solar2023.t_victdbus_stunde where tStunde = STR_TO_DATE('{sLetzteStunde}', '%Y-%m-%d %H')"
         cur.execute( sStmt)
         rec = cur.fetchone()
         if rec == None:
            self.Error2Log(f'Fehler beim Lesen der Zählerstände der letzten Stunde aus t_victdbus_stunde: rec==none')
            return

         self.ls.dSoc      = rec[0] 
         self.ls.dErtrag   = rec[1] 
         self.ls.dEmL1     = rec[2] 
         self.ls.dEmL2     = rec[3] 
         cur.close()

         #unklar, ob das Sinn macht, erstmal keinen Stundendurchschnitt ausweisen, sondern den Absolutwert
         #wenn der letzte Datensatz nicht von der letzten Stunde stammt, dann den Durchschnitt der letzten Stunden annehmen
         #tDiff = self.tZaehler - self.ls.tStunde
         #iStunden = self.iGetHours( tDiff)
         iStunden = 1 

         self.ls.dSocDiff = round( (self.dSoc - self.ls.dSoc) / iStunden, 2)           # positiv: Batterie wurde geladen, negativ: Batterie wurde entladen
         self.ls.dErtragDiff = round((self.dErtragAbs - self.ls.dErtrag) / iStunden, 2)
         self.ls.dEmL1Diff = round((self.dEmL1Abs - self.ls.dEmL1) / iStunden, 2)
         self.ls.dEmL2Diff = round((self.dEmL2Abs - self.ls.dEmL2) / iStunden, 2)

         dBattkWh = self.dSoc2Kwh(self.ls.dSocDiff) # größer oder kleiner 0
         #                           (dStadt            + dErtrag)             - (dBatt    + dHaus)
         self.ls.dAnlagenVerbrauch = (self.ls.dEmL2Diff + self.ls.dErtragDiff) - (dBattkWh + self.ls.dEmL1Diff)
         self.ls.dAnlagenVerbrauch = round( self.ls.dAnlagenVerbrauch, 2)

      except Exception as e:
         self.Error2Log(f'Fehler beim Lesen der Zählerstände der letzten Stunde aus t_victdbus_stunde: {e}')


   ###### BerechneLadungsEnde(self, dSocSoll) ##############################################################################
   def BerechneLadungsEnde(self, dSocSoll):
      if self.nMaxChargeCurr == 0.0:
         self.Error2Log(f'Fehler in BerechneLadungsEnde(): self.nMaxChargeCurr == {self.nMaxChargeCurr}')
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
      # dabei nicht mit festen Verbotszeiten arbeiten, sondern die Prognosetabelle abfragen

#$$ nur temp für Tests, um auch bei zu erwartendem Solarertrag das Nachladen und Ausgleichen testen zu können
#      self.tAus = tSollEnde # keine Einschränkung für das Laden durch die Solarprognose
#      self.Info2Log(f'Es darf geladen werden: Keine Einschränkung durch die Solarprognose')
#      return True           # es darf geladen werden


      sVon = self.sDate2Str(self.tEin)
      sBis = self.sDate2Str(tSollEnde)

      sStmt = f"select stunde,p1,p3,p6,p12,p24 from solar2023.t_prognose where Stunde BETWEEN  STR_TO_DATE('{sVon}', '%Y-%m-%d %H') AND STR_TO_DATE('{sBis}', '%Y-%m-%d %H')\
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

   def bLiegtEinschaltenImVerbot(self):
      if self.tVerbotVon <= self.tEin and self.tEin <= self.tVerbotBis:
         return f'{self.tVerbotVon} - {self.tVerbotBis}'
      if self.tVerbotVon2 != self.tLeer:
         if self.tVerbotVon2 <= self.tEin and self.tEin <= self.tVerbotBis2:
               return f'{self.tVerbotVon} - {self.tVerbotBis}, {self.tVerbotVon2} - {self.tVerbotBis2}'
      return f''

   ###### bIstAusgleichenNoetigUndMoeglich(self) ##############################################################################
   def bIstAusgleichenNoetigUndMoeglich(self):

      diff = self.tNow - self.tLetzterAusgleich 
      if diff.days < self.nAusgleichAlleNWochen * 7 :
         return False # Ausgleich ist nicht nötig

      # Einschalten zur nächsten vollen Stunde
      self.tEin = self.tZaehler

      # Prüfen, ob Einschalten im verbotenen Bereich liegt
      sVerbot = self.bLiegtEinschaltenImVerbot()
      if 0 < len (sVerbot) :
         self.Info2Log(f'Nachladen nicht möglich, weil Einschalt-Stunde {self.tEin} im verbotenen Bereich ({sVerbot}) liegt')
         return False 


      # Wie lange wird das Ausgleichen dauern? 
      tSollEnde = self.BerechneLadungsEnde( dSocSoll=100.0)

      tSollEnde =  tSollEnde + datetime.timedelta(hours = self.dAusgleichStunden)

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

         sVonStunde = self.sDate2Str(self.tEin)
         sBisStunde = self.sDate2Str(self.tAus)
         sNow = self.sDate2Str(self.tNow, True)

         sStmt = "insert into solar2023.t_charge_ticket (eSchaltart, tAnlDat, tSoll, sGrund, tSollAus)\
                   values ( '{0}', STR_TO_DATE('{1}', '%Y-%m-%d %H:%i:%s'), STR_TO_DATE('{2}', '%Y-%m-%d %H'), '{3}', STR_TO_DATE('{4}', '%Y-%m-%d %H') )"
         sStmt = sStmt.format( self.sSchaltart_ein,  sNow, sVonStunde, self.sLadeart, sBisStunde)

         cur = self.mdb.cursor()
         cur.execute( sStmt)
         cur.close()

         sLog = f'Schalt-Ticket in t_charge_ticket eingetragen: {self.sSchaltart_ein}, {self.sLadeart}, Ein: {sVonStunde}, Aus: {sBisStunde}'
         self.Info2Log(sLog)
         self.log4Tickets.info(sLog)

      except Exception as e:
         sErr = f'Fehler beim insert in t_charge_ticket mit ({self.sSchaltart_ein}, {self.sLadeart}, Ein: {sVonStunde}, Aus: {sBisStunde}): {e}'
         self.Error2Log(sErr)
         self.log4Tickets.error(sErr)
         self.vScriptAbbruch()


   ###### LadenAusschalten(self) ##############################################################################
   def LadenAusschalten(self, sLadeart ):
      # ein Ticket in t_charge_ticket eintragen, das Schalten übernimmt das Script mpIIAcOnOff.py/SchalteGpio()
      # ohne Rücksicht auf noch nicht abgearbeitete Tickets

      try:
         self.sLadeart = self.sLadeartAus

         sAusStunde = self.sDate2Str(self.tZaehler)
         sNow = self.sDate2Str(self.tNow, True)

         sStmt = "insert into solar2023.t_charge_ticket (eSchaltart, tAnlDat, tSoll )\
                   values ( '{0}', STR_TO_DATE('{1}', '%Y-%m-%d %H:%i:%s'), STR_TO_DATE('{2}', '%Y-%m-%d %H'))"
         sStmt = sStmt.format( self.sSchaltart_aus, sNow,  sAusStunde)

         cur = self.mdb.cursor()
         cur.execute( sStmt)
         cur.close()

         sLog = f'Schalt-Ticket in t_charge_ticket eingetragen: {self.sSchaltart_aus}, {self.sLadeart}, Aus: {sAusStunde}'
         self.Info2Log(sLog)
         self.log4Tickets.info(sLog)

         if sLadeart == self.sLadeartAusgleichen:
            self.tLetzterAusgleich = self.tZaehler

      except Exception as e:
         sErr = f'Fehler beim insert in t_charge_ticket mit ({self.sSchaltart_aus}, {self.sLadeart}, Aus: {sAusStunde}): {e}'
         self.Error2Log(sErr)
         self.log4Tickets.error(sErr)
         self.vScriptAbbruch()

   ###### iLiesIntWertAusMariaDb(self, iDefault, sSelectStmt) ##############################################################################
   def iLiesIntWertAusMariaDb( self, iDefault, sSelectStmt):

         try:
            cur = self.mdb.cursor()
            cur.execute( sSelectStmt)

            rec = cur.fetchone()
            if rec == None:
               self.Error2Log(f'{sSelectStmt} hat keinen Wert geliefert')
               return iDefault
            if rec[0] == None:
               return iDefault
            return rec[0]
            cur.close()
   
         except Exception as e:
            self.Error2Log(f'Fehler in LiesIntWertAusMariaDb({sSelectStmt}): {e}')
            return iDefault


   ###### TagesprofilEinlesen(self, a24h, nMonat) ##############################################################################
   def TagesprofilEinlesen(self, a24h, nMonat):
         
         try:
            sStmt = f'select nStunde, dKwhHaus, dKwhanlage from solar2023.t_tagesprofil where nMonat={nMonat}  order by nStunde'
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
               t += 1
            cur.close()
   
         except Exception as e:
            self.Error2Log(f'Fehler in TagesprofilEinlesen(): {e}')


   ###### TagesprofilAktualisieren(self) ##############################################################################
   def TagesprofilAktualisieren(self):

         try:
            if self.bMitHypoSocRechnen == True:
               return # es gibt keine aktuellen Werte..

            nZStunde = self.nZaehlerStunde;
            if nZStunde == 0:
               nZStunde = 24  # t_tagesprofil-Stundenindex läuft von 1 bis 24

            sStmt = f'select dKwhHaus, dKwhHausMin, dKwhHausMax, dKwhAnlage, dKwhAnlageMin, dKwhAnlageMax, dKwhSolarMax \
                     from solar2023.t_tagesprofil where nMonat = {self.nMonat} and nStunde = {nZStunde}'

            cur = self.mdb.cursor()
            cur.execute( sStmt)
            rec = cur.fetchone()

            nStundenNeu = self.nAnzStunden + 1

            dKwhHaus = rec[0]
            dKwhHausMin = rec[1]
            dKwhHausMax = rec[2]

            dKwhAnlage = rec[3]
            dKwhAnlageMin = rec[4]
            dKwhAnlageMax = rec[5]
            dKwhSolarMax = rec[6]

            # Durchschnitt des Hausverbrauchs neu berechnen:
            dKwhHaus = round(( (self.nAnzStunden  * dKwhHaus) + self.ls.dEmL1Diff ) / (nStundenNeu),2) # neuer Durchschnitt
            if 0.0 < self.ls.dEmL1Diff and self.ls.dEmL1Diff < dKwhHausMin:
               dKwhHausMin = round(self.ls.dEmL1Diff,2) # neuer Minwert
            if self.ls.dEmL1Diff > dKwhHausMax:
               dKwhHausMax = round(self.ls.dEmL1Diff,2) # neuer Maxwert


            # Verbrauchswerte der Anlage müssen erst  berechnet werden:
            # Fazit: es genügt eine Formel: 

            # Batterie-kWh muss aus SOC abgeleitet werden: 100% == 10kWh
            dBatt = self.dSoc2Kwh(self.ls.dSocDiff) # größer oder kleiner 0
            dStadt = self.ls.dEmL2Diff    # 0 oder größer 0
            dErtrag = self.ls.dErtragDiff # 0 oder größer 0
            dHaus = self.ls.dEmL1Diff     # immer größer 0 (Router, Heizung, ...)
            dAnlage = 0.0

            #  if 0.0 < dStadt: # es wurde nachgeladen oder ausgeglichen:
            #     dAnlage = (dStadt + dErtrag) - (dBatt + dHaus)
            
            #  else: # Wechselrichterbetrieb, ggf  mit Solarunterstützung:

            #     if 0.0 < dErtrag: # Solarertrag

            #        if dBatt > 0.0: # Batterien wurden aus Solarüberschuss geladen, der nicht im Haus verbraucht werden konnte
            #           dAnlage = (0.0 + dErtrag) - (dBatt + dHaus)

            #        elif dBatt < 0.0:  # Solarertrag reicht nicht aus, das Haus zu versorgen, Batterien wurden entladen
            #           dAnlage = (0.0 + dErtrag) - (dBatt + dHaus)
            #           #Beispiel:          1kWh     -1kWh      1,7kWh = 0,3kWh
                 
            #     else: # kein Solarertrag
            #           dAnlage = (0.0 + 0.0) - (dBatt + dHaus)
            #           #Beispiel:              -1kWh    0,7kWh = 0,3kWh

            # Fazit: es genügt eine Formel: 
            dAnlage = (dStadt + dErtrag) - (dBatt + dHaus)

            dKwhAnlageNeu = round(( (self.nAnzStunden  * dKwhAnlage) + dAnlage) / (nStundenNeu),2) # neuer Durchschnitt

            if 0.0 < dAnlage and dAnlage < dKwhAnlageMin:
               dKwhAnlageMin = round( dAnlage, 2) # neuer Minwert

            if dKwhAnlageMax < dAnlage:
               dKwhAnlageMax = round( dAnlage, 2) # neuer Maxwert

            if dKwhSolarMax < dErtrag:
               dKwhSolarMax = round( dErtrag, 2) # neuer Maxwert

            self.nAnzStunden = nStundenNeu # wird in SchreibeStatusInMariaDb() nach t_charge_state gespeichert

            sStmt = f'update solar2023.t_tagesprofil set dKwhHaus={dKwhHaus},dKwhAnlage={dKwhAnlage}, \
                        dKwhHausMin={dKwhHausMin},dKwhHausMax={dKwhHausMax},dKwhAnlageMin={dKwhAnlageMin},dKwhAnlageMax={dKwhAnlageMax}, \
                        dKwhSolarMax={dKwhSolarMax} where nMonat = {self.nMonat} and nStunde = {nZStunde}'
            cur.execute( sStmt)
            self.mdb.commit()
            cur.close()

         except Exception as e:
            self.Error2Log(f'Fehler in TagesprofilAktualisieren(): {e}')
         

   ###### SolarprognoseEinlesen(self) ##############################################################################
   def SolarprognoseEinlesen(self, aXXh, tEin, iStunden):

         try:
            nLiesAbStunde = self.iLiesIntWertAusMariaDb(11,f'select MIN(nStunde) from solar2023.t_tagesprofil where nMonat={self.nMonat} and dKwhSolarMax >= 0.1')
            nLiesBisStunde = self.iLiesIntWertAusMariaDb(14, f'select MAX(nStunde) from solar2023.t_tagesprofil where nMonat={self.nMonat} and dKwhSolarMax >= 0.1')
            nLiesAbStunde2 = self.iLiesIntWertAusMariaDb(11, f'select MIN(nStunde) from solar2023.t_tagesprofil where nMonat={self.nMonat+1} and dKwhSolarMax >= 0.1')
            nLiesBisStunde2 = self.iLiesIntWertAusMariaDb(14, f'select MAX(nStunde) from solar2023.t_tagesprofil where nMonat={self.nMonat+1} and dKwhSolarMax >= 0.1')


            sVon = self.sDate2Str(tEin + datetime.timedelta(hours=1)) # eine Stunde addieren, weil in der Prognosetabelle die backwards-Werte (Prognose bis nn Uhr...)
            tEnd = tEin + datetime.timedelta(hours=iStunden)
            sBis = self.sDate2Str(tEnd)
            sStmt = f"select stunde,p1,p3,p6,p12,p24 from solar2023.t_prognose where Stunde BETWEEN  STR_TO_DATE('{sVon}', '%Y-%m-%d %H') AND STR_TO_DATE('{sBis}', '%Y-%m-%d %H')\
                        order by stunde"

            cur = self.mdb.cursor()
            cur.execute( sStmt)
            rec = cur.fetchone()
            if rec == None:
               self.Info2Log(f'Fehler in SolarprognoseEinlesen(): Keine Prognosedaten gefunden in t_prognose für {sVon} bis {sBis}')
               return False


            while rec != None:
               tProgn = rec[0]
               nStunde = tProgn.hour
               if tProgn.month == self.nMonat:
                  if nStunde < nLiesAbStunde or nLiesBisStunde < nStunde:
                     rec = cur.fetchone()
                     continue
               else:
                  if nStunde < nLiesAbStunde2 or nLiesBisStunde2 < nStunde:
                     rec = cur.fetchone()
                     continue

               dProg = 0.0
               for i in range(1,5+1): # rec ist 0-basiert, alle Prognosewerte durchgehen, von P1 bis P24, ersten, der ungleich 0 ist, nehmen
                  if rec[i] != None:
                     dProg = rec[i]
                     break  

               tDiff = tProgn - tEin
               iStunde = self.iGetHours( tDiff)

               if iStunde < iStunden:
                  print(f'Stunde: {iStunde}: {tProgn}, Prognose: {dProg}') # reicht, wenn es im sh-log steht
                  aXXh[iStunde].dSolarPrognose = dProg

               rec = cur.fetchone()
            cur.close()
            return True

         except Exception as e:
            self.Error2Log(f'Fehler in SolarprognoseEinlesen(): {e}')
         cur.close()
         return False


   ###### BerechneMaximaleSocUnterschreitung(self, aXXh, tEin, iStunden) ##############################################################################
   def BerechneMaximaleSocUnterschreitung(self, aXXh, tEin, iStunden):

      try:
         self.SolarprognoseEinlesen( aXXh, tEin, iStunden)  # Solarprognose einlesen, direkt nach aXXh, liest monatsübergreifend

         a24h = [0.0 for h in range(24)] # in a24h[0] steht, was bis 01:00 verbraucht wurde!
         a24hNext = [0.0 for h in range(24)] # in a24h[0] steht, was bis 01:00 verbraucht wurde!
         
         self.TagesprofilEinlesen( a24h, self.nMonat)

         # den nächsten Monat auch noch einlesen
         tEnd = tEin + datetime.timedelta(hours=iStunden)
         if tEnd.month != self.nMonat:
            self.TagesprofilEinlesen( a24hNext, tEnd.month) 

         # Stundenzahl bis Monatsende berechnen
         tLastHourOfThisMonth = datetime.datetime(tEnd.year, self.nMonat + 1, 1, 0,0) # + 1  weil 24:00 diesen Monat simlutiert wird durch 1. des nächsten Monats 00:00
         nHoursThisMonth = self.iGetHours(tLastHourOfThisMonth - tEin)

         # Tagesprofil ins XXh-Profil übertragen
         hStart = tEin.hour + 1 # +1 weil tEin den Beginn der ersten Stunde definiert, die Verbrauchswerte ab mit bis-Stunde gespeichert sind
         hStopp = hStart + iStunden
         hXX = 0
         for h in range( hStart, hStopp):
            hStunde = h % 24
            if hStunde == 0:
               hStunde = 24
            iIdxStunde = hStunde - 1

            if nHoursThisMonth <= hXX:
               print(f'h: {h}: hStunde: {hStunde}: hXX: {hXX}, a24hNext[{iIdxStunde}]: {a24hNext[iIdxStunde]}')
               aXXh[hXX].dVerbrauch = a24hNext[iIdxStunde]
            else:
               print(f'h: {h}: hStunde: {hStunde}: hXX: {hXX}, a24h[{iIdxStunde}]: {a24h[iIdxStunde]}')
               aXXh[hXX].dVerbrauch = a24h[iIdxStunde]
            hXX += 1
         

         # SOC-Prognose berechnen
         dKapa100 = self.nBattAnz * self.nBattKapa * self.nBattVolt / 1000 # Juni 2023: 4*50Ah*50V/1000 = 10kWh
         dSoc100 = 100.0
         dSocPrognose = aXXh[0].dSoc
         dMaxSocUnterschreitung = 0.0

         # der erste Wert aXXh[0] entspricht dem aktuellen SOC
         print(f'aXXh[{0}]: {aXXh[0].tStunde}:  {aXXh[0].dSoc}')
         # aXXh[0] nicht wegnschreiben! Denn auf  aXXh[0] steht der aktuelle SOC!
         # self.SchreibePrognoseWertInMariaDb( aXXh[0].tStunde, aXXh[0].dSoc)

         dSocMin = 100.0
         for h in range( 1, iStunden):
            dKapaDiff = aXXh[h].dSolarPrognose - aXXh[h].dVerbrauch
            dSocDiff = round(dKapaDiff * dSoc100 / dKapa100, 2)

 #$$ bei 89% beginnt Absorbtion, es gibt noch kein Modell für die Ladekurve in diesem Bereich
            dSocPrognose = min( float(self.nSocAbsorbtion), round(dSocPrognose + dSocDiff, 2))

            aXXh[h].dSoc = dSocPrognose
            print(f'aXXh[{h}]: {aXXh[h].tStunde}:  {aXXh[h].dSoc}') # damit nicht das Log zumüllen, es reicht aus, dass diese Werte im sh-Protokoll stehen
            self.SchreibePrognoseWertInMariaDb( aXXh[h].tStunde, aXXh[h].dSoc)

            if  (aXXh[h].dSoc < float(self.nSocMin) and  aXXh[h].dSoc < dSocMin):
                 dSocMin = aXXh[h].dSoc

         if dSocMin < 100.0:
            dMaxSocUnterschreitung = round(float(self.nSocMin) - dSocMin, 2)

         self.mdb.commit()
         self.Info2Log(f'Prognose-Werte in DB eingetragen.')


      except Exception as e:
         self.Error2Log(f'Ausnahme in BerechneMaximaleSocUnterschreitung( {tEin}, {iStunden}): {e}')
         self.vScriptAbbruch()

      return dMaxSocUnterschreitung


   ###### bIstLadenNoetigUndMoeglich(self) ##############################################################################
   def bIstLadenNoetigUndMoeglich(self):
      try:

         # Einschalten zur nächsten vollen Stunde
         self.tEin = self.tZaehler

         # Prüfen, ob Not-Ein nötig ist
         if self.dSoc < float(self.nSocMin):
            self.tAus = self.tEin + + datetime.timedelta(hours=2) # mindestens 20% nachladen
            self.Info2Log(f'Nachladen nötig, weil SOC unter {self.nSocMin}%. Wenn dann noch Sonne dazukommt, wird das toleriert.')
            return True 

         # Prüfen, ob Einschalten im verbotenen Bereich liegt
         sVerbot = self.bLiegtEinschaltenImVerbot()
         if 0 < len (sVerbot) :
            self.Info2Log(f'Nachladen nicht möglich, weil Einschalt-Stunde {self.tEin} im verbotenen Bereich ({sVerbot}) liegt')
            return False 

         # Vektor anlegen und füllen: {self.nAnzPrognoseStunden} x Verbrauch(t_tagesprofil) + Solarertrag(t_prognose) + SOC(berechnet)
         # dabei die maximale Unterschreitung des SOCMin ermitteln und zurückliefern
         self.aProgStd[0].dSoc = self.dSoc

         dSocMaxUnter = self.BerechneMaximaleSocUnterschreitung( self.aProgStd, self.tEin, self.nAnzPrognoseStunden) 

         if dSocMaxUnter == 0.0:
            self.Info2Log(f'Nachladen nicht nötig, weil die untere SOC-Grenze innerhalb der nächsten {self.nAnzPrognoseStunden-1} Stunden nicht unterschritten wird')
            return False 

         self.Info2Log(f'Nachladen nötig, weil die untere SOC-Grenze innerhalb der nächsten {self.nAnzPrognoseStunden-1} Stunden unterschritten würde: {self.nSocMin} --> {dSocMaxUnter}')

         # Wie lange wird das Nachladen dauern? 
         tSollEnde = self.BerechneLadungsEnde( dSocSoll=self.dSoc + dSocMaxUnter)

         # Laden ist verboten in Stunden, wo der Ertrag laut Prognose größer als 0,1kWh/h sein soll
         # D.h. prüfen: Wann kommt diese nächste Sonnenstunde? Ab da ist kein Laden möglich
         self.tAus = self.tLeer
         if self.BerechneAusschaltzeitpunkt(tSollEnde) == False: # setzt self.tAus
            return False
         else:
            return True

      except Exception as e:
         self.Error2Log(f'Ausnahme in bIstLadenNoetigUndMoeglich(): {e}. return False')

      return False



   ###### bIstAusgleichenAusschaltenMoeglich(self) ##############################################################################
   # Möglich, wenn SOC mindestens <dAusgleichStunden> Stunden bei 100% war
   def bIstAusgleichenAusschaltenMoeglich(self):

      try:
         tVon = self.tZaehler - datetime.timedelta(hours=self.dAusgleichStunden)
         sVon = self.sDate2Str(tVon)
         sBis = self.sDate2Str(self.tZaehler)

         sStmt = f"SELECT MIN(s.dSocAbs) FROM solar2023.t_victdbus_stunde s WHERE s.tStunde BETWEEN STR_TO_DATE('{sVon}', '%Y-%m-%d %H') \
                     AND STR_TO_DATE('{sBis}', '%Y-%m-%d %H')"

         cur = self.mdb.cursor()
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

      if self.bIstLadenNoetigUndMoeglich() == True:
         self.Info2Log(f'Nachladen wird nicht ausgeschaltet, weil bIstLadenNoetigUndMoeglich() == True')
         return False

      self.Info2Log(f'Nachladen kann ausgeschaltet werden')
      return True


   ###### SchreibeDbusWerteInMariaDb(self) ##############################################################################
   def SchreibeDbusWerteInMariaDb(self):
      
      try:
         if self.bMitHypoSocRechnen == True:
            return # es gibt keine aktuellen Werte...
         

         sStmt = "insert into solar2023.t_victdbus_stunde (tStunde, dSocAbs, dSoc, dErtragAbs, dErtrag, dEmL1, dEmL2, dEmL1Abs, dEmL2Abs,dAnlagenVerbrauch,\
                        dCellVoltageMin,dCellVoltageMax,dCellTemperaturMin,dCellTemperaturMax,sCellIdMinVoltage,sCellIdMaxVoltage,sCellIdMinTemperature,sCellIdMaxTemperature)\
                   values (STR_TO_DATE('{0}', '%Y-%m-%d %H'), {1}, {2}, {3}, {4}, {5}, {6}, {7}, {8}, {9}, {10}, {11}, {12}, {13}, {14}, {15}, {16}, {17}  ) \
                   ON DUPLICATE KEY UPDATE  dSocAbs={1}, dSoc={2}, dErtragAbs={3}, dErtrag={4}, dEmL1={5}, dEmL2={6}, dEmL1Abs={7}, dEmL2Abs={8},dAnlagenVerbrauch={9},\
                   dCellVoltageMin={10},dCellVoltageMax={11},dCellTemperaturMin={12},dCellTemperaturMax={13},sCellIdMinVoltage={14},sCellIdMaxVoltage={15},sCellIdMinTemperature={16},sCellIdMaxTemperature={17}"
         sStmt = sStmt.format(self.sZaehlerStunde, self.dSoc, self.ls.dSocDiff, self.dErtragAbs, self.ls.dErtragDiff, self.ls.dEmL1Diff, 
                              self.ls.dEmL2Diff, self.dEmL1Abs, self.dEmL2Abs, self.ls.dAnlagenVerbrauch,
                              self.sMinCellV,  self.sMaxCellV, self.sMinCellT, self.sMaxCellT,
                              self.sMinCellVCellId,self.sMaxCellVCellId, self.sMinCellTCellId,self.sMaxCellTCellId)

         cur = self.mdb.cursor()
         cur.execute( sStmt)
         self.mdb.commit()
         cur.close()
   
         self.Info2Log(f'Dbus-Werte in DB aktualisiert: {self.dSoc}, {self.dErtragAbs}, {self.dEmL1Abs}, {self.dEmL2Abs}')

      except Exception as e:
         self.Error2Log(f'Fehler beim insert in t_victdbus_stunde mit {self.dSoc}, {self.dErtragAbs}, {self.dEmL1Abs}, {self.dEmL2Abs}: {e}')
         self.vScriptAbbruch()

   ###### SchreibePrognoseWertInMariaDb(self, tStunde, dSoc) ##############################################################################
   def SchreibePrognoseWertInMariaDb(self, tStunde, dSocPrognose):
      
      try:
         sStunde = self.sDate2Str(tStunde)
         sStmt = "insert into solar2023.t_victdbus_stunde (tStunde, dSocPrognose)\
                   values (STR_TO_DATE('{0}', '%Y-%m-%d %H'), {1}  ) \
                   ON DUPLICATE KEY UPDATE  dSocPrognose={1}"
         sStmt = sStmt.format( sStunde, dSocPrognose)

         cur = self.mdb.cursor()
         cur.execute( sStmt)
         cur.close()
   
      except Exception as e:
         self.Error2Log(f'Fehler beim Prognose-insert in t_victdbus_stunde mit {sStunde}, {dSocPrognose}: {e}')
         self.vScriptAbbruch()
         
   ###### SchreibeStatusInMariaDb(self) ##############################################################################
   def SchreibeStatusInMariaDb(self):

      try:
         sLetzterAusgleich = self.sDate2Str( self.tLetzterAusgleich)

         sStmt = f"update solar2023.t_charge_state set eLadeart='{self.sLadeart}', tAendDat=sysdate() , nAnzStunden={self.nAnzStunden},\
                                                tLetzterAusgleich=STR_TO_DATE('{sLetzterAusgleich}', '%Y-%m-%d %H')"

         cur = self.mdb.cursor()
         cur.execute( sStmt)

         sNow = self.sDate2Str(self.tNow, True)
         sStmt = f"update solar2023.t_charge_ticket set tIst = STR_TO_DATE('{sNow}', '%Y-%m-%d %H:%i:%s') where tAnlDat = STR_TO_DATE('{sNow}', '%Y-%m-%d %H:%i:%s')"

         cur.execute( sStmt)
         cur.close()


      except Exception as e:
         self.Error2Log(f'Fehler beim update von t_charge_state mit ({self.sLadeart}): {e}')
         self.vScriptAbbruch()


   ###### HoleGpioStatus(self, iPin, bMitInit) ##############################################################################
   def HoleGpioStatus(self, iPin, bMitInit):
      # abfragen, in welchem Zustand sich der KM12-Sensor am Stromstoßschalter befindet und mit Ladeart aus DB vergleichen
      # ist unter Windows nicht ausführbar!
      try:
         if bMitInit:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.iGpioPinSensorAc, GPIO.IN, GPIO.PUD_DOWN) # den internen pulldown-Widerstand aktivieren
      
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
            self.Info2Log(f'Pin {self.iGpioPinSensorAc} hat Wert {iStat1}-->{sPinStat}')
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
         self.Info2Log(f'GPIO-Status Pin {self.iGpioPinSensorAc} stimmt mit aktueller Ladeart überein: GPIO: {self.sAcSensor}, Ladeart: {self.sLadeart}')

      else:
         self.Error2Log(f'Status ({self.sAcSensor}) GPIO-Pin {self.iGpioPinSensorAc} passt nicht zur Ladeart: {self.sLadeart}')
       

   ###### GpioSendeSchaltimpuls(self, sEinAus) ##############################################################################
   def GpioSendeSchaltimpuls(self, sEinAus):

      #https://projects.raspberrypi.org/en/projects/physical-computing/1
      # ist unter Windows nicht ausführbar!
      try:
         GPIO.setmode(GPIO.BCM)
         # hier nur das Sensor-Pin initialisieren, das Actor-Pin wird unten erledigt
         GPIO.setup(self.iGpioPinSensorAc, GPIO.IN, GPIO.PUD_DOWN) # den internen pulldown-Widerstand aktivieren) 
         
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
         self.Error2Log(f'Ausnahme in GpioSendeSchaltimpuls():  {e}')
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

   ###### BerechneHypoSoc(self) ##############################################################################
   # Wenn keine Verbindung via ssh/dbus zum Cerbo besteht, kann der aktuelle SOC nicht ermittelt werden.
   # Hier wird deshalb ein hyp. SOC auf Basis des letzten bekannten SOC und der Solar- und Verbrauchswerte berechnet,
   # mit dem die Funktionen dann weiterrechnen können, um ein/auschalten zu können
   def BerechneHypoSoc(self):
      dSoc = self.ls.dSoc #letzter bekannter SOC wurde in HoleLetzteStundeAusDb() gelesen
      tStunde = self.ls.tStunde

      # Matrix anlegen für den Zeitraum LetzteBekannteStunde bis jetzt
      iStunden = self.iGetHours( self.tZaehler - tStunde)
      iStunden += 1 # weil auf [0] nur der aktuelle SOC liegt
      aXXh = [CPrognoseStunde(tStunde, h) for h in range(iStunden)]
      aXXh[0].dSoc = dSoc
      self.BerechneMaximaleSocUnterschreitung( aXXh, tStunde, iStunden ) # Funktion mit nutzen, Unterschreitung ignorieren

      #letzter Wert in aXXh ist der SOC, der für die aktuelle Stunde berechnet wurde
      self.dSoc = aXXh[iStunden-1].dSoc
      self.Info2Log(f'Hypo. (berechneter) SOC um {aXXh[iStunden-1].tStunde}: {self.dSoc}')


   ###### BerechneEinAus(self) ##############################################################################
   def BerechneEinAus(self):

      if self.bMitHypoSocRechnen == True:
         self.BerechneHypoSoc() # korrigiert self.dSoc, alle folgenden Funktionen rechnen mit diesem SOC weiter

      if self.sLadeart == ac.sLadeartAus:
         if self.bIstAusgleichenNoetigUndMoeglich():           
            self.LadenEinschalten( self.sLadeartAusgleichen )
         else:
            if self.bIstLadenNoetigUndMoeglich():
               self.LadenEinschalten( self.sLadeartNachladen )

      elif self.sLadeart == self.sLadeartAusgleichen:    
         if self.bIstAusgleichenAusschaltenMoeglich():
            self.LadenAusschalten(self.sLadeartAusgleichen)
          
      elif self.sLadeart == self.sLadeartNachladen:    
         if self.bIstLadenAusschaltenMoeglichOderNoetig():
            self.LadenAusschalten(self.sLadeartNachladen)

      else:
           self.Error2Log(f'Fehler: Unbekannte Ladeart: {self.sLadeart}')



###### CAcOnOff  } ##############################################################################

ac = CAcOnOff()                           # Konfigdatei lesen 

ac.VerbindeMitMariaDb()                   # Verbindung zur DB herstellen, zweite Verbindung fürs Log
ac.WerteInsLog()                          # Wichtige Konfigurationsdaten ins Log schreiben

# erster "Unittest", Sollwerte und Vergleich fehlt noch ;)
#ac.nMonat = 11
#tEin = datetime.datetime(2023,ac.nMonat,30,12,0)
#ac.nAnzPrognoseStunden += 1 # weil auf [0] nur der aktuelle SOC liegt
#ac.aProgStd = [CPrognoseStunde(tEin, h) for h in range(ac.nAnzPrognoseStunden)]
#ac.aProgStd[0].dSoc = 5
#dSocMaxUnter = ac.BerechneMaximaleSocUnterschreitung( ac.aProgStd, tEin, ac.nAnzPrognoseStunden) 


ac.HoleDbusWerteVomCerbo()                # Werte aus der Anlage lesen, wenn das nicht möglich ist, die Prognose ab dem letzten bekannten SOC rechnen  
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





