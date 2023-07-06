import requests
import fileinput
import json
import datetime
import base64
import sys
import mariadb

tNow = datetime.datetime.now()
sNow = tNow.strftime("%Y-%m-%d-%H-%M")
tJetztStunde = datetime.datetime( tNow.year, tNow.month, tNow.day, tNow.hour, 0)


#***********************************************************************************/
# meteoblue-API exemplary request
#***********************************************************************************/
# Data packages / weather maps / images: pvpro-1h
# https://docs.meteoblue.com/en/weather-apis/packages-api/forecast-data#pv-pro
# liefert 
# - PV power in kWh
# - GTI Global Tilted Irradiance (Radiation) in W/m2
# 4 Wochen Test-Abo:
#	API calls per day (number): maximum 25/day
#	Service expiry (date): 15.06.2023
#
# Differenz zwischen den _instant und _backward-Datenreihen siehe https://content.meteoblue.com/en/research-education/specifications/weather-variables/radiation
# „The backwards value will be the average…So, for production, the backwards value is definitely more useful.”
# 
sPwd = "gibts bei MeteoBlue"
#OK api_url = "https://my.meteoblue.com/packages/pvpro-1h?apikey=********&lat=52.5244&lon=13.4105&asl=74&format=json&tz=Europe%2FBerlin&slope=30&kwp=1&facing=180&tracker=0&power_efficiency=0.85"

skWPeak = "1.4" # Kilowattpeak der installierten Solarkollektoren
iNeigung = 30 # Neigung der Solarmodule, z.B. 30 Grad
iRichtung = 210 #Ausrichtung der Solarmodule, z.B. 180 (Süd)
sEffizienz = "0.95" #Effizienz der Solarmodule, 0.2 ...1
sLongi = "13.4" # Länge
sLati = "52.6" # Breite

#Um Calls/Credits zu sparen kann das Script ab hier auch mit einer vorher gespeicherten Datei getestet werden:
#tNow = datetime.datetime(2023,7,5,10,21)
#sNow = tNow.strftime("%Y-%m-%d-%H-%M")
#sFile = "E:\\dev_priv\\python_svn\\solarprognose1\\webreq1\\meteoblue\\mb_pvpro_2023-07-05-10-19.json"
#f = open(sFile, "r")
#data = json.load(f)
#f.close()
api_url = "https://my.meteoblue.com/packages/pvpro-1h?apikey=" + sPwd + "&lat=" + sLati + "&lon=" + sLongi + "&format=json&tz=Europe%2FBerlin&slope=" + str(iNeigung) + "&kwp=" + skWPeak + "&facing=" + str(iRichtung) + "&tracker=0&power_efficiency=" + sEffizienz
response = requests.get(api_url)
data = response.json()


#für Vergleichszwecke auch noch als Datei speichern
sPretty = json.dumps( data, sort_keys=True, indent=2)
sFile = "E:\\dev_priv\\python_svn\\solarprognose1\\webreq1\\meteoblue\\mb_pvpro_" + sNow + ".json"
f = open(sFile, "w")
f.write( sPretty)
f.close()


modelrun = data['metadata']['modelrun_utc']
modelrun_upd = data['metadata']['modelrun_updatetime_utc']


try:
   conn = mariadb.connect( host="192.168.2.26", port=3306,#  ssl_ca="/path/to/skysql_chain.pem",
                           user="****", password="***")
except mariadb.Error as e:
   print(f"Error connecting to the database: {e}")
   sys.exit(1)

# Metadaten der Abfrage speichern
cur = conn.cursor()
stmt = "INSERT INTO db1.t_abfragen (tAbfrage, dLongitude, dLatitude, tModelRun, tModelRunUpdate, dkWPeak, iNeigung, iRichtung, dEffizienz) VALUES( CONVERT(%s,datetime), CONVERT(%s,double), CONVERT(%s,double), CONVERT(%s,datetime),CONVERT(%s,datetime),CONVERT(%s,double), %d, %d,CONVERT(%s,double))"
values = ( sNow, sLongi, sLati, modelrun, modelrun_upd,skWPeak, iNeigung, iRichtung, sEffizienz)
cur.execute( stmt,values)

 
# Solarprognosedaten der Abfrage speichern
for t in range(1,72): # bei 1 beginnen, weil der Durchschnitt (in der backward-Reihe) für [0]==00:00 nicht bekannt ist
                      # nur für die nächsten 48 Stunden speichern
                      # backwards-(Durchschnitts-)Reihe lesen (in der instant-Reihe steht der Momentanwert der vollen Stunden)
   sStunde = data['data_1h']['time'][t]
   tStunde = datetime.datetime.strptime(sStunde, '%Y-%m-%d %H:%M')

   if (tStunde <= tNow) :
      continue; # nur die Zukunft speichern

   if (tStunde.hour < 8 or 17 < tStunde.hour  ) :
      continue; # nur die für den Ertrag relevanten Stunden des Tages speichern

   
   tDiff = tStunde - tJetztStunde
   iStunden = (int)((tDiff.days * 86400 + tDiff.seconds) / 3600)
   
   sField = ""
   if iStunden >= 24:
      sField = "p24"
   elif iStunden >= 12:
      sField = "p12"
   elif iStunden >= 6:
      sField = "p6"
   elif iStunden >=3:
      sField = "p3"
   elif iStunden == 1:
      sField = "p1"
   else:
      continue

   dkWh = data['data_1h']['pvpower_backwards'][t]

   stmt = "insert into db1.t_prognose (stunde, " + sField + ") values(CONVERT('{0}',datetime), {1}) ON DUPLICATE KEY UPDATE " + sField + "={1}" 
   stmt = stmt.format(sStunde, dkWh)
   print(stmt)
   cur.execute( stmt,values)

  


conn.commit()


