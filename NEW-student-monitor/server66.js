// server.js —— 启动时自动初始化数据库（含 student_ip）
const express = require('express');
const sqlite3 = require('sqlite3').verbose();
const cors = require('cors');
const bodyParser = require('body-parser');

const app = express();
const PORT = 3000;

app.use(cors());
app.use(bodyParser.json());
app.use(express.static('public'));

// 连接数据库（自动创建 data.db）
const db = new sqlite3.Database('./data.db', (err) => {
  if (err) {
    console.error('❌ DB 连接失败:', err.message);
  } else {
    console.log('✅ SQLite 连接成功');
    // 启动时自动初始化表结构
    initDatabase();
  }
});

// ====== 初始化数据库 ======
function initDatabase() {
  // 创建 browsing_records 表（含 student_ip）
  db.run(`
    CREATE TABLE IF NOT EXISTS browsing_records (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      student_id TEXT NOT NULL,
      student_ip TEXT,
      url TEXT NOT NULL,
      title TEXT,
      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )`, (err) => {
      if (err) return console.error('❌ records 表创建失败:', err.message);
      console.log('✅ browsing_records 表就绪');
    });

  // 创建 blacklist 表
  db.run(`
    CREATE TABLE IF NOT EXISTS blacklist (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      domain TEXT NOT NULL UNIQUE
    )`, (err) => {
      if (err) return console.error('❌ blacklist 表创建失败:', err.message);
      console.log('✅ blacklist 表就绪');

      // 插入初始黑名单（若不存在）
      const initDomains = ['qq.com', 'youku.com', 'games.com', 'douyu.com'];
      initDomains.forEach(domain => {
        db.run(
          `INSERT OR IGNORE INTO blacklist (domain) VALUES (?)`,
          [domain],
          (err) => {
            if (err) console.error(`❌ 插入 ${domain} 失败:`, err.message);
          }
        );
      });
      console.log('✅ 初始黑名单已加载');
    });
}

// ====== API 接口 ======
app.get('/api/blacklist', (req, res) => {
  db.all('SELECT domain FROM blacklist ORDER BY domain', (err, rows) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json(rows.map(r => r.domain));
  });
});

app.post('/api/blacklist/add', (req, res) => {
  const { domain } = req.body;
  if (!domain) return res.status(400).json({ error: '需提供 domain' });
  db.run('INSERT OR IGNORE INTO blacklist (domain) VALUES (?)', 
    [domain.trim().toLowerCase()], 
    function (err) {
      if (err) return res.status(500).json({ error: '插入失败' });
      res.json({ ok: true, id: this.lastID });
    }
  );
});

app.delete('/api/blacklist/:domain', (req, res) => {
  db.run('DELETE FROM blacklist WHERE domain = ?', [req.params.domain], (err) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json({ ok: true });
  });
});

// 接收学生端上报（兼容你当前 student_agent.py.txt，但建议升级 IP）
app.post('/api/report', (req, res) => {
  const { student_id, url, title, blacklisted } = req.body;
  if (!student_id || !url) return res.status(400).json({ error: '缺 student_id 或 url' });

  // 尝试提取 IP（兼容旧版无 IP 的上报）
  let student_ip = '';
  try {
    // 如果 url 是有效 URL，尝试从它提取域名用于黑名单匹配
    const urlObj = new URL(url);
    student_ip = urlObj.hostname.includes('10.1.82.') ? urlObj.hostname : '';
  } catch (e) {
    // 忽略
  }

  db.run(
    `INSERT INTO browsing_records (student_id, student_ip, url, title) VALUES (?, ?, ?, ?)`,
    [student_id, student_ip, url, title || ''],
    (err) => {
      if (err) return res.status(500).json({ error: '写入失败' });
      res.json({ ok: true, blacklisted: !!blacklisted });
    }
  );
});

// 返回最新记录
app.get('/api/latest', (req, res) => {
  const limit = 100;
  db.all(`
    SELECT r.*, 
      CASE WHEN b.id IS NOT NULL THEN 1 ELSE 0 END AS blacklisted
    FROM browsing_records r
    LEFT JOIN blacklist b ON r.url LIKE '%' || b.domain || '%'
    ORDER BY r.timestamp DESC
    LIMIT ?
  `, [limit], (err, rows) => {
    if (err) return res.status(500).json({ error: err.message });
    // 兜底：若 student_ip 为空，显示 —
    res.json(rows.map(r => ({ ...r, student_ip: r.student_ip || '—' })));
  });
});

// 启动服务
app.listen(PORT, '0.0.0.0', () => {
  console.log(`✅ 服务端已启动 → http://10.1.82.202:${PORT}`);
  console.log(`📁 数据库：./data.db（自动初始化）`);
});