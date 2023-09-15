Hier werden Scriptdateien vorgestellt für die Benutzung in einer Photovoltaik-Insel.

Diese Scriptdateien sollen auf einem Raspberry Pi ausgeführt werden und die Stromversorgung für das Ausgleichen und Nachladen der Speicherbatterien ein- und ausschalten.

Die Entwicklung ist noch nicht abgeschlossen, erste Tests finden unter Windows 10 statt. Da GPIO unter Windows nicht zur Verfügung steht, wird die Funktionalität in der Testphase durch eine Hilfsklasse simuliert.

Das Laden der Batterie erfolgt in Abhängigkeit von der Solarprognose, die von https://www.meteoblue.com zur Verfügung gestellt wird.
In die Berechnung gehen auch Anlagenwerte wie SOC und Verbrauch ein, die über Victron ssh/dbus ermittelt werden.
Verbrauchswerte werden mit dem Zähler EM540 erfasst.

* gh_solarprognose.sql - Script zum Anlegen des Schemas für die MariaDB-Datenbank
* gh_mariadb_solarprognose.sql - Datenbank-Abfragen
* gh_gpioersatz.py - GPIO-Hilfsklasse für den Test von gh_mpIIAcOnOff.py unter Windows
* gh_mb_pvpro.py - Abfrage der Solarprognose und Speichern der Ergebnisse in die Datenbank
* mb_pvpro_2023-07-06-14-17.json - Ergebnis einer Abfrage der Solarprognose im json-Format
* gh_mpIIAcOnOff.py - Das eigentliche Schaltscript
* gh_mpIIAcOnOff.cfg - Alle Einstellungen für das Schaltscript
* gh_schaltschema.pdf - Schaltschema: Raspi-GPIO-Relaisboard-Stromstoßschalter-Leistungsschütz-MPII

Anlass für die Entwicklung: https://github.com/grasmax/s1/issues/11

Alle Scripte werden auf diesem Controller ausgeführt:
* Raspberry Pi CM4IO Board
* CM4001032 Raspberry Pi Compute Module 4, 1GB-RAM, 32GB-eMMC, BCM2711, ARM Cortex-A72
* raspberry pi os (32bit) v11
* IO CREST JMB582 2 Port SATA III PCI-e 3.0 x1 Non-RAID Controller Karte Jmicro Chipsatz SI-PEX40148 (https://github.com/geerlingguy/raspberry-pi-pcie-devices/issues/64)
* 2TB WD20EFZX
  
Die Inbetriebnahme des Controllers ist beschrieben in https://github.com/grasmax/AcOnOff/blob/main/Inbetriebnahme%20eines%20Steuerrechners%20f%C3%BCr%20eine%20Photovoltaikinsel.pdf

