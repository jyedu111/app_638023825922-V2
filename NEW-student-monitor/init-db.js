// init-db.js —— 自动初始化 SQLite 数据库
const sqlite3 = require('sqlite3').verbose();

const db = new sqlite3.Database('./data.db', (err) => {
  if (err) {
    console.error('❌ DB 连接失败:', err.message);
    return;
  }
  console.log('✅ SQLite 连接成功');

  // 创建表
  const createTables = `
    CREATE TABLE IF NOT EXISTS browsing_records (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      student_id TEXT NOT NULL,
      student_ip TEXT,
      url TEXT NOT NULL,
      original_url TEXT,
      title TEXT,
      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS blacklist (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      domain TEXT NOT NULL UNIQUE,
      reason TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS ip_blacklist (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ip_address TEXT NOT NULL UNIQUE,
      reason TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    INSERT OR IGNORE INTO blacklist (domain, reason) VALUES 
    ('qq.com', '社交娱乐'),
    ('youku.com', '视频网站'),
    ('games.com', '游戏站点');
  `;

  db.exec(createTables, (err) => {
    if (err) {
      console.error('❌ 表创建失败:', err.message);
    } else {
      console.log('✅ 表已创建/更新完成');
      console.log('✅ 数据库初始化完成');
    }
    db.close();
  });
});