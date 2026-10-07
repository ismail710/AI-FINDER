@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%CD%\src"
python -m freelancer_finder.web.server %*

