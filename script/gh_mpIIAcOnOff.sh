# Unter Windows10 konnte man den SSH-Schluessel dauerhaft mit ssh-add hinterlegen.
# Unter raspberyy pi os  muss man den  Schluessel bei einem ssh-agent registrieren.
# An den vom System gestarteten Agent kommt man aber nicht ran.
# Deshalb wird hier vor der Ausfuehrung des Python-Scripts ein weiterer Agent gestartet und nach der Ausfuehrung wieder entfernt.

logfiletimestamp=$(date "+%Y%m%d_%H%M%S")

date   > /mnt/wd2tb/script/mpIIaconoff/log/mpIIaconoff_shlog_$logfiletimestamp.txt
echo 'Starte mpIIaconoff.sh '  >> /mnt/wd2tb/script/mpIIaconoff/log/mpIIaconoff_shlog_$logfiletimestamp.txt


# Einen neuen Agent starten:
eval "$(ssh-agent -s)" >> /mnt/wd2tb/script/mpIIaconoff/log/mpIIaconoff_shlog_$logfiletimestamp.txt

# Den ssh-Schluessel hinterlegen:
/usr/bin/ssh-add ~/.ssh/k4  >> /mnt/wd2tb/script/mpIIaconoff/log/mpIIaconoff_shlog_$logfiletimestamp.txt

# ssh-Variabelen ins Log schreiben:
env | grep SSH  >>/mnt/wd2tb/script/mpIIaconoff/log/mpIIaconoff_shlog_$logfiletimestamp.txt

# Man koennte nun auch hier DBUS-Werte abfragen.
# Da das nun aber auch im Python funktioniert, steht das hier nur noch zur Info:
# /usr/bin/ssh  root@192.168.2.38 "dbus -y com.victronenergy.system /Dc/Battery/Soc GetValue" > /mnt/wd2tb/script/mpIIaconoff/temp/soc.txt

# Rechnen und Schalten:
cd /mnt/wd2tb/script/mpIIaconoff
/usr/bin/python /mnt/wd2tb/script/mpIIaconoff/mpIIAcOnOff.py >> /mnt/wd2tb/script/mpIIaconoff/log/mpIIaconoff_shlog_$logfiletimestamp.txt

# Den Agenten wieder beenden:
eval "$(ssh-agent -k)"  >>/mnt/wd2tb/script/mpIIaconoff/log/mpIIaconoff_shlog_$logfiletimestamp.txt

