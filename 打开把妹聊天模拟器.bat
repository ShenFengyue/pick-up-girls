@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1

set "BASE_PYTHON="
for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
) do (
    if not defined BASE_PYTHON if exist "%%~P" (
        "%%~P" --version >nul 2>&1
        if not errorlevel 1 set "BASE_PYTHON=%%~P"
    )
)

if not exist ".venv\Scripts\python.exe" (
    if not defined BASE_PYTHON (
        echo Python 3.10 or newer was not found. Install Python and run this file again.
        pause
        exit /b 1
    )
    echo Preparing the app the first time. This can take a few minutes...
    "%BASE_PYTHON%" -m venv --without-pip .venv
    if errorlevel 1 goto :failed
)

".venv\Scripts\python.exe" -c "import streamlit, openai, dotenv, keyring" >nul 2>&1
if errorlevel 1 (
    if not defined BASE_PYTHON (
        echo Could not locate Python to install the app dependencies.
        pause
        exit /b 1
    )
    echo Installing app dependencies. This is only needed once...
    "%BASE_PYTHON%" -m pip install --upgrade --target ".venv\Lib\site-packages" -r requirements.txt
    if errorlevel 1 goto :failed
)

".venv\Scripts\python.exe" -m streamlit run app.py --server.address 127.0.0.1 --server.showEmailPrompt false --browser.gatherUsageStats false
if errorlevel 1 (
    echo.
    echo The app stopped with an error. Check the message above.
    pause
)
endlocal
exit /b

:failed
echo.
echo Setup failed. Check your internet connection and the error above, then double-click this file again.
pause
endlocal
exit /b 1
