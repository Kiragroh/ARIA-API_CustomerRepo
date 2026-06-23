@echo off
title ARIA FHIR Tester
pushd "%~dp0"
start "" "http://127.0.0.1:8012/"
python server.py
popd
