
# Achtung! Alle Stunden-Angaben verstehen sich als das Ende der Stunde. Im Sinne von: bis dahin gab es Solarertrag. Oder: bis dahin wurden kWh verbraucht.


# für mpIIaconoff.py


CREATE TABLE `t_charge_log` (
	`tLog` DATETIME NULL DEFAULT NULL COMMENT 'Wann wurde ein- oder ausgeschaltet',
	`eTyp` VARCHAR(20) NULL DEFAULT NULL COMMENT 'Info oder Fehler' COLLATE 'utf8mb4_general_ci',
	`eLadeart` VARCHAR(20) NULL DEFAULT NULL COMMENT 'Aus...Stromzufuhr ist ausgeschaltet (kein Laden), Voll...Absorbtions/Ausgleichsladung bis auf 100%, Nach..Batterie unter Beachtung der Solarprognose zwischen 20 und 90 % halten' COLLATE 'utf8mb4_general_ci',
	`sText` VARCHAR(250) NULL DEFAULT NULL COMMENT 'Fehler oder Infotext, z.B. Grund für das Ein- oder Ausschalten' COLLATE 'utf8mb4_general_ci'
)
COMMENT='Tabelle speichert, wann und warum die Stromzufuhr (AC-IN) für den MultiplusII-Charger ein oder ausgeschaltet wurde'
COLLATE='utf8mb4_general_ci'
ENGINE=InnoDB
;

CREATE TABLE `t_charge_ticket` (
	`eSchaltart` VARCHAR(20) NULL DEFAULT NULL COMMENT 'ausschalten...Stromzufuhr ausschalten (kein Laden), einschalten...Stromzufuhr einschalten für Nachladen oder ausgleichen' COLLATE 'utf8mb4_general_ci',
	`tAnlDat` DATETIME NULL DEFAULT NULL COMMENT 'Wann wurde das Ticket angelegt',
	`tSoll` DATETIME NULL DEFAULT NULL COMMENT 'Wann soll eingeschaltet werden',
	`tIst` DATETIME NULL DEFAULT NULL COMMENT 'Tatsächlicher Schaltzeitpunkt',
	`tSollAus` DATETIME NULL DEFAULT NULL COMMENT 'Nur bei Einschalt-Ticket (informativ): Wann eingeschaltet werden soll',
	`sGrund` VARCHAR(30) NULL DEFAULT NULL COMMENT 'Nur bei Einschalt-Ticket (informativ): Nachladen oder Ausgleichen',
)
COMMENT='Tabelle enthält alle Tickets für Schaltvorgänge. Die Tickets werden von mpIIcalcaconoff.py angelegt und von mpIIaconoff abgearbeitet.'
COLLATE='utf8mb4_general_ci'
ENGINE=InnoDB
;

CREATE TABLE `t_victdbus_stunde` (
	`tStunde` DATETIME NOT NULL,
	`dErtragAbs` DOUBLE NULL DEFAULT NULL COMMENT 'Gesamt-Solarertrag in kWh',
	`dErtrag` DOUBLE NULL DEFAULT NULL COMMENT 'Solarertrag der letzten Stunde in kWh',
	`dSocAbs` DOUBLE NULL DEFAULT NULL COMMENT 'Aktueller SOC in Prozent',
	`dSoc` DOUBLE NULL DEFAULT NULL COMMENT 'Änderung des SOC in der letzten Stunde  in Prozent',
	`dEmL1Abs` DOUBLE NULL DEFAULT NULL COMMENT 'Zählerstand L1: mit EM540 erfasster Verbrauch in kWh, gemessen am Ausgang AC-OUT1 des MPII',
	`dEmL1` DOUBLE NULL DEFAULT NULL COMMENT 'Änderung des Zählerstands L1 in der letzten Stunde: mit EM540 erfasster Verbrauch in kWh, gemessen am Ausgang AC-OUT1 des MPII',
	`dEmL2Abs` DOUBLE NULL DEFAULT NULL COMMENT 'Zählerstand L2: mit EM540 erfasster Verbrauch in kWh, gemessen am Eingang AC-IN des MPII',
	`dEmL2` DOUBLE NULL DEFAULT NULL COMMENT 'Änderung des Zählerstands L2 in der letzten Stunde: mit EM540 erfasster Verbrauch in kWh, gemessen am Eingang AC-IN des MPII',
	`dAnlagenVerbrauch` DOUBLE NULL DEFAULT NULL COMMENT 'Berechneter Anlagenverbrauch: (dStadt(L2) + dErtrag ) - (dBatt (Soc)   + dHaus (L1))',
	PRIMARY KEY (`tStunde`) USING BTREE
)
COMMENT='per ssh und dbus abgefragte Werte direkt aus der Anlage'
COLLATE='utf8mb4_general_ci'
ENGINE=InnoDB
;

