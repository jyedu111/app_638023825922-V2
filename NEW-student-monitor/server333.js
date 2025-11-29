// server.js —— 精简版（无截图）
const express = require('express');
const sqlite3 = require('sqlite3').verbose();
const cors = require('cors');
const bodyParser = require('body-parser');

const app = express();
const PORT = 3000;

app.use(cors());
app.use(bodyParser.json());
app.use(express.static('public'));

const db = new sqlite3.Database('./data.db');

// ====== 创建表（无 screenshot 字段）======
db.serialize(() => {
  db.run(`
    CREATE TABLE IF NOT EXISTS browsing_records (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      student_id TEXT NOT NULL,
      url TEXT NOT NULL,
      title TEXT,
      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )`);
  db.run(`
    CREATE TABLE IF NOT EXISTS blacklist (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      domain TEXT NOT NULL UNIQUE
    )`);
});

// ====== 接收上报 ======
app.post('/api/report', (req, res) => {
  const { student_id, url, title } = req.body;
  if (!student_id || !url) return res.status(400).json({ error: '缺参数' });
  
  const domain = new URL(url).hostname.replace('www.', '').toLowerCase();
  db.get('SELECT 1 FROM blacklist WHERE ? LIKE "%" || domain || "%"', [domain], (err, row) => {
    const blacklisted = !!row;
    
    db.run(
      `INSERT INTO browsing_records (student_id, url, title) VALUES (?, ?, ?)`,
      [student_id, url, title || ''],
      (err) => res.json({ ok: true, blacklisted })
    );
  });
});

// ====== 获取最新记录 ======
app.get('/api/latest', (req, res) => {
  const limit = 100;
  db.all(`
    SELECT r.*, 
      CASE WHEN b.id IS NOT NULL THEN 1 ELSE 0 END AS blacklisted
    FROM browsing_records r
    LEFT JOIN blacklist b ON r.url LIKE '%' || b.domain || '%'
    ORDER BY r.timestamp DESC
    LIMIT ?
  `, [limit], (err, rows) => res.json(rows));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`✅ 服务端运行中 → http://10.1.82.202:${PORT}`);
});