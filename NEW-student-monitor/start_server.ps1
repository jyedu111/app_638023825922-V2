# 启动学生监控系统服务器并保持运行
Write-Host "正在启动学生监控系统服务器..."
while ($true) {
    try {
        # 启动服务器
        node server.js
        Write-Host "服务器意外退出，正在重启..."
        Start-Sleep -Seconds 2
    } catch {
        Write-Host "启动服务器时出错: $_"
        Start-Sleep -Seconds 2
    }
}