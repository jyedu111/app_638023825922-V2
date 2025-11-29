// Node.js服务器包装器，提供自动重启功能
const { spawn } = require('child_process');
const fs = require('fs');

let serverProcess = null;
let restartCount = 0;
const maxRestarts = 10; // 最大重启次数
const restartDelay = 3000; // 重启延迟（毫秒）

// 记录日志函数
function log(message) {
  const timestamp = new Date().toLocaleString();
  const logMessage = `[${timestamp}] ${message}\n`;
  console.log(logMessage);
  
  // 写入日志文件
  fs.appendFileSync('server_wrapper.log', logMessage, 'utf8');
}

// 启动服务器函数
function startServer() {
  if (restartCount >= maxRestarts) {
    log(`⚠️  达到最大重启次数(${maxRestarts})，停止自动重启`);
    return;
  }
  
  log(`🚀 启动学生监控系统服务器 (重启次数: ${restartCount})`);
  
  // 生成子进程运行server.js
  serverProcess = spawn('node', ['server.js'], {
    stdio: 'inherit', // 继承标准输入输出
    shell: true
  });
  
  serverProcess.on('exit', (code, signal) => {
    log(`🛑 服务器进程退出 - 退出码: ${code}, 信号: ${signal}`);
    
    // 如果服务器正常退出（代码0），也进行重启，确保服务持续运行
    if (code !== null || signal !== null) {
      restartCount++;
      log(`🔄 ${restartDelay/1000}秒后自动重启服务器`);
      setTimeout(startServer, restartDelay);
    }
  });
  
  serverProcess.on('error', (err) => {
    log(`❌ 服务器进程启动失败: ${err.message}`);
    restartCount++;
    log(`🔄 ${restartDelay/1000}秒后自动重启服务器`);
    setTimeout(startServer, restartDelay);
  });
}

// 处理终止信号
process.on('SIGTERM', () => {
  log('📢 接收到终止信号，正在关闭服务器...');
  if (serverProcess) {
    serverProcess.kill('SIGTERM');
  }
  process.exit(0);
});

process.on('SIGINT', () => {
  log('📢 接收到中断信号(Ctrl+C)，正在关闭服务器...');
  if (serverProcess) {
    serverProcess.kill('SIGINT');
  }
  process.exit(0);
});

// 启动监控服务
log('🎉 学生监控系统服务器包装器启动');
log(`⚙️  配置: 最大重启次数=${maxRestarts}, 重启延迟=${restartDelay/1000}秒`);
log(`📝 日志文件: server_wrapper.log`);
startServer();