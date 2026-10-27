@echo off
rem HADES OS v3 launcher - ASCII only on purpose.
rem A Persian string in a .bat file depends on the console codepage and breaks
rem silently on cp1252; every human-readable string lives in the UTF-8 docs instead.
setlocal
cd /d "%~dp0"

if "%1"=="" goto menu
goto %1

:menu
echo HADES OS v3
echo   check  - structure + registry verification (doctor)
echo   build  - index, wiki site
echo   test   - the gate test battery (scratch vaults only, never this vault)
echo   all    - check + build
echo.
echo run: start.bat check
goto end

:check
py -3.10 15_SYSTEM\scripts\hades.py doctor
if errorlevel 1 echo. & echo DOCTOR REPORTED ERRORS - read the lines above
goto end

:index
py -3.10 15_SYSTEM\scripts\hades.py index
goto end

:build
py -3.10 15_SYSTEM\scripts\hades.py index
py -3.10 15_SYSTEM\scripts\wiki.py build
goto end

:wiki
py -3.10 15_SYSTEM\scripts\wiki.py serve
goto end

:test
py -3.10 15_SYSTEM\scripts\test_hades.py
goto end

:all
py -3.10 15_SYSTEM\scripts\hades.py doctor
py -3.10 15_SYSTEM\scripts\hades.py index
py -3.10 15_SYSTEM\scripts\wiki.py build
goto end

:end
endlocal
