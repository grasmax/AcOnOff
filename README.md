# AcOnOff
Speicherbatterie in einer Photovoltaik-Insel nachladen oder ausgleichen

Ziel: Nachladen der Solar-Puffer-Batterien in Abhängigkeit vom Batterie-SOC und der Solarprognose
         durch Ein- und Ausschalten der Versorgung des MultiplusII-Chargers mit Stadtstrom an AC-IN
 Schaltprinzip:
    mb_pvpro.py holt die Solarprognose von MeteoBlue und schreibt sie in die Tabelle t_prognose
    in Planung: xx holt den SOC aus der Anlage schreibt den Wert in die Tabelle t_soc
    hier umgesetzt:
          CCBerechneEinAus.CBerechneEinAus() berechnet aus t_prognose und t_soc, ob und wie lange die Batterien geladen werden sollen 
          und schreibt in die Tabellen t_charge_state und t_charge_ticket
          Pythonscript relais2einaus() auf dem Master-Raspi (in Planung) steuert Relais2 auf dem Raspi-Relayboard 
    in Planung: Relais2 schaltet 48VDC- durch zum Klemmmenblock 3 im Verteilerkasten Solar
    Dadurch schaltet der Schütz im Verteilerkasten Solar 230VAC durch zu AC-IN des MultiplusII.
    Dadurch schaltet der MultiplussII das Ladegerät ein und versorgt alle an AC-Out1 angeschlossenen Verbraucher mit Stadtstrom.
 Überlegungen zum Laden der Batterien
    Unterscheiden: Nachladen(bis 90%) / Ausgleichsladen (ausreichend lange, bis alle Batterien und -Zellen ausgeglichen sind)
    Ladezustand und -verfahren wird in die DB-Tabelle t_charge_state gespeichert.
    Alle Ein- und Ausschaltvorgänge werden in die DB-Tabellen t_charge_ticket und t_charge_log gespeichert.

    Diese Berechung wird stündlich ausgeführt:
       In welchem Zustand ist das Ladegerät?
          AUS
             Eintrag in t_charge_log
             IstAusgleichenNoetigUndMoeglich?
                ja: AusgleichEin, Ende
                nein:IstLadenNötig?
                   ja: Ladenein, Ende
                   nein: Ende

          AUSGLEICHEN (bis 100%)
             Eintrag in t_charge_log
             IstAusgleichenAusMöglich?
                ja: AusgleichenAus, Ende
                nein: Ende

          LADEN (bis 90%)
             Eintrag in t_charge_log
             IstLadenAusMöglich?
                ja: LadenAus, Ende  <-- wenn Ausgleichen nötig, wird dies erst eine Stunde später eingeschaltet
                nein: Ende

    Es werden also folgende Funktionen gebraucht:
       Logeintrag(Art)      
          Art in t_charge_log und in t_charge_state eintragen(das Schalten über nimmt ein anderes Python-Script)
       IstAusgleichenNötig()
          ja, Wenn letzter 100%-SOC länger als n Wochen zurückliegt   
          sonst nein
       AusgleichEin()
          Logeintrag(AusgleichEin)
       IstLadenNötig()
          Beschreibung siehe unten
       LadenEin()
          Logeintrag(LadenEin)
       IstAusgleichenAusMöglich()
          ja, wenn SOC länger als n Stunden auf 100%
          sonst nein
       AusgleichenAus
          Logeintrag(AusgleichAus)
       IstLadenAusMöglich()
          ja, Wenn SOC größer 90%
          sonst nein      
       LadenAus()
          Logeintrag(LadenAus)

   Detaillierte Beschreibung zu IstLadenNötig()
    
       Ziele:
          Bei Blackout-Gefahr: 
          - Kapa permanent bei 100% halten, keine Solarunterstützung, Laden mit Stadtstrom permanent ein
          Bei Brownout-Gefahr, d.h. angekündigten Abschaltungen
          - Kapa vor der Abschaltung mit oder ohne Solarunterstützung auf 100% bringen
          Im Normalfall:
          - Für den lt. Prognose zu erwartender Solar-Ertrag muss Kapa in der Batterie freigelassen werden
          - Ausgleichs- und Nachladen nur dann, wenn laut Prognose mehr als 0,1kWh/h zu erwarten sind
          - Batterie-SOC zwischen 21 und 85 Prozent halten, 20% sind zusätzlich durch die Generatorregel im Cerbo abgesichert
              - SOC um 1700 am Ende des Solartages: 85% 
              - SOC um 0900 am Beginn des Solartages: 85% - NettoSolarertrag
          - Anzahl der Ein/Ausschaltvorgänge minimieren um die Schütze zu schonen
          - Nachladen im Idealfall nur nachts, wenn nur die Grundlast (Kühlung, Heizung, Fritzbox) gebraucht wird
          - KI-like beim Verbrauch mit den historischen Werten der Jahreszeit rechnen
          - KI-like beim Ertragsprognose mit den historischen Werten der Jahreszeit rechnen

       Randbedingungen:
          SOC: 100% entsprechen 200Ah (4*50Ah)
          in einer Stunde kann die Batteriekapa mit einem Ladestrom von 230VAC/9,5A (per Konfig und Kabel vorgegeben, entsprechen ca. 50VDC/40A, das sind 40Ah)
              16.6.23: Ladestrom war im MPII auf 5A begrenzt...auf 20A erhöht, kommt auch an...         
                -->20A/h SOC kann pro Stunde um 10% erhöht werden
             Ladedauer von 20% auf 85%: 65% / 10% : 6,5h
          Durchschnittlicher Verbrauch in 24h: 4kWh = 40%
          Der Solarertrag reduziert sich um den Eigenverbrauch der Anlage
          In die Reichweitenberechnung gehen ein:
                +Solarprognose
                -Sofortverbrauch
                -Eigenverbrauch

       Umsetzung:
          stündlich prüfen
          aktuellen SOC betrachten
             SOC darf in der kommenden Stunde nicht unter 21% fallen
             nachts, wenn niemand auf Fehler reagieren kann: SOC darf zwischen 2200 und 0800 nicht unter 21% fallen
             nachts mit der 12h-Prognose rechnen, zwischen 9 und 17 mit den 6-3-1-Prognosen

       Beispielrechnung 0900:
          maximal möglicher Brutto-Solarertrag lt Prognose: 5kWh 
                minus Eigenverbrauch der Anlage von 1kWh, bleiben: 4kWh
                minus Sofortverbrauch im Haus von 1kWh, bleiben: 3kWh = 30% Netto-Solarertrag
          Fazit: 0900 darf der SOC nicht über 55% liegen
    
       Beispielrechnung 1700:
          maximal möglicher Brutto-Solarertrag lt Prognose für nächsten Tag: 5kWh 
                minus Eigenverbrauch der Anlage von 1kWh, bleiben: 4kWh
                minus Sofortverbrauch im Haus von 1kWh, bleiben: 3kWh = 30% Netto-Solarertrag
          Fazit: 0900 darf der SOC nicht über 55% liegen
          1700: SOC: 85%
          1700-0900: 16h / 2/3 vom Durchschnittsverbrauch des Hauses: 2,7kWh sind 27%
          Fazit: bis 0900 sinkt der SOC auf 58% 

       Beispielrechnung 14.6.,1300: SOC: 66%, Prognose: 2,9kWh - 0,58 (Anlage)  - 0,7 (Haus) = ~1,6kWh = 16%
          Fazit: 1700 SOC: 66+16=82% --> 3% fehlen zwar --> nicht einschalten

       Beispielrechnung 15.6.,1500: SOC: 63%, Ymppt=256kWh Prognose: 0,97kWh/Ist:0,88 - 0,3? (Anlage)  - 0,7 (Haus) = -0,1kWh = -1%
          Fazit: 1700 SOC: 63-1=62% --> es fehlen 23% bis Soll (85)
          1700-0900: 16h / 2/3 vom Durchschnittsverbrauch des Hauses: 2,7kWh sind 27%
          Annahme: bis 0900 sinkt der SOC auf 35% - wird knapp --> eigentlich kann sofort geladen werden
          Ist 16.6. 0900: 43% , war also zu pessimistisch
                grau, keine Sonne, Prognose trotzdem 3kWh?? Batterien müssen geladen und ausgeglichen werden -->Paneele aus, MPII über Generator auf "Laden"
       Neue Durchschnittswerte
       Istwerte: Arbeitstag Homeoffice: 15.6. 0930-1630: 7h 1kWh Verbrauch 0,143kWh/h   SOC: 54-->65: +11%=1,1kWh Summe: 2,2kWh
                  Abend/Nacht Grundlast: 15.6. 1630-16.6.0613 13h45 1,8kWh Verbrauch  0,131 kWh/h



