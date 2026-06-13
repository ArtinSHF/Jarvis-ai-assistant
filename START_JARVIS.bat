@echo off
title J.A.R.V.I.S Launcher
echo [JARVIS] Installing/checking dependencies...
pip install -r requirements.txt --quiet
echo [JARVIS] Launching...
python jarvis.py
pause
