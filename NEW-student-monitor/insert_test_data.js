// 插入测试浏览记录数据
const sqlite3 = require('sqlite3').verbose();

const db = new sqlite3.Database('./data.db', (err) => {
  if (err) {
    console.error('❌ DB 连接失败:', err.message);
    return;
  }
  console.log('✅ SQLite 连接成功');

  // 生成一些过去24小时内的随机时间戳
  function getRandomTimestamp() {
    const now = new Date();
    const past = new Date(now.getTime() - 24 * 60 * 60 * 1000); // 24小时前
    return new Date(past.getTime() + Math.random() * (now.getTime() - past.getTime())).toISOString();
  }

  // 测试数据
  const testRecords = [
    ['test001', '192.168.1.101', 'baidu.com', 'https://www.baidu.com/search?q=编程学习', '百度搜索 - 编程学习', getRandomTimestamp()],
    ['test002', '192.168.1.102', 'zhihu.com', 'https://www.zhihu.com/question/123456', '知乎 - 如何高效学习编程', getRandomTimestamp()],
    ['test003', '192.168.1.103', 'qq.com', 'https://www.qq.com', '腾讯首页', getRandomTimestamp()],
    ['test001', '192.168.1.101', 'github.com', 'https://github.com/user/repo', 'GitHub 代码仓库', getRandomTimestamp()],
    ['test002', '192.168.1.102', 'bilibili.com', 'https://www.bilibili.com/video/av123456', '哔哩哔哩视频', getRandomTimestamp()]
  ];

  // 开始事务插入数据
  db.run('BEGIN TRANSACTION', (err) => {
    if (err) {
      console.error('❌ 开始事务失败:', err.message);
      db.close();
      return;
    }

    const stmt = db.prepare(`
      INSERT INTO browsing_records (student_id, student_ip, url, original_url, title, timestamp) 
      VALUES (?, ?, ?, ?, ?, ?)
    `);

    let count = 0;
    for (const record of testRecords) {
      stmt.run(record, (err) => {
        if (err) {
          console.error('❌ 插入数据失败:', err.message);
        } else {
          count++;
        }
      });
    }

    stmt.finalize(() => {
      db.run('COMMIT', (err) => {
        if (err) {
          console.error('❌ 提交事务失败:', err.message);
        } else {
          console.log(`✅ 成功插入 ${count} 条测试数据`);
        }
        db.close();
      });
    });
  });
});