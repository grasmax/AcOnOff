Anlass für die Entwicklung: https://github.com/grasmax/s1/issues/11 und https://github.com/grasmax/s1/issues/6.

Hier werden Scriptdateien vorgestellt für die Benutzung in einer Photovoltaik-Insel.

Diese Scriptdateien sollen auf einem _Raspberry Pi_ ausgeführt werden und die Stromversorgung<br> für das Ausgleichen und Nachladen der Speicherbatterien ein- und ausschalten
([Schaltschema](https://github.com/grasmax/AcOnOff/blob/main/doc/gh_schaltschema.pdf)).

Die Entwicklung ist noch nicht abgeschlossen, Tests finden unter _Windows 10_ und _Raspberry Pi OS_ statt.<br> Da _GPIO_ unter _Windows_ nicht zur Verfügung steht, wird die Funktionalität beim Test unter _Windows_ durch eine Hilfsklasse simuliert.

Das Laden der Batterie erfolgt in Abhängigkeit von der Solarprognose, die von [_meteoblue_](https://www.meteoblue.com) zur Verfügung gestellt wird.
In die Berechnung gehen auch Anlagenwerte wie SOC und Verbrauch ein, die über _Victron_ ssh/dbus ermittelt werden.
Verbrauchswerte werden mit dem Zähler _EM540_ erfasst.

* gh_solarprognose.sql - Script zum Anlegen des Schemas für die MariaDB-Datenbank
* gh_mariadb_solarprognose.sql - Datenbank-Abfragen
* gh_gpioersatz.py - GPIO-Hilfsklasse für den Test von gh_mpIIAcOnOff.py unter Windows
* gh_mb_pvpro.py - Abfrage der Solarprognose und Speichern der Ergebnisse in die Datenbank
* mb_pvpro_2023-07-06-14-17.json - Ergebnis einer Abfrage der Solarprognose im json-Format
* gh_mpIIAcOnOff.py - Das eigentliche Schaltscript
* gh_mpIIAcOnOff.cfg - Alle Einstellungen für das Schaltscript
* gh_schaltschema.pdf - Schaltschema: Raspi-GPIO-Relaisboard-Stromstoßschalter-Leistungsschütz-MPII

Alle Scripte werden auf diesem Controller ausgeführt:
* Raspberry Pi CM4IO Board
* CM4001032 Raspberry Pi Compute Module 4, 1GB-RAM, 32GB-eMMC, BCM2711, ARM Cortex-A72
* raspberry pi os (32bit) v11
* IO CREST JMB582 2 Port SATA III PCI-e 3.0 x1 Non-RAID Controller Karte Jmicro Chipsatz SI-PEX40148 (https://github.com/geerlingguy/raspberry-pi-pcie-devices/issues/64)
* 2TB WD20EFZX
  
Die Inbetriebnahme des Controllers [hier](https://github.com/grasmax/AcOnOff/blob/main/doc/Inbetriebnahme%20eines%20Steuerrechners%20f%C3%BCr%20eine%20Photovoltaikinsel.pdf) beschrieben.

