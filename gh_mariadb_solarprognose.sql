
SELECT * FROM db1.t_charge_log ORDER BY 1;
SELECT * FROM db1.t_charge_state;


select stunde,p1,p3,p6,p12,p24 from db1.t_prognose where Stunde BETWEEN  STR_TO_DATE('2023-06-22 10', '%Y-%m-%d %H') AND STR_TO_DATE('2023-06-22 17', '%Y-%m-%d %H')

SELECT * FROM db1.t_prognose ORDER BY 1;
SELECT max(p24),max(p12),max(p6),max(p3),max(p1) FROM db1.t_prognose ORDER BY 1;

SELECT * FROM db1.t_charge_state;
SELECT * FROM db1.t_charge_ticket ORDER BY tAnldat;
SELECT * FROM t_victdbus_stunde ORDER BY 1;

SELECT * from db1.v_eval_h ORDER BY Stunde;
SELECT * from db1.v_portal_yield_kwh_h;

