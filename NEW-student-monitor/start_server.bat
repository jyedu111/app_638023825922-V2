@echo off
cls
echo Starting student monitor server...

:LOOP
node server.js
echo Server restarting in 3 seconds...
ping localhost -n 4 > nul
goto LOOP