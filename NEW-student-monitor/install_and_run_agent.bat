@echo off
REM install_and_run_agent.bat
REM 一键在 Windows 学生端部署并启动 student_agent

SETLOCAL ENABLEDELAYEDEXPANSION
cd /d "%~dp0"

echo ================================
echo 学生端代理 一键安装与启动
echo ================================

echo 检查 Python 是否可用...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
  echo.
  echo 错误: 未检测到 Python。请安装 Python 3.8+ 并勾选“Add to PATH”。
  pause
  exit /b 1
)

echo 创建虚拟环境 venv...
python -m venv venv

echo 激活虚拟环境并安装依赖（可能需要几分钟）...
call "%CD%\venv\Scripts\activate.bat"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo 生成静默运行脚本 agent.vbs
set PYTHONW=%CD%\venv\Scripts\pythonw.exe
if exist "%PYTHONW%" (
  >agent.vbs echo Set objShell = CreateObject("WScript.Shell")
  >>agent.vbs echo objShell.Run ""%PYTHONW%" "%CD%\\student_agent.py"", 0, False
) else (
  >agent.vbs echo Set objShell = CreateObject("WScript.Shell")
  >>agent.vbs echo objShell.Run "cmd /c "%CD%\\venv\\Scripts\\python.exe" "%CD%\\student_agent.py"", 0, False
)

echo
echo 已生成 agent.vbs，用于静默运行代理（双击或由脚本启动）。

echo 建议：在学生端设置后端地址为环境变量，例如：
echo   setx MONITOR_SERVER "http://10.1.82.202:3003"
echo 然后重启或重新登录使环境变量生效。

echo 正在以静默方式启动代理...
wscript.exe "%CD%\agent.vbs"

echo 启动完成。若需在前台调试，可运行：
echo   call "%%CD%%\venv\Scripts\activate.bat" && python student_agent.py
pause
