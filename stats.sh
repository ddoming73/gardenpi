#!/bin/sh

# TODO dump this script and use subprocess.run()
# for now this is easier as subprocess throws an excepcion if any call returns non-zero

if [ "$1" = "check-network" ] ; then
    RES=$(systemctl is-active network-online.target)
    echo "$RES"
elif [ "$1" = "check-time" ] ; then
    RES=$(systemctl is-active systemd-time-wait-sync.service)
    echo "$RES"    
elif [ "$1" = "signal" ] ; then
    RSSI=$(iw wlan0 station dump | grep "signal:" | cut -f3 | cut -d' ' -f1)
    PERCENT=$(( ($RSSI+110) *10/7 ))
    echo "Signal: $RSSI dBm $PERCENT%"
elif [ "$1" = "ssid" ] ; then
    SSID=$(iw wlan0 info | grep ssid | cut -d' ' -f2)
    echo "SSID: $SSID" 
elif [ "$1" = "ip" ] ; then
    IP=$(hostname -I)
    echo "IP: $IP"
elif [ "$1" = "time" ] ; then
    TS=$(date +%H:%M:%S)
    echo "Time: $TS"    
fi