// server.js —— 无注释版（兼容 SQLite）
const express = require('express');
const sqlite3 = require('sqlite3').verbose();
const cors = require('cors');
const bodyParser = require('body-parser');

const app = express();
const PORT = 3000;

app.use(cors());
app.use(bodyParser.json());
app.use(express.static('public'));

const db = new sqlite3.Database('./data.db', (err) => {
  if (err) {
    console.error('❌ DB 连接失败:', err.message);
  } else {
    console.log('✅ SQLite 连接成功');
    initDatabase();
  }
});

function initDatabase() {
  db.run(`
    CREATE TABLE IF NOT EXISTS browsing_records (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      student_id TEXT NOT NULL,
      url TEXT NOT NULL,
      title TEXT,
      target_ip TEXT,
      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )`, (err) => {
      if (err) return console.error('❌ records 表创建失败:', err.message);
      console.log('✅ browsing_records 表就绪');
    });

  db.run(`
    CREATE TABLE IF NOT EXISTS blacklist (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      domain TEXT NOT NULL UNIQUE
    )`, (err) => {
      if (err) return console.error('❌ blacklist 表创建失败:', err.message);
      const domains = ['qq.com', 'youku.com', 'games.com'];
      domains.forEach(d => {
        db.run(`INSERT OR IGNORE INTO blacklist (domain) VALUES (?)`, [d]);
      });
      console.log('✅ blacklist 表及初始数据就绪');
    });
}

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

app.post('/api/report', (req, res) => {
  const { student_id, url, title, target_ip } = req.body;
  if (!student_id || !url) return res.status(400).json({ error: '缺参数' });

  let domain = '';
  try { domain = new URL(url).hostname.replace('www.', '').toLowerCase(); } catch {}

  db.get('SELECT 1 FROM blacklist WHERE ? LIKE "%" || domain || "%"', [domain], (err, row) => {
    const blacklisted = !!row;
    db.run(
      `INSERT INTO browsing_records (student_id, url, title, target_ip) VALUES (?, ?, ?, ?)`,
      [student_id, url, title || '', target_ip || ''],
      (err) => res.json({ ok: true, blacklisted })
    );
  });
});

app.get('/api/latest', (req, res) => {
  db.all(`
    SELECT r.*, 
      CASE WHEN b.id IS NOT NULL THEN 1 ELSE 0 END AS blacklisted
    FROM browsing_records r
    LEFT JOIN blacklist b ON r.url LIKE '%' || b.domain || '%'
    ORDER BY r.timestamp DESC
    LIMIT ?
  `, [50], (err, rows) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json(rows.map(r => ({ ...r, target_ip: r.target_ip || '—' })));
  });
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`✅ 服务端运行中 → http://10.1.82.202:${PORT}`);
});