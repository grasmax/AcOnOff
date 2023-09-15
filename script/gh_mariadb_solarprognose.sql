SELECT * FROM t_abfragen ORDER BY tAbfrage DESC;
SELECT * FROM t_prognose ORDER BY Stunde ;
SELECT * FROM t_prognose_log ORDER BY tLog ;

SELECT * FROM t_charge_log ORDER BY tLog;
SELECT * FROM t_charge_state;
SELECT * FROM t_charge_ticket;
SELECT * FROM t_tagesprofil;
SELECT * FROM t_victdbus_stunde ORDER BY tstunde;

SELECT * from v_eval_h_victrondata ORDER BY Stunde;
SELECT * from v_eval_h_localdata ORDER BY Stunde;