CREATE TABLE `t_tagesprofil` (
	`nStunde` INT NOT NULL COMMENT '1..24. 1..bis 01:00 wurde etwas verbraucht',
	`dKwhHaus` DOUBLE NULL DEFAULT NULL COMMENT 'Durchschnitts-Verbrauch der Verbraucher im Solarteil der Hausinstallation in kWh',
	`dKwhAnlage` DOUBLE NULL DEFAULT NULL COMMENT 'Durchschnittlicher Eigenverbrauch der Anlage in kWh',
	`dKwhHausMin` DOUBLE NULL DEFAULT NULL COMMENT 'Minimaler der Verbraucher im Solarteil der Hausinstallation in kWh',
	`dKwhHausMax` DOUBLE NULL DEFAULT NULL COMMENT 'Maximaler der Verbraucher im Solarteil der Hausinstallation in kWh',
	`dKwhAnlageMin` DOUBLE NULL DEFAULT NULL COMMENT 'Minimaler Eigenverbrauch der Anlage in kWh',
	`dKwhAnlageMax` DOUBLE NULL DEFAULT NULL COMMENT 'Maximaler Eigenverbrauch der Anlage in kWh',
	PRIMARY KEY (`nStunde`) USING BTREE
)
COMMENT='24 Datensätze für jede Stunde eines Tages'
COLLATE='utf8mb4_general_ci'
;
delete from t_tagesprofil;
SELECT * FROM t_tagesprofil;
INSERT INTO `t_tagesprofil` (`nStunde`, `dKwhHaus`, `dKwhAnlage`, `dKwhHausMin`, `dKwhHausMax`, `dKwhAnlageMin`, `dKwhAnlageMax`) VALUES (1, 0.1, 0.025, 0.1, 0.1, 0.025, 0.025);
INSERT INTO `t_tagesprofil` (`nStunde`, `dKwhHaus`, `dKwhAnlage`, `dKwhHausMin`, `dKwhHausMax`, `dKwhAnlageMin`, `dKwhAnlageMax`) VALUES (2, 0.1, 0.03, 0.1, 0.15, 0.025, 0);
INSERT INTO `t_tagesprofil` (`nStunde`, `dKwhHaus`, `dKwhAnlage`, `dKwhHausMin`, `dKwhHausMax`, `dKwhAnlageMin`, `dKwhAnlageMax`) VALUES (3, 0.1, 0.02, 0.1, 0.2, 0.025, 0);
INSERT INTO `t_tagesprofil` (`nStunde`, `dKwhHaus`, `dKwhAnlage`, `dKwhHausMin`, `dKwhHausMax`, `dKwhAnlageMin`, `dKwhAnlageMax`) VALUES (4, 0.1, 0.02, 0.1, 0.1, 0.025, 0);
INSERT INTO `t_tagesprofil` (`nStunde`, `dKwhHaus`, `dKwhAnlage`, `dKwhHausMin`, `dKwhHausMax`, `dKwhAnlageMin`, `dKwhAnlageMax`) VALUES (5, 0.1, 0.03, 0.1, 0.2, 0.025, 0);
INSERT INTO `t_tagesprofil` (`nStunde`, `dKwhHaus`, `dKwhAnlage`, `dKwhHausMin`, `dKwhHausMax`, `dKwhAnlageMin`, `dKwhAnlageMax`) VALUES (6, 0.1, 0.02, 0.1, 0.1, 0.025, 0);
INSERT INTO `t_tagesprofil` (`nStunde`, `dKwhHaus`, `dKwhAnlage`, `dKwhHausMin`, `dKwhHausMax`, `dKwhAnlageMin`, `dKwhAnlageMax`) VALUES (7, 0.1, 0.02, 0.1, 0.2, 0.025, 0);
INSERT INTO `t_tagesprofil` (`nStunde`, `dKwhHaus`, `dKwhAnlage`, `dKwhHausMin`, `dKwhHausMax`, `dKwhAnlageMin`, `dKwhAnlageMax`) VALUES (8, 0.1, 0.03, 0.1, 0.2, 0.025, 0);
INSERT INTO `t_tagesprofil` (`nStunde`, `dKwhHaus`, `dKwhAnlage`, `dKwhHausMin`, `dKwhHausMax`, `dKwhAnlageMin`, `dKwhAnlageMax`) VALUES (9, 0.1, 0.02, 0.1, 0.2, 0.01, -0.08);
INSERT INTO `t_tagesprofil` (`nStunde`, `dKwhHaus`, `dKwhAnlage`, `dKwhHausMin`, `dKwhHausMax`, `dKwhAnlageMin`, `dKwhAnlageMax`) VALUES (10, 0.1, 0.03, 0.1, 0.2, 0.025, -0.07);
INSERT INTO `t_tagesprofil` (`nStunde`, `dKwhHaus`, `dKwhAnlage`, `dKwhHausMin`, `dKwhHausMax`, `dKwhAnlageMin`, `dKwhAnlageMax`) VALUES (11, 0.1, 0.02, 0.1, 0.2, 0.01, -0.07);
INSERT INTO `t_tagesprofil` (`nStunde`, `dKwhHaus`, `dKwhAnlage`, `dKwhHausMin`, `dKwhHausMax`, `dKwhAnlageMin`, `dKwhAnlageMax`) VALUES (12, 0.1, 0.03, 0.1, 0.2, 0.025, -0.08);
INSERT INTO `t_tagesprofil` (`nStunde`, `dKwhHaus`, `dKwhAnlage`, `dKwhHausMin`, `dKwhHausMax`, `dKwhAnlageMin`, `dKwhAnlageMax`) VALUES (13, 0.1, 0.02, 0.1, 0.2, 0.025, -0.08);
INSERT INTO `t_tagesprofil` (`nStunde`, `dKwhHaus`, `dKwhAnlage`, `dKwhHausMin`, `dKwhHausMax`, `dKwhAnlageMin`, `dKwhAnlageMax`) VALUES (14, 0.1, 0.03, 0.1, 0.2, 0.01, -0.08);
INSERT INTO `t_tagesprofil` (`nStunde`, `dKwhHaus`, `dKwhAnlage`, `dKwhHausMin`, `dKwhHausMax`, `dKwhAnlageMin`, `dKwhAnlageMax`) VALUES (15, 0.03, 0.01, 0.1, 0.2, 0.01, -0.08);
INSERT INTO `t_tagesprofil` (`nStunde`, `dKwhHaus`, `dKwhAnlage`, `dKwhHausMin`, `dKwhHausMax`, `dKwhAnlageMin`, `dKwhAnlageMax`) VALUES (16, 0.1, 0.02, 0.1, 0.2, 0.01, -0.06);
INSERT INTO `t_tagesprofil` (`nStunde`, `dKwhHaus`, `dKwhAnlage`, `dKwhHausMin`, `dKwhHausMax`, `dKwhAnlageMin`, `dKwhAnlageMax`) VALUES (17, 0.11, 0.03, 0.1, 0.2, 0.01, -0.05);
INSERT INTO `t_tagesprofil` (`nStunde`, `dKwhHaus`, `dKwhAnlage`, `dKwhHausMin`, `dKwhHausMax`, `dKwhAnlageMin`, `dKwhAnlageMax`) VALUES (18, 0.12, 0.02, 0.1, 0.2, 0.01, -0.09);
INSERT INTO `t_tagesprofil` (`nStunde`, `dKwhHaus`, `dKwhAnlage`, `dKwhHausMin`, `dKwhHausMax`, `dKwhAnlageMin`, `dKwhAnlageMax`) VALUES (19, 0.1, 0.03, 0.1, 0.2, 0.01, 0.01);
INSERT INTO `t_tagesprofil` (`nStunde`, `dKwhHaus`, `dKwhAnlage`, `dKwhHausMin`, `dKwhHausMax`, `dKwhAnlageMin`, `dKwhAnlageMax`) VALUES (20, 0.12, 0.02, 0.1, 0.2, 0.01, -1.49);
INSERT INTO `t_tagesprofil` (`nStunde`, `dKwhHaus`, `dKwhAnlage`, `dKwhHausMin`, `dKwhHausMax`, `dKwhAnlageMin`, `dKwhAnlageMax`) VALUES (21, 0.05, 0.02, 0.1, 0.3, 0.01, -0.3);
INSERT INTO `t_tagesprofil` (`nStunde`, `dKwhHaus`, `dKwhAnlage`, `dKwhHausMin`, `dKwhHausMax`, `dKwhAnlageMin`, `dKwhAnlageMax`) VALUES (22, 0.1, 0.02, 0.1, 0.3, 0.025, 0);
INSERT INTO `t_tagesprofil` (`nStunde`, `dKwhHaus`, `dKwhAnlage`, `dKwhHausMin`, `dKwhHausMax`, `dKwhAnlageMin`, `dKwhAnlageMax`) VALUES (23, 0.1, 0.02, 0.1, 0.3, 0.025, -0.1);
INSERT INTO `t_tagesprofil` (`nStunde`, `dKwhHaus`, `dKwhAnlage`, `dKwhHausMin`, `dKwhHausMax`, `dKwhAnlageMin`, `dKwhAnlageMax`) VALUES (24, 0.14, 0.03, 0.1, 0.3, 0.025, -0.1);
SELECT * FROM t_tagesprofil;

