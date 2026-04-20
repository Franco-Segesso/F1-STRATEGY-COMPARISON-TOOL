@echo off
setlocal

cd /d "%~dp0"
echo [F1] Carpeta del proyecto: %CD%

set "PY_CMD="
where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "PY_CMD=py -3"
) else (
    where python >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        set "PY_CMD=python"
    )
)

if "%PY_CMD%"=="" (
    echo [ERROR] No se encontro Python en PATH.
    echo Instala Python 3.10+ y volve a ejecutar este archivo.
    pause
    exit /b 1
)

echo [F1] Usando interprete: %PY_CMD%

if not exist ".venv\Scripts\python.exe" (
    echo [F1] Creando entorno virtual .venv...
    %PY_CMD% -m venv .venv
    if %ERRORLEVEL% NEQ 0 goto :error
)

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] No se pudo crear o encontrar .venv\Scripts\python.exe
    goto :error
)

echo [F1] Actualizando pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if %ERRORLEVEL% NEQ 0 goto :error

echo [F1] Instalando dependencias de la app...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 goto :error

if exist "requirements-data.txt" (
    echo [F1] Instalando dependencias de datos ^(FastF1^)...
    ".venv\Scripts\python.exe" -m pip install -r requirements-data.txt
    if %ERRORLEVEL% NEQ 0 goto :error
)

echo [F1] Iniciando simulador...
".venv\Scripts\python.exe" f1_simulador_python.py
set "APP_EXIT=%ERRORLEVEL%"

if %APP_EXIT% NEQ 0 (
    echo [ERROR] El simulador termino con codigo %APP_EXIT%.
    pause
    exit /b %APP_EXIT%
)

echo [F1] Simulador cerrado correctamente.
exit /b 0

:error
echo [ERROR] Fallo la preparacion del entorno o la instalacion de dependencias.
pause
exit /b 1
