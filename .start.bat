@echo off
setlocal

set VENV_DIR=venv

REM Проверка наличия виртуального окружения
if not exist %VENV_DIR% (
    echo Virtual environment not found. Creating...
    python -m venv %VENV_DIR%
)

REM Проверка наличия requirements.txt
if exist requirements.txt (
    echo Checking if all dependencies from requirements.txt are installed...
    
    REM Получаем список установленных пакетов
    %VENV_DIR%\Scripts\pip freeze > installed_packages.txt

    REM Установка недостающих пакетов
    for /f "tokens=*" %%i in (requirements.txt) do (
        REM Проверка наличия пакета
        echo Checking %%i...
        %VENV_DIR%\Scripts\pip show %%i >nul 2>&1
        if errorlevel 1 (
            echo Installing %%i...
            %VENV_DIR%\Scripts\pip install %%i
        ) else (
            echo %%i is already installed.
        )
    )

    del installed_packages.txt
) else (
    echo requirements.txt not found.
)


cls
echo Running main.py...
%VENV_DIR%\Scripts\python.exe main.py

endlocal
pause
call %0
