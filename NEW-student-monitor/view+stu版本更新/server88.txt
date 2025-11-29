// server.js —— 自动初始化数据库 + 支持 student_ip
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
    initDatabase();
  }
});

// ====== 初始化数据库 ======
function initDatabase() {
  // 创建主表（含 student_ip）
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

  // 创建黑名单表 + 初始数据
  db.run(`
    CREATE TABLE IF NOT EXISTS blacklist (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      domain TEXT NOT NULL UNIQUE
    )`, (err) => {
      if (err) return console.error('❌ blacklist 表创建失败:', err.message);
      
      // 插入初始黑名单
      const domains = ['qq.com', 'youku.com', 'games.com', 'douyu.com'];
      domains.forEach(d => {
        db.run(`INSERT OR IGNORE INTO blacklist (domain) VALUES (?)`, [d]);
      });
      console.log('✅ blacklist 表及初始数据就绪');
    });
}

// ====== API ======
app.get('/api/blacklist', (req, res) => {
  db.all('SELECT domain FROM blacklist ORDER BY domain', (err, rows) => {
    res.json(err ? { error: err.message } : rows.map(r => r.domain));
  });
});

app.post('/api/blacklist/add', (req, res) => {
  const { domain } = req.body;
  if (!domain) return res.status(400).json({ error: '需提供 domain' });
  db.run('INSERT OR IGNORE INTO blacklist (domain) VALUES (?)', [domain.trim().toLowerCase()], 
    function (err) {
      res.json(err ? { error: '插入失败' } : { ok: true, id: this.lastID });
    }
  );
});

app.delete('/api/blacklist/:domain', (req, res) => {
  db.run('DELETE FROM blacklist WHERE domain = ?', [req.params.domain], (err) => {
    res.json(err ? { error: err.message } : { ok: true });
  });
});

// 接收上报（兼容 stu44.py.txt，但建议升级 IP）
app.post('/api/report', (req, res) => {
  const { student_id, url, title, blacklisted } = req.body;
  if (!student_id || !url) return res.status(400).json({ error: '缺 student_id 或 url' });

  // 兼容旧版：若未传 IP，则尝试从 URL 或主机名提取（兜底）
  let student_ip = '';
  try {
    // 方法1：优先尝试从 hostname 提取局域网 IP
    student_ip = require('os').networkInterfaces()['以太网']?.find(iface => 
      iface.family === 'IPv4' && !iface.internal
    )?.address || '';
  } catch (e) {}

  db.run(
    `INSERT INTO browsing_records (student_id, student_ip, url, title) VALUES (?, ?, ?, ?)`,
    [student_id, student_ip, url, title || ''],
    (err) => res.json({ ok: true, blacklisted: !!blacklisted })
  );
});

// 返回最新记录（含 student_ip）
app.get('/api/latest', (req, res) => {
  db.all(`
    SELECT r.*, 
      CASE WHEN b.id IS NOT NULL THEN 1 ELSE 0 END AS blacklisted
    FROM browsing_records r
    LEFT JOIN blacklist b ON r.url LIKE '%' || b.domain || '%'
    ORDER BY r.timestamp DESC
    LIMIT ?
  `, [100], (err, rows) => {
    if (err) return res.status(500).json({ error: err.message });
    // 兜底：空 IP 显示 —
    res.json(rows.map(r => ({ ...r, student_ip: r.student_ip || '—' })));
  });
});

// 启动
app.listen(PORT, '0.0.0.0', () => {
  console.log(`✅ 服务端运行中 → http://10.1.82.202:${PORT}`);
});