CREATE TABLE `t_charge_state` (
	`eLadeart` VARCHAR(20) NULL DEFAULT NULL COMMENT 'Aus...Stromzufuhr ist ausgeschaltet (kein Laden), Voll...Absorbtions/Ausgleichsladung bis auf 100%, Nach..Batterie unter Beachtung der Solarprognose zwischen 20 und 90 % halten' COLLATE 'utf8mb4_general_ci',
	`tAendDat` DATETIME NULL DEFAULT NULL COMMENT 'Wann wurden EIN und AUS berechnet und eingeschaltet',
	`tLetzterAusgleich` DATETIME NULL DEFAULT NULL COMMENT 'Wann das letzte Ausgleichs-Laden stattgefunden hat',
	`nAnzStunden` INT(11) NULL DEFAULT NULL COMMENT 'Basis für die Berechnung des Stundendurchschnitts im Tagesprofil'
)
COMMENT='Tabelle speichert, ob die Stromzufuhr (AC-IN) für den MultiplusII-Charger ein oder ausgeschaltet ist, wann das letzte Ausgleichsladen stattgefunden hat und den letzten Solarertrag'
COLLATE='utf8mb4_general_ci'
ENGINE=InnoDB
;
INSERT INTO `t_charge_state` (`eLadeart`, `tAendDat`, `tLetzterAusgleich`, `nAnzStunden`) VALUES ('nachladen', '2023-07-07 09:00:41', '2023-09-07 15:00:00', 0);



