@echo off
title 学生端部署工具
echo.
echo 📦 正在安装依赖...（需联网）
echo.

:: 尝试多种 Python 路径（兼容机房环境）
set "PYTHON=python"
where python >nul 2>&1 || set "PYTHON=py"
where py >nul 2>&1 || for %%i in ("C:\Python39\python.exe", "C:\Program Files\Python39\python.exe", "C:\Program Files\Python310\python.exe") do (
    if exist "%%i" set "PYTHON=%%i" && goto :python_found
)
where %PYTHON% >nul 2>&1 || (
    echo ❌ 未找到 Python！请先安装 Python 3.9+（勾选 "Add to PATH"）
    echo 或手动修改此脚本中的 PYTHON 变量指向正确的 Python 路径
    pause
    exit /b 1
)
:python_found

:: 安装依赖
%PYTHON% -m pip install --upgrade pip
%PYTHON% -m pip install -r requirements.txt

:: 创建开机自启
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
echo 正在创建开机自启配置...
copy /Y "%~dp0agent.vbs" "%STARTUP%\学生行为监控.vbs" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo ✅ 开机自启配置已添加
) else (
    echo ⚠️  无法添加开机自启（可能需要管理员权限）
)

echo.
echo ✅ 安装完成！
echo.
echo 下一步：
echo   1. 修改 student_agent.py 中 ENABLE_SCREENSHOT = True （如需截屏）
echo   2. 双击运行 agent.vbs （无黑窗后台运行）
echo   3. 或直接运行: %PYTHON% student_agent.py
echo.
pause