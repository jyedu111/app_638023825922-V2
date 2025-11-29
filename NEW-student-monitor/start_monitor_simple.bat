@echo off
cls
title Student Monitor System

REM Kill any existing node processes
ECHO Cleaning up existing Node.js processes...
taskkill /F /IM node.exe >nul 2>&1
ECHO Cleanup complete!

ECHO Starting Student Monitor System...
ECHO -----------------------------------------

:LOOP
ECHO [%TIME%] Starting server...

REM Run the server using port 3001 directly
node server.js

ECHO [%TIME%] Server exited, restarting in 3 seconds...
ping -n 3 127.0.0.1 >nul

goto LOOP