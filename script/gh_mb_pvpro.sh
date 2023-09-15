# Solarprognose von MeteoBlue holen und speichern

date   > /mnt/wd2tb/script/meteoblue_forecast/log/mb_pvpro_shlog.txt
echo 'Starte mb_pvpro.sh '  >>  /mnt/wd2tb/script/meteoblue_forecast/log/mb_pvpro_shlog.txt


cd /mnt/wd2tb/script/meteoblue_forecast
/usr/bin/python /mnt/wd2tb/script/meteoblue_forecast/mb_pvpro.py >>  /mnt/wd2tb/script/meteoblue_forecast/log/mb_pvpro_shlog.txt



