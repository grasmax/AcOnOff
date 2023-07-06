#   Ziel: Nachladen der Solar-Puffer-Batterien in Abhängigkeit vom Batterie-State of Charge (SOC, Batterieladezustand),
#            der Solarprognose sowie dem prognostizierten Verbrauch einschließlich der Anlage selbst
#            durch Ein- und Ausschalten der Versorgung des MultiplusII-Chargers mit Stadtstrom an AC-IN:
#
#             Bei Blackout-Gefahr: 
#             - SOC permanent bei 100% halten, keine Solarunterstützung, Laden mit Stadtstrom permanent ein
#             - Umsetzung nicht hier im Script, sondern mit Hardwareschalter (AC-IN permanent ein)
#
#             Bei Brownout-Gefahr, d.h. angekündigten Abschaltungen
#             - Kapa vor der Abschaltung mit oder ohne Solarunterstützung auf 100% bringen
#             - Umsetzung: in Planung: Brownouts abfragen und in Tabelle eintragen, Versuchen, bis zum Beginn die SOC-Lücke bis 100% zu füllen
#
#             Unterscheiden: Nachladen(bis 90%) / Ausgleichsladen (ausreichend lange, bis alle Batterien und -Zellen ausgeglichen sind)
#
#             Im Normalfall:
#             - Für den lt. Prognose zu erwartender Solar-Ertrag muss Kapa in der Batterie freigehalten werden
#             - Ausgleichs- und Nachladen nur dann, wenn laut Prognose mehr als 0,1kWh/h zu erwarten sind
#             - SOC zwischen 21 und 85 Prozent halten, 20% sind zusätzlich durch die Generatorregel im Cerbo abgesichert
#             - Anzahl der Ein/Ausschaltvorgänge minimieren um die Schütze zu schonen
#             - Nachladen im Idealfall nur nachts, wenn nur die Grundlast (Kühlung, Heizung, Fritzbox) gebraucht wird
#             - KI-like beim Verbrauch mit den historischen Werten des Monats / der Jahreszeit rechnen
#             - (KI-like beim Ertragsprognose mit den historischen Werten der Jahreszeit rechnen)
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
#       mb_pvpro.py holt die Solarprognose von MeteoBlue und schreibt sie in die Tabelle t_prognose
#       hier umgesetzt:
#             dieses Script liest über ssh/dbus Werte aus der Anlage und schreibt sie in die Tabelle t_victdbus_stunde: SOC, Solarertrag, Zählerstände
#             in Arbeit: dieses Script liest füllt und aktualisiert stündlich die Tabelle t_tagesprofil; darin sind für jede Stunde der Durchschnittsverbrauch gespeichert
#             CCBerechneEinAus.CBerechneEinAus() berechnet aus t_prognose, t_tagesprofil und t_victdbus_stunde, ob und wie lange die Batterien geladen werden sollen 
#             und schreibt in die Tabellen t_charge_state und t_charge_ticket
#             SchalteGpio (auf dem Master-Raspi (in Planung)) schaltet ein Relais1 auf dem Raspi-Relayboard 
#       in Planung: Relais1 schaltet 12VDC durch zu einem Stromstoßschalter. Der Stromstoßschalter schaltet 48VDC durch zum Klemmmenblock 3 im Verteilerkasten Solar
#       Dadurch schaltet der Schütz im Verteilerkasten Solar 230VAC durch zu AC-IN des MultiplusII.
#       Dadurch schaltet der MultiplussII das Ladegerät ein und versorgt alle an AC-Out1 angeschlossenen Verbraucher mit Stadtstrom.
#       Der Schaltzustand des Stromstoßschalters wird erfasst mit einem KM12-Sensor, der seinerseits im eingeschalteten Zustand 3VDC zu einem GPIO-Pin schaltet, dass
#       von HoleUndTesteGpioStatus() überwacht wird.
#
#       Diese Berechung wird stündlich ausgeführt:
#          In welchem Zustand ist das Ladegerät?
#             AUS
#                Eintrag in t_charge_log
#                IstAusgleichenNoetigUndMoeglich?
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
# als cronjob laufen lassen
# http://www.raspberrypi-tutorials.de/software/cronjobs-auf-dem-raspberry-pi-erstelleneinrichten.html
# stündlich zur Minute 55
#     sudo crontab -e
#     5 * * * * root /home/pi/mpIIAcOnOff.py
#
# Das ursprüngliche Konzept sah ein weiteres Script vor, dass das GPIO-Pins schalten sollte und über Tickets von hier aus getriggert werden sollte.
# Dabei ging ich davon aus, dass das GPIO-Pin solange auf high gehalten werden muss, wie der Leistungsschütz eingeschaltet sein soll.
# Dafür hätte das Script für die Dauer des Ladevorgangs laufen müssen. Und das Relais hätte 48VDC schalten müssen, es ist aber nur für 30 VDC zugelassen.
# Das aktuelle Konzept sieht deshalb einen zusätzlichen Stromstoßschalter vor, der über das Relais auf dem Raspi-Board mit 12VDC angesteuert wird.
# Dazu ist nur ein 0.2ms-Impuls nötig, das Relais wird geschont und das Script muss nicht dauerhaft laufen. 
# Das Schalten des GPIO-Pin 26 kann also hier gleich mit erledigt werden. (Pin 26 getestet in der Alarmanlage)
# An den Stromstoßschalter ist ein KM12-Modul angedokt, das den Schaltzustand anzeigt. 
# Dieser Schaltzustand wird über GPIO-Pin 22 abgefragt (mit 3,3V an Pin 22 und 23 schon an der Alarmanlage getestet)
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
#
#  raspi io-, cm4- und pci-Boards
#     Stromkabel mit J19 oder J20 Stecker fehlt noch 
#
#  Victron/Gavazzi-Zähler
#     erl. einbauen
#     erl. mit Cerbo verbinden
#     erl. Werte abfragen und in die DB-Speichern
#     in den Auswertungen berücksichtigen
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


