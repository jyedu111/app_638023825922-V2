// server.js —— 全功能服务端
const express = require('express');
const sqlite3 = require('sqlite3').verbose();
const cors = require('cors');
const bodyParser = require('body-parser');
const ExcelJS = require('exceljs'); // ✅ 用于导出 XLS
const fs = require('fs');
const path = require('path');

const app = express();
const PORT = 3000;
const DB_PATH = './data.db';

// 中间件
app.use(cors());
app.use(bodyParser.json({ limit: '10mb' })); // 允许大 payload（截屏）
app.use(express.static('public'));
app.use(express.urlencoded({ extended: true }));

// 连接 DB
const db = new sqlite3.Database(DB_PATH, (err) => {
  if (err) console.error('❌ DB 连接失败:', err.message);
  else console.log('✅ SQLite 连接成功');
});

// ──────────────── API ────────────────

// ✅ 接收学生端上报（支持截图）
app.post('/api/report', (req, res) => {
  const { student_id, url, title, screenshot } = req.body;
  if (!student_id || !url) return res.status(400).json({ error: '缺 student_id 或 url' });

  let domain;
  try {
    domain = new URL(url).hostname.replace('www.', '').toLowerCase();
  } catch {
    domain = 'invalid-url';
  }

  // 检查是否黑名单
  db.get('SELECT 1 FROM blacklist WHERE ? LIKE "%" || domain || "%"', [domain], (err, row) => {
    const isBlacklisted = !!row;

    // 插入记录（screenshot 可为 null）
    const stmt = db.prepare(`
      INSERT INTO browsing_records (student_id, url, title, screenshot)
      VALUES (?, ?, ?, ?)
    `);
    stmt.run(student_id, url, title || '', screenshot || null, function (err) {
      stmt.finalize();
      if (err) return res.status(500).json({ error: '数据库写入失败' });
      res.json({ ok: true, blacklisted: isBlacklisted });
    });
  });
});

// ✅ 获取最新记录（供前端轮询/SSE）
app.get('/api/latest', (req, res) => {
  const limit = Math.min(parseInt(req.query.limit) || 50, 200);
  db.all(`
    SELECT r.*, 
      CASE WHEN b.id IS NOT NULL THEN 1 ELSE 0 END AS blacklisted
    FROM browsing_records r
    LEFT JOIN blacklist b ON r.url LIKE '%' || b.domain || '%'
    ORDER BY r.timestamp DESC
    LIMIT ?
  `, [limit], (err, rows) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json(rows);
  });
});

// ✅ SSE 实时流（用于 index.html）
app.get('/api/stream', (req, res) => {
  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive'
  });

  let lastId = 0;
  db.get('SELECT MAX(id) as id FROM browsing_records', (err, row) => {
    if (row && row.id) lastId = row.id;
  });

  const interval = setInterval(() => {
    db.all(`
      SELECT r.*, 
        CASE WHEN b.id IS NOT NULL THEN 1 ELSE 0 END AS blacklisted
      FROM browsing_records r
      LEFT JOIN blacklist b ON r.url LIKE '%' || b.domain || '%'
      WHERE r.id > ?
      ORDER BY r.id ASC
    `, [lastId], (err, rows) => {
      if (err) return;
      rows.forEach(row => {
        lastId = Math.max(lastId, row.id);
        res.write(`data: ${JSON.stringify(row)}\n\n`);
      });
    });
  }, 2000);

  req.on('close', () => clearInterval(interval));
});

// ─────── ✅ 黑名单管理 API ───────
app.get('/api/blacklist', (req, res) => {
  db.all('SELECT id, domain, reason, created_at FROM blacklist ORDER BY created_at DESC', 
    (err, rows) => res.json(err ? { error: err.message } : rows)
  );
});

app.post('/api/blacklist/add', (req, res) => {
  const { domain, reason } = req.body;
  if (!domain) return res.status(400).json({ error: '需提供 domain' });
  db.run('INSERT OR IGNORE INTO blacklist (domain, reason) VALUES (?, ?)', 
    [domain.trim().toLowerCase(), reason || ''], 
    function(err) {
      if (err) return res.status(500).json({ error: '插入失败' });
      res.json({ ok: true, id: this.lastID });
    }
  );
});

app.delete('/api/blacklist/:id', (req, res) => {
  db.run('DELETE FROM blacklist WHERE id = ?', [req.params.id], (err) => {
    res.json(err ? { error: err.message } : { ok: true });
  });
});

// ─────── ✅ 导出 XLS ───────
app.get('/api/export/xls', async (req, res) => {
  try {
    const rows = await new Promise((resolve, reject) => {
      db.all(`
        SELECT 
          r.timestamp,
          r.student_id,
          r.url,
          r.title,
          CASE WHEN b.id IS NOT NULL THEN '是' ELSE '否' END AS blacklisted
        FROM browsing_records r
        LEFT JOIN blacklist b ON r.url LIKE '%' || b.domain || '%'
        ORDER BY r.timestamp DESC
      `, [], (err, data) => err ? reject(err) : resolve(data));
    });

    const workbook = new ExcelJS.Workbook();
    const sheet = workbook.addWorksheet('上网行为记录');
    
    sheet.columns = [
      { header: '时间', key: 'timestamp', width: 20 },
      { header: '学生ID', key: 'student_id', width: 15 },
      { header: '网址', key: 'url', width: 40 },
      { header: '标题', key: 'title', width: 30 },
      { header: '是否黑名单', key: 'blacklisted', width: 12 }
    ];

    rows.forEach(row => {
      sheet.addRow({
        timestamp: new Date(row.timestamp).toLocaleString('zh-CN'),
        student_id: row.student_id,
        url: row.url,
        title: row.title || '',
        blacklisted: row.blacklisted
      });
    });

    res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    res.setHeader('Content-Disposition', 'attachment; filename="behavior_' + new Date().toISOString().slice(0,10) + '.xlsx"');
    
    await workbook.xlsx.write(res);
    res.end();
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: '导出失败' });
  }
});

// ─────── 启动服务 ───────
app.listen(PORT, '0.0.0.0', () => {
  console.log(`🌐 服务已启动`);
  console.log(`👉 监控页: http://10.1.82.202:${PORT}`);
  console.log(`👉 管理后台: http://10.1.82.202:${PORT}/admin.html`);
  console.log(`👉 导出 XLS: http://10.1.82.202:${PORT}/api/export/xls`);
});