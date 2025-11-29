@echo off
cls
title 学生监控系统 - 自动重启服务

REM 终止可能存在的node进程
ECHO 正在清理可能存在的Node.js进程...
taskkill /F /IM node.exe >nul 2>&1
ECHO 清理完成！

REM 设置使用3001端口（避免与可能的3000端口冲突）
set NODE_ENV=production
set PORT=3001

ECHO 正在启动学生监控系统服务...
ECHO 使用端口: %PORT%
ECHO 服务地址: http://localhost:%PORT%
ECHO 按Ctrl+C停止服务
ECHO -----------------------------------------

:LOOP
REM 记录重启时间
ECHO [%TIME%] 启动服务器...

REM 运行服务器并捕获退出码
node server.js
set EXIT_CODE=%ERRORLEVEL%

REM 显示退出信息
ECHO [%TIME%] 服务器退出，退出码: %EXIT_CODE%

REM 根据退出码决定是否重启
if %EXIT_CODE% EQU 0 (
    ECHO [%TIME%] 服务器正常退出，3秒后重启...
) else (
    ECHO [%TIME%] 服务器异常退出，5秒后重启...
    ping -n 5 127.0.0.1 >nul
)

REM 短暂延迟后重启
ping -n 3 127.0.0.1 >nul

REM 检查是否需要继续运行（通过检查是否存在stop.txt文件）
if exist stop.txt (
    ECHO 检测到停止信号，服务已停止。
    del stop.txt >nul 2>&1
    exit /b 0
)

goto LOOP