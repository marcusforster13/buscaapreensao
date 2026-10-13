@echo off
rem Abre o visualizador three.js em http://localhost:8000 usando o Python que vem com o Blender.
cd /d "%~dp0"
start "" http://localhost:8000
"C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe" -m http.server 8000
