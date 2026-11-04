@echo off
REM SWEET daily statewide update, for Windows Task Scheduler.
REM Days whose SNODAS/SWANN files are not posted yet are retried on the next run.

set SWEET_DIR=C:\Users\mgersh\nm_swe
set CONDA_BAT=C:\Users\mgersh\AppData\Local\miniconda3\condabin\conda.bat
set ENV_NAME=nm_swe
set LOG=data\logs\task_scheduler.log

cd /d "%SWEET_DIR%" || exit /b 1
if not exist data\logs mkdir data\logs
echo ==== %DATE% %TIME% ==== >> %LOG%

if not exist "%CONDA_BAT%" (
  echo ERROR: conda.bat not found at %CONDA_BAT% >> %LOG%
  exit /b 1
)
call "%CONDA_BAT%" activate %ENV_NAME% >> %LOG% 2>&1
if errorlevel 1 (
  echo ERROR: could not activate conda environment %ENV_NAME% >> %LOG%
  exit /b 1
)

python -m src.daily_update >> %LOG% 2>&1
exit /b %errorlevel%