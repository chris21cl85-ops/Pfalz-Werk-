@echo off
title PFALZ-WERK
cd /d "%~dp0"
py -3 start.py
if errorlevel 1 pause
