@echo off
rem Forward classroom commands to the existing Kafka installation.
setlocal
set "KAFKA_CONFIGS=%~dp0..\..\infra\runtime\kafka_2.13-4.1.2\bin\windows\kafka-configs.bat"
if not exist "%KAFKA_CONFIGS%" (
    echo Kafka installation not found at "%KAFKA_CONFIGS%" 1>&2
    exit /b 1
)
call "%KAFKA_CONFIGS%" %*
exit /b %ERRORLEVEL%
