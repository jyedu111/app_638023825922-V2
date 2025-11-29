// 简单测试服务器，用于诊断运行问题
const http = require('http');
const PORT = 3002;

// 创建基本的HTTP服务器
const server = http.createServer((req, res) => {
  res.writeHead(200, {'Content-Type': 'text/plain'});
  res.end('测试服务器运行正常！\n');
});

// 启动服务器
server.listen(PORT, () => {
  console.log(`🎯 测试服务器启动在 http://localhost:${PORT}`);
  console.log(`⏰ 启动时间: ${new Date().toLocaleString()}`);
  console.log(`🔄 此服务器将持续运行...`);
});

// 防止进程退出的各种措施

// 1. 捕获所有异常
process.on('uncaughtException', (error) => {
  console.error(`🚨 捕获到异常: ${error.message}`);
  console.error(error.stack);
  console.log('🔧 服务器继续运行...');
});

// 2. 捕获未处理的Promise拒绝
process.on('unhandledRejection', (reason, promise) => {
  console.error(`🚨 Promise拒绝: ${reason}`);
  console.log('🔧 服务器继续运行...');
});

// 3. 服务器错误处理
server.on('error', (error) => {
  console.error(`🚨 服务器错误: ${error.message}`);
  console.log('🔧 尝试保持服务器运行...');
});

// 4. 高频心跳机制（每5秒）
setInterval(() => {
  const now = new Date().toLocaleString();
  console.log(`💓 心跳检查 - ${now}`);
}, 5000);

// 5. 保持事件循环活跃
setInterval(() => {
  // 空操作但保持事件循环活跃
  process.stdout.write('');
}, 1000);

// 6. 忽略终止信号（仅用于测试）
process.on('SIGTERM', () => {
  console.log('🚫 忽略终止信号SIGTERM');
});

process.on('SIGINT', () => {
  console.log('🚫 忽略中断信号SIGINT (Ctrl+C)');
});

console.log('🛡️  所有安全措施已启用');
console.log('📝 服务器将尝试无限期运行...');