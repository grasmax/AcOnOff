Hier werden Scriptdateien vorgestellt für die Benutzung in einer Photovoltaik-Insel.
Diese Scriptdateien sollen auf einem Raspberry Pi ausgeführt werden und die Stromversorgung für das Laden der Pufferbatterien steuern.
Die Entwicklung ist noch nicht abgeschlossen, erste Tests finden unter Windows 10 statt. Da GPIO unter Windows nicht zur Verfügung steht, wird die Funktionalität in der Testphase durch eine Hilfsklasse simuliert.
Das Laden der Batterie erfolgt in Abhängigkeit von der Solarprognose, die von https://www.meteoblue.com zur Verfügung gestellt wird.
In die Berechnung gehen auch Anlagenwerte wie SOC und Verbrauch ein, die über Victron ssh/dbus ermittelt werden.
Verbrauchswerte werden mit dem Zähler EM540 erfasst.