#  bessere Passwortverschlüsselung?
#  (Durchschnitts-)Verbrauch für jeden Monat ermitteln
#  Eigenverbrauch der Anlage muss genauer bestimmt werden, sollte mit dem neuen Zähler möglich werden
#  Anteil Sofortverbrauch am Durchschnittsverbrauch ermitteln


import os
import base64
import ctypes
import datetime
import subprocess
import logging
from logging.handlers import RotatingFileHandler
import json
from tokenize import Double
import mariadb
import time

# ist unter Windows logischerweise nicht ausführbar (keine GPIO-Pins...)
# import RPi.GPIO as GPIO 
# für den Test unter windows liegt eine Hilfsklasse gleichen Namens in gpio.py:
from gpioersatz import GPIO


class CPrognoseTag:
   def __init__(self, tNow, Stunde):

      self.tStunde = datetime.datetime(tNow.year,tNow.month,  tNow.day, tNow.hour+1) + datetime.timedelta(hours=Stunde)
      self.dVerbrauch  = 0.0  # Summe der Verbrauchswerte aus Tabelle t_tagesprofil
      self.dSolarPrognose  = 0.0  # Wert aus Tabelle t_prognose
      self.nSoc = 0   # auf Basis des aktuellen SOC, der voraussichtlichen Verbrauchswerte und der Solarvorhersage berechneter Wert