-- für mb_pvpro.py


CREATE TABLE `t_abfragen` (
	`tAbfrage` DATETIME NULL DEFAULT NULL COMMENT 'Zeitpunkt der Abfrage',
	`dLongitude` DOUBLE NULL DEFAULT NULL COMMENT 'Längengrad des Standorts',
	`dLatitude` DOUBLE NULL DEFAULT NULL COMMENT 'Breitengrad des Standortes',
	`tModelRun` DATETIME NULL DEFAULT NULL COMMENT 'Zeitpunkt des Prognoselaufs bei Meteoblue',
	`tModelRunUpdate` DATETIME NULL DEFAULT NULL COMMENT 'Zeitpunkt des Prognoseupdates bei Meteoblue',
	`dkWPeak` DOUBLE NULL DEFAULT NULL COMMENT 'Kilowattpeak der installierten Solarkollektoren',
	`iNeigung` INT(11) NULL DEFAULT NULL COMMENT 'Neigung der Solarmodule, z.B. 30 Grad',
	`iRichtung` INT(11) NULL DEFAULT NULL COMMENT 'Ausrichtung der Solarmodule, z.B. 180 (Süd)',
	`dEffizienz` DOUBLE NULL DEFAULT NULL COMMENT 'Effizienz der Solarmodule, 0.2 ...1'
)
COMMENT='speichert den Zeitpunkt der Abfrage der Solarprognose mit den wichtigsten Parametern\r\nabgefragt mit https://docs.meteoblue.com/en/weather-apis/packages-api/forecast-data#pv-pro \r\nin mb_pvpro.py'
COLLATE='utf8mb4_general_ci'
ENGINE=InnoDB
;

