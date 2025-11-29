// 复制server.js但使用3001端口
const PORT = 3001;

// 读取原始server.js内容并替换端口
const fs = require('fs');
const originalContent = fs.readFileSync('server.js', 'utf8');
const modifiedContent = originalContent.replace('const PORT = 3000;', 'const PORT = 3001;');

fs.writeFileSync('temp_server.js', modifiedContent);

// 执行修改后的服务器
require('./temp_server.js');

console.log('注意：服务器现在运行在3001端口！');