###### CBerechneEinAus  { ##############################################################################
class CBerechneEinAus:

   ###### __init__(self) ##############################################################################
   def __init__(self):
      print("Programmstart")

      # Konfiguration einlesen und Verbindung zur Datenbank aufbauen
      logging.basicConfig(encoding='utf-8', level=logging.DEBUG,
                          style='{', datefmt='%Y-%m-%d %H:%M:%S', format='{asctime} {levelname} {filename}:{lineno}: {message}',
                          handlers=[RotatingFileHandler('./mpIIAcOnOff.log', maxBytes=100000, backupCount=10)],)

      self.tNow = datetime.datetime.now()
      print(self.tNow)
      self.sJetztStunde = f'{self.tNow.year}-{self.tNow.month}-{self.tNow.day} {self.tNow.hour}'

      self.tLeer = datetime.datetime(2022,1,1)

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

         self.AusgleichAlleNWochen = Settings['Laden']['AusgleichAlleNWochen']
         self.Absorb100Dauer = Settings['Laden']['DauerAbsorbtion100']

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
      self.nSoc = 0                 # aktueller SOC aus der Anlage, abgefragt per dbus
      self.dErtragAbs = 0.0         # aktueller Gesamt-Solarertrag, abgefragt per dbus
      self.dErtragLast = 0.0        # letzter Wertes aus t_charge_state
      self.dErtrag = 0.0            # berechneter Solarertrag für die letzte Stunde, ermittelt als Differenz aus dErtragLast und dem aktuellen dbus-Wertes
      self.sLadeart = ''            # None/Aus, Voll, Nach

      self.sAcSensor = ''
      
      self.tEin = self.tLeer
      self.tAus = self.tLeer
      self.tLetzterAusgleich = self.tLeer  # Zeitpunkt, wann der letzte Ausgleich abgeschlossen war

      self.a48h = [CPrognoseTag(self.tNow, h) for h in range(48)]

   ###### VerbindeMitMariaDb(self) ##############################################################################
   def VerbindeMitMariaDb(self):
      # Verbindung zur MariaDB
      try:
         self.mdb = mariadb.connect( host=self.MariaIp, port=3306,user=self.MariaUser, password=self.MariaPwd)
      except Exception as e:
         logging.error(f'Fehler in mariadb.connect(): {e}')
         return False;

      try:
         self.mdbLog = mariadb.connect( host=self.MariaIp, port=3306,user=self.MariaUser, password=self.MariaPwd)
      except Exception as e:
         logging.error(f'Fehler in mariadb.connect() fürs Logging: {e}')
         return False;

      # ab hier Logging in die MariaDb-Tabelle t_charge_log
      self.Info2Log('mdb-connect ok')
      return True


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
      #$$ hier müsste noch eine email/sms verschieckt werden!
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
         vScriptAbbruch()


   ###### Info2Log(self, sText) ##############################################################################
   def Info2Log(self, sText):
      self.__Record2Log( "info", "", sText)

   ###### Error2Log(self, sText) ##############################################################################
   def Error2Log(self, sText):
      self.__Record2Log( "error", "", sText)

   ###### State2Log(self, eLadeart, sText) ##############################################################################
   def State2Log(self, eLadeart, sText):
      self.__Record2Log( "info", eLadeart, sText)


   ###### HoleDbusWertVomCerbo(self, sService, sPath) ##############################################################################
   def HoleDbusWertVomCerbo(self, sService, sPath): 
      
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
 #     putty  und dann dbus -y com.victronenergy.system /Dc/Battery/Soc GetValue
 #      oder gleich so mit dem per ssh-keygen erzeugten Schlüsseldatei leno2venus: 
 #              C:\Users\Rainer>ssh -i leno2venus root@192.168.2.38 "dbus -y com.victronenergy.system /Dc/Battery/Soc GetValue"
 #               59
 #        dafür wurde auf dem Client (leno2018) ein ssh-Schlüsselpaar erzeugt und der öffentliche Schlüssel aus der pub-Datei 
 #           auf dem Cerbo in  root@einstein:~# nano ~/.ssh/authorized_keys  eingetragen
 #           habe dann noch ein Schlüsselpaar l2v erzeugt und mitssh-add registriert. Danach konnte ich ssh auch ohne -i ausführen.
          
      sDbusCmd = f'dbus -y {sService} {sPath} GetValue'

      #das Verzeichnis openssh musste von system32 nach e': kopiert werden, weil python/ssh darauf nicht zufgreifen können
      sSshCmd = f'e:\\dev_priv\\openssh\\ssh {self.SshCerboUser}@{self.SshCerboIP} "{sDbusCmd}">{self.SshDbusTempFile}'

      try:
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
      self.nSoc = int(round(float(self.HoleDbusWertVomCerbo( "com.victronenergy.system", "/Dc/Battery/Soc")),2) )

      #Gesamt-Solarertrag aus dem MPPT-Solarregler
      self.dErtragAbs = round(float(self.HoleDbusWertVomCerbo( self.SshDbusSolarServiceName, "/Yield/System")),2)
      
      #Gesamtverbrauch aller Verbraucher im Solarteil der Hausinstallation (ohne Eigenverbrauch der Anlage)
      # gezählt wird alles, was aus dem Inverter kommt, egal ob aus der Batterie oder nur durchgeschleifter Stadtstrom beim Nachladen oder Ausgleichen
      self.dVerbrauchL1 = round(float(self.HoleDbusWertVomCerbo( self.SshDbusEmServiceName, "/Ac/L1/Energy/Forward")),2)

      # gezählt wird am MPII-AC-In, was an Stadtstrom reingeht, um die Batterie zu laden und während des Ladens alle Verbraucher im Solarteil der Hausinstallation zu versorgen
      self.dVerbrauchL2 = round(float(self.HoleDbusWertVomCerbo( self.SshDbusEmServiceName, "/Ac/L2/Energy/Forward")),2)
      

   ###### HoleLadeartAusDb(self) ##############################################################################
   def HoleLadeartAusDb(self):
      cur = self.mdb.cursor()
      sStmt = f'select eLadeart, dErtrag, tLetzterAusgleich from db1.t_charge_state'
      try:
         cur.execute( sStmt)
         rec = cur.fetchone()
         if rec == None:
            self.Error2Log(f'Fehler bei select eLadeart from mariadb.DB1.t_charge_state: rec == None')
            self.vScriptAbbruch()

         sArt = rec[0].replace("\r\n","",1)
         if sArt == self.sLadeartAus or sArt == self.sLadeartAusgleichen or sArt == self.sLadeartNormal:
            self.sLadeart = sArt
         else:
            self.Error2Log(f'Fehler beim Lesen der eLadeart from mariadb.DB1.t_charge_state: Unbekannte Ladeart: {sArt}')
            self.vScriptAbbruch()

         self.dErtragLast = rec[1]
         if self.dErtragLast == 0 or self.dErtragLast == None:
            self.dErtragLast = self.dErtragAbs
         
         self.tLetzterAusgleich = rec[2]
         if self.tLetzterAusgleich == None:
            self.Error2Log(f'Fehler: t_charge_state.tLetzterAusgleich noch nicht initialisiert.')
            self.vScriptAbbruch()

         self.Info2Log(f'Ladeart: {ac.sLadeart}')

      except Exception as e:
         self.Error2Log(f'Fehler bei select eLadeart from mariadb.DB1.t_charge_state: {e}')
         self.vScriptAbbruch()


   ###### BerechneLadungsEnde(self, nSocSoll) ##############################################################################
   def BerechneLadungsEnde(self, nSocSoll):
      if self.nMaxChargeCurr == 0.0:
         self.Error2Log(f'Fehler bei select eLadeart from mariadb.DB1.t_charge_state: {e}')
         self.vScriptAbbruch()

      # Berechnung in Abhängigkeit von Anzahl Batterien, Ah der Batterien, SOC, Ladestrom und Eigenverbrauch
      nKapa100 = self.nBattAnz * self.nBattKapa # Juni 2023: 4*50Ah = 200Ah
      nGapProz = nSocSoll - self.nSoc # Lücke in % 22.6.23 1400 100-70=30%
      nGapAh = (nKapa100 * nGapProz) / 100
      dStunden = nGapAh / self.nMaxChargeCurr # Juni 2023: Ladestrom 20A --> 60 / 20 = 3h
      
      #Eigenverbrauch vereinfacht dazunehmen, ohne die Verlängerung iterativ xmal zu berücksichtigen
      dEigenStundekWh = self.dEigenverbrauch / 24
      dEigenkWh =  dEigenStundekWh * dStunden
      dEigenAh = dEigenkWh / 50 # 50V angenommen
      dEigenStunden = dEigenAh / self.nMaxChargeCurr

      tDau = datetime.timedelta(hours= int(dStunden + dEigenStunden) + 1)
      tEnde = self.tEin + tDau
      self.Info2Log(f'Berechnetes Ladungsende: {tEnde}')
      return tEnde


   ###### BerechneAusschaltzeitpunkt(self, tSollEnde) ##############################################################################
   def BerechneAusschaltzeitpunkt(self, tSollEnde):
      # von tEin bis tSollEnde prüfen, ob mit Solarertrag zu rechnen ist
      # dabei nicht mit den Verbotszeiten (self.nVerbotVon,self.nVerbotBis) arbeiten, sondern die Prognosetabelle abfragen

      sVon = f'{self.tEin.year}-{self.tEin.month}-{self.tEin.day} {self.tEin.hour}'
      sBis = f'{tSollEnde.year}-{tSollEnde.month}-{tSollEnde.day} {tSollEnde.hour}'

      sStmt = f"select stunde,p1,p3,p6,p12,p24 from db1.t_prognose where Stunde BETWEEN  STR_TO_DATE('{sVon}', '%Y-%m-%d %H') AND STR_TO_DATE('{sBis}', '%Y-%m-%d %H')\
                     order by stunde"

      try:
         cur = self.mdb.cursor()
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
         return True           # es darf geladen werden

      except Exception as e:
         self.Error2Log(f'Fehler beim Lesen der Prognosedaten aus t_prognose für {sVon} bis {sVon}: {e}')
         self.Info2Log(f'Es wird ohne Prognosedaten gerechnet und geladen')
         self.tAus = tSollEnde # keine Einschränkung durch die Solarprognose
         return True # es darf geladen werden


   ###### IstAusgleichenNoetigUndMoeglich(self) ##############################################################################
   def IstAusgleichenNoetigUndMoeglich(self):
      print(f'IstAusgleichenNoetigUndMoeglich')
      diff = self.tNow - self.tLetzterAusgleich 
      if diff.days < self.AusgleichAlleNWochen * 7 :
         return False # Ausgleich ist nicht nötig

      # Einschalten zur nächsten vollen Stunde
      self.tEin = datetime.datetime(self.tNow.year,self.tNow.month,self.tNow.day,self.tNow.hour+1,0)

      # Wie lange wird das Ausgleichen dauern? 
      tSollEnde = self.BerechneLadungsEnde( nSocSoll=100)

      # Ist Ausgleichen möglich? Ausgleichen ist verboten in Stunden, wo der Ertrag laut Prognose größer als 0,1kWh/h sein soll
      # D.h. prüfen: Wann kommt diese nächste Sonnenstunde? Ab da ist kein Laden möglich
      self.tAus = self.tLeer
      if self.BerechneAusschaltzeitpunkt(tSollEnde) == False:
         return False
      else:
         return True


   ###### LadenEinschalten(self, sLadeart ) ##############################################################################
   def LadenEinschalten(self, sLadeart ):
      # ein Ticket in t_charge_ticket eintragen, das Schalten übernimmt das Script mpIIAcOnOff.py
      # ohne Rücksicht auf noch nicht abgearbeitete Tickets

      self.sLadeart = sLadeart

      sVonStunde = f'{self.tEin.year}-{self.tEin.month}-{self.tEin.day} {self.tEin.hour}'
      sBisStunde = f'{self.tAus.year}-{self.tAus.month}-{self.tAus.day} {self.tAus.hour}'

      cur = self.mdb.cursor()
      sStmt = "insert into db1.t_charge_ticket (eSchaltart, tAnlDat, tSoll, sGrund, tSollAus)\
                values ( '{0}', sysdate(), STR_TO_DATE('{1}', '%Y-%m-%d %H'), '{3}', STR_TO_DATE('{2}', '%Y-%m-%d %H') )"
      sStmt = sStmt.format( self.sSchaltart_ein,  sVonStunde, sBisStunde, self.sLadeart)

      try:
         cur.execute( sStmt)
         self.Info2Log(f'Schalt-Ticket in t_charge_ticket eingetragen: {self.sSchaltart_ein}, {self.sLadeart}, Ein: {sVonStunde}, Aus: {sBisStunde}')
      except Exception as e:
         self.Error2Log(f'Fehler beim insert in mariadb.DB1.t_charge_ticket mit ({self.sSchaltart_ein}, {self.sLadeart}, Ein: {sVonStunde}, Aus: {sBisStunde}): {e}')
         self.vScriptAbbruch()

   def TagesprofilEinlesen(self, a24h):
         cur = self.mdb.cursor()
         sStmt = f'select nStunde, dKwhHaus, dKwhanlage from db1.t_tagesprofil'
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


   def SolarprognoseEinlesen(self):

         sVon = f'{self.tEin.year}-{self.tEin.month}-{self.tEin.day} {self.tEin.hour}'
         tEnd = self.tEin + datetime.timedelta(hours=48)
         sBis = f'{tEnd.year}-{tEnd.month}-{tEnd.day} {tEnd.hour}'
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
         return True

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
         dSocPrognose = float(self.nSoc)
         nMaxSocUnterschreitung = 0
         for h in range( 48):
            dKapaDiff = self.a48h[h].dSolarPrognose - self.a48h[h].dVerbrauch
            dSocDiff = dKapaDiff * dSoc100 / dKapa100

            #$$ bei 89% beginnt Absorbtion, es gibt noch kein Modell für die Ladekurve in diesem Bereich
            dSocPrognose = min( float(self.nSocAbsorbtion), dSocPrognose + dSocDiff)

            self.a48h[h].nSoc = int(dSocPrognose + 0.5)
            print(f'a48h[{h}]: {self.a48h[h].tStunde}:  {self.a48h[h].nSoc}')

            if( self.a48h[h].nSoc < self.nSocMin):
               nMaxSocUnterschreitung = self.nSocMin - self.a48h[h].nSoc

      except Exception as e:
         self.Error2Log(f'Fehler in BerechneMaximaleSocUnterschreitung(): {e}')
         self.vScriptAbbruch()

      return nMaxSocUnterschreitung




   ###### IstLadenNoetigUndMoeglich(self) ##############################################################################
   def IstLadenNoetigUndMoeglich(self):
      print(f'IstLadenNoetigUndMoeglich')

      if self.nSoc < self.nSocMin:
         return True # Nachladen nötig, wenn dann noch Sonne dazukommt, wird das toleriert

      # Einschalten zur nächsten vollen Stunde
      self.tEin = datetime.datetime(self.tNow.year,self.tNow.month,self.tNow.day,self.tNow.hour+1,0)

      # 48h-Vektor anlegen und füllen: 48 x Verbrauch(t_tagesprofil) + Solarertrag(t_prognose) + SOC(berechnet)
      # dabei die maximale Unterschreitung des SOCMin ermitteln und zurückliefern
      nSocMaxUnter = self.BerechneMaximaleSocUnterschreitung()

      if self.a48h[0].nSoc < self.nSocMin:
         self.Info2Log(f'Nachladen nötig, weil die untere SOC-Grenze innerhalb der nächsten Stunde unterschritten würde: {self.a48h[0].nSoc} < {self.nSocMin}')
         return True 

      if nSocMaxUnter == 0:
         self.Info2Log(f'Nachladen nicht nötig, weil die untere SOC-Grenze innerhalb der nächsten 48 Stunden nicht unterschritten wird')
         return False 

      self.Info2Log(f'Nachladen nötig, weil die untere SOC-Grenze innerhalb der nächsten 48 Stunden unterschritten würde: {self.nSocMin} --> {nSocMaxUnter}')

      # Wie lange wird das Nachladen dauern? 
      tSollEnde = self.BerechneLadungsEnde( nSocSoll=self.nSoc + nSocMaxUnter)

      # Ist Ausgleichen möglich? Ausgleichen ist verboten in Stunden, wo der Ertrag laut Prognose größer als 0,1kWh/h sein soll
      # D.h. prüfen: Wann kommt diese nächste Sonnenstunde? Ab da ist kein Laden möglich
      self.tAus = self.tLeer
      if self.BerechneAusschaltzeitpunkt(tSollEnde) == False:
         return False
      else:
         return True

      return False


   ###### IstAusgleichenAusschaltenMoeglichUndNötig(self) ##############################################################################
   def IstAusgleichenAusschaltenMoeglichUndNötig(self):
      print("IstAusgleichenAusschaltenMoeglichUndNötig")
      return False

   ###### AusgleichenAusschalten(self) ##############################################################################
   def AusgleichenAusschalten(self):
      print("AusgleichenAusschalten")

   ###### IstLadenAusschaltenMoeglich( self) ##############################################################################
   def IstLadenAusschaltenMoeglich( self):
      print("IstLadenAusschaltenMoeglich")
      return False

   ###### LadenAusschalten(self) ##############################################################################
   def LadenAusschalten(self):
      print("LadenAusschalten")


   ###### SchreibeDbusWerteInMariaDb(self) ##############################################################################
   def SchreibeDbusWerteInMariaDb(self):
      self.dErtrag = round(self.dErtragAbs-self.dErtragLast,2)
      cur = self.mdb.cursor()
      sStmt = "insert into db1.t_victdbus_stunde (tStunde, nSoc, dErtragAbs, dErtrag, dEmL1, dEmL2)\
                values (STR_TO_DATE('{0}', '%Y-%m-%d %H'), {1}, {2}, {3}, {4}, {5}  ) ON DUPLICATE KEY UPDATE nSoc={1}, dErtragAbs={2}, dErtrag={3}, dEmL1={4}, dEmL2={5}"
      sStmt = sStmt.format(self.sJetztStunde, self.nSoc, self.dErtragAbs, self.dErtrag, self.dVerbrauchL1, self.dVerbrauchL2)

      try:
         cur.execute( sStmt)
         self.mdb.commit()
         self.Info2Log(f'Dbus-Werte in DB aktualisiert: {self.nSoc}, {self.dErtragAbs}, {self.dErtrag}, {self.dVerbrauchL1}, {self.dVerbrauchL2}')

      except Exception as e:
         self.Error2Log(f'Fehler beim insert inmariadb.DB1.t_victdbus_stunde mit ({self.nSoc}, {self.dErtragAbs}, {round(self.dErtragAbs-self.dErtragLast,2)}): {e}')
         self.vScriptAbbruch()

      sStmt = f'update db1.t_charge_state set tAendDat=sysdate(), dErtrag={self.dErtragAbs}'

      try:
         cur.execute( sStmt)
         self.mdb.commit()
      except Exception as e:
         self.Error2Log(f'Fehler beim update von mariadb.DB1.t_charge_state mit (dErtrag={self.dErtragAbs}): {e}')
         self.vScriptAbbruch()




   ###### SchreibeStatusInMariaDb(self) ##############################################################################
   def SchreibeStatusInMariaDb(self):
      cur = self.mdb.cursor()
      sStmt = f'update db1.t_charge_state set eLadeart="{self.sLadeart}", tAendDat=sysdate() '

      try:
         cur.execute( sStmt)
      except Exception as e:
         self.Error2Log(f'Fehler beim update von mariadb.DB1.t_charge_state mit ({self.sLadeart}): {e}')
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
         self.Error2Log(f'GPIO-Status Pin {self.iGpioPinSensorAc} passt nicht zur Ladeart: {self.sAcSensor}, Ladeart: {self.sLadeart}')
       

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
         if ac.IstAusgleichenNoetigUndMoeglich():
            ac.LadenEinschalten( self.sLadeartAusgleichen )
         else:
            if ac.IstLadenNoetigUndMoeglich():
               ac.LadenEinschalten( self.sLadeartNachladen )

      elif ac.sLadeart == ac.sLadeartAusgleichen:    
         if ac.IstAusgleichenAusschaltenMoeglichUndNötig():
             ac.AusgleichenAusschalten()
          
      elif ac.sLadeart == ac.sLadeartNormal:    
         if ac.IstLadenAusschaltenMoeglich():
            ac.LadenAusschalten()

      else:
           self.Error2Log(f'Fehler: Unbekannte Ladeart: {ac.sLadeart}')


###### CBerechneEinAus  } ##############################################################################

ac = CBerechneEinAus()                    # Konfigdatei lesen 

while ac.VerbindeMitMariaDb() == False:   # Verbindung zur DB herstellen, zweite Verbindung fürs Log
   time.sleep(2)

ac.HoleLadeartAusDb()                     # In welchem Zustand ist das Ladegerät?
ac.HoleDbusWerteVomCerbo()                # Werte aus der Anlage lesen   
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