CREATE TABLE `t_prognose` (
	`Stunde` DATETIME NOT NULL COMMENT 'Datum und Uhrzeit der  Ertrags-Stunde',
	`P24` DOUBLE NULL DEFAULT NULL,
	`P12` DOUBLE NULL DEFAULT NULL,
	`P6` DOUBLE NULL DEFAULT NULL,
	`P3` DOUBLE NULL DEFAULT NULL,
	`P1` DOUBLE NULL DEFAULT NULL,
	PRIMARY KEY (`Stunde`) USING BTREE
)
COMMENT='Speichert zu jeder Stunde die 24-, 12-, 6-, 3- und 1-Stunden-Prognose\r\nabgefragt mit https://docs.meteoblue.com/en/weather-apis/packages-api/forecast-data#pv-pro \r\nin mb_pvpro.py'
COLLATE='utf8mb3_general_ci'
ENGINE=InnoDB
;

CREATE TABLE `t_prognose_log` (
	`tLog` DATETIME NULL DEFAULT NULL COMMENT 'Log-Zeitpunkt',
	`eTyp` VARCHAR(20) NULL DEFAULT NULL COMMENT 'Info oder Fehler' COLLATE 'utf8mb4_general_ci',
	`sText` VARCHAR(250) NULL DEFAULT NULL COMMENT 'Fehler oder Infotext' COLLATE 'utf8mb4_general_ci'
)
COMMENT='Tabelle speichert alle Info und Fehler beim Holen und Speichern der Solarprognose'
COLLATE='utf8mb4_general_ci'
ENGINE=InnoDB


-- für Daten, die aus dem Victron-Portal geholt wurden:


