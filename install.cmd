@echo off
chcp 65001 >nul
setlocal
rem Set PYTHON to the intended virtual-environment interpreter.
if "%PYTHON%"=="" set PYTHON=python
"%PYTHON%" "%~dp0install.py" %*
exit /b %ERRORLEVEL%
