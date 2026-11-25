@echo off
setlocal

if exist "%~dp0devneya.exe" goto native
if exist "%~dp0dist\provider-preview\Start devneya preview.cmd" goto preview

echo Starting devneya in WSL...
wsl.exe --cd "%~dp0." --exec /bin/bash scripts/start-wsl.sh
goto result

:native
pushd "%~dp0." || goto result
".\devneya.exe"
set "result=%errorlevel%"
popd
goto finish

:preview
call "%~dp0dist\provider-preview\Start devneya preview.cmd"
exit /b %errorlevel%

:result
set "result=%errorlevel%"

:finish
if not "%result%"=="0" pause
exit /b %result%