CREATE TABLE `t_victport_stunde` (
	`tStunde` DATETIME NOT NULL,
	`dErtragAbs` DOUBLE NULL DEFAULT NULL COMMENT 'Gesamter Solarertrag in kWh',
	`dErtrag` DOUBLE NULL DEFAULT NULL COMMENT 'Solarertrag in dieser Stunde in kWh',
	`dBattSOC` DOUBLE NULL DEFAULT NULL COMMENT 'Batterie-Ladezustand am Ende der Stunde in Prozent',
	`sAbsorption` VARCHAR(5) NULL DEFAULT NULL COMMENT 'j, wenn in der letzten Stunde Absorption erkannt wurde. Sonst n' COLLATE 'utf8mb4_general_ci',
	`dBattSpannung` DOUBLE NULL DEFAULT NULL COMMENT 'Batteriespannung am Ende der Stunde in Volt',
	`dMaxPvSpannung` DOUBLE NULL DEFAULT NULL COMMENT 'Maximale PV-Spannung der Stunde',
	`dMaxPvLeistung` DOUBLE NULL DEFAULT NULL COMMENT 'Maximale PV-Leistung der Stunde',
	`dMinBattStrom` DOUBLE NULL DEFAULT NULL COMMENT 'Minimaler Strom von/zur Batterie',
	`dMaxBattStrom` DOUBLE NULL DEFAULT NULL COMMENT 'Maximaler Strom von/zur Batterie',
	PRIMARY KEY (`tStunde`) USING BTREE
)
COMMENT='Auszug aus den Daten, die leider manuell per CSV-Export aus der Advanced-Seite des Victron-Portals geholt werden müssen.\r\nNachbearbeitet und importiert mit vp_import_csv_to_db.py\r\n'
COLLATE='utf8mb4_general_ci'
ENGINE=InnoDB
;


--  Auswertung
-- Views müssen über New/View angelegt werden!

v_eval_ticket_kwh
select 
`t`.`tSoll` AS `TicketZeit`,`t`.`eSchaltart` AS `TicketSchaltart`,
`s`.`tStunde` AS `EmDbusStunde`,
`s`.`dErtrag` AS `Solarertrag`,
`s`.`dSoc` AS `SOCDifferenz`,
`s`.`dEmL1` AS `Hausverbrauch`,
`s`.`dEmL2` AS `StadtstromVerbrauch`,
`s`.`dAnlagenVerbrauch` AS `AnlagenVerbrauch` 
from (`t_charge_ticket` `t` join `t_victdbus_stunde` `s`)
where `t`.`eSchaltart` like 'aus' 
	and `t`.`tSoll` = `s`.`tStunde`

v_eval_h_victrondata
SELECT DATE_FORMAT(y.tStunde , '%Y-%m-%d %H Uhr') Stunde , f.P24, f.P12, f.P6, f.P3, f.P1, round(y.dErtrag,2) Ist_kWh, 
round(y.dErtrag - f.P1, 2) DeltaP1, round(y.dErtrag - f.P3, 2) DeltaP3, round(y.dErtrag - f.P6, 2) DeltaP6,
round(y.dErtrag - f.P12, 2) DeltaP12, round(y.dErtrag - f.P24, 2) DeltaP24, 
y.sAbsorption Absorption, y.dMaxPvSpannung Max_PV_V, y.dBattSOC SOC, y.dBattSpannung Batt_V, y.dMaxPvLeistung MAX_PV_W, y.dMinBattStrom MIN_Batt_A, y.dMaxBattStrom MAX_Batt_A
from t_victport_stunde y, t_prognose f
WHERE y.tStunde = f.Stunde 


v_eval_h_localdata
SELECT DATE_FORMAT(f.Stunde , '%Y-%m-%d %H Uhr') Stunde , 
f.P24, f.P12, f.P6, f.P3, f.P1, round(y.dErtrag,2) Ist_kWh, 
round(y.dErtrag - f.P1, 2) DeltaP1, round(y.dErtrag - f.P3, 2) DeltaP3, round(y.dErtrag - f.P6, 2) DeltaP6,
round(y.dErtrag - f.P12, 2) DeltaP12, round(y.dErtrag - f.P24, 2) DeltaP24, 
y.dSosAbs SOC
from t_victdbus_stunde y, t_prognose f
WHERE y.tStunde = f.Stunde  ;



