// server.js —— 学生监控系统后端服务器
const express = require('express');
const sqlite3 = require('sqlite3').verbose();
const cors = require('cors');
const bodyParser = require('body-parser');
const ExcelJS = require('exceljs');
const app = express();
const PORT = 3001;

// 中间件配置
app.use(cors());
app.use(bodyParser.json());
app.use(express.static('public'));

// 数据库连接
const db = new sqlite3.Database('./data.db', (err) => {
  if (err) {
    console.error('❌ 数据库连接失败:', err.message);
  } else {
    console.log('✅ SQLite 数据库连接成功');
    initDatabase();
  }
});

// 初始化数据库
// 初始化数据库函数
function initDatabase() {
  // 使用事务确保所有表创建和初始化在一个原子操作中完成
  db.serialize(() => {
    // 首先删除旧表（如果存在）以确保干净的开始
    db.run('DROP TABLE IF EXISTS browsing_records');
    db.run('DROP TABLE IF EXISTS blacklist');
    db.run('DROP TABLE IF EXISTS ip_blacklist');
    
    // 创建浏览记录表 - 添加original_url字段
    db.run(`
      CREATE TABLE browsing_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        student_ip TEXT,
        url TEXT NOT NULL,
        original_url TEXT,
        title TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
      )`, (err) => {
      if (err) return console.error('❌ 浏览记录表创建失败:', err.message);
    });
    
    // 创建域名黑名单表 - 确保包含reason和created_at字段
    db.run(`
      CREATE TABLE blacklist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain TEXT NOT NULL UNIQUE,
        reason TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )`, (err) => {
      if (err) return console.error('❌ 域名黑名单表创建失败:', err.message);
      
      // 添加默认黑名单数据
      const initDomains = [
        { domain: 'qq.com', reason: '社交娱乐' },
        { domain: 'youku.com', reason: '视频网站' },
        { domain: 'games.com', reason: '游戏站点' },
        { domain: 'douyu.com', reason: '直播平台' }
      ];
      
      initDomains.forEach(({ domain, reason }) => {
        db.run(
          'INSERT INTO blacklist (domain, reason) VALUES (?, ?)',
          [domain, reason],
          function(err) {
            if (err && !err.message.includes('UNIQUE constraint failed')) {
              console.log(`⚠️ 添加默认域名 ${domain} 时出错:`, err.message);
            }
          }
        );
      });
    });
    
    // 创建IP黑名单表
    db.run(`
      CREATE TABLE ip_blacklist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ip_address TEXT NOT NULL UNIQUE,
        reason TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )`, (err) => {
      if (err) return console.error('❌ IP黑名单表创建失败:', err.message);
    });
    
    // 创建索引提升性能
    db.run('CREATE INDEX idx_records_student_id ON browsing_records(student_id)');
    db.run('CREATE INDEX idx_records_timestamp ON browsing_records(timestamp)');
    db.run('CREATE INDEX idx_records_url ON browsing_records(url)');
    db.run('CREATE INDEX idx_records_original_url ON browsing_records(original_url)');
    db.run('CREATE INDEX idx_blacklist_domain ON blacklist(domain)');
    db.run('CREATE INDEX idx_ip_blacklist_address ON ip_blacklist(ip_address)');
    
    // 完成后输出状态
    console.log('✅ browsing_records 表就绪');
    console.log('✅ blacklist 表及初始数据就绪');
    console.log('✅ ip_blacklist 表就绪');
    console.log('✅ 所有索引创建完成');
  });
}

// 获取域名黑名单
app.get('/api/blacklist/domains', (req, res) => {
  db.all('SELECT id, domain, reason, created_at FROM blacklist ORDER BY domain', (err, rows) => {
    if (err) return res.status(500).json({ error: '获取域名黑名单失败:' + err.message });
    res.json(rows);
  });
});

// 添加域名黑名单
app.post('/api/blacklist/domains/add', (req, res) => {
  const { domain, reason } = req.body;
  if (!domain || !domain.includes('.')) {
    return res.status(400).json({ error: '请输入有效域名（如：taobao.com）' });
  }
  const cleanDomain = domain.trim().toLowerCase();
  db.run(
    'INSERT OR IGNORE INTO blacklist (domain, reason) VALUES (?, ?)',
    [cleanDomain, reason || '无理由'],
    function (err) {
      if (err) return res.status(500).json({ error: '添加失败:' + err.message });
      if (this.lastID) {
        res.json({ ok: true, message: `域名 ${cleanDomain} 已加入黑名单` });
      } else {
        res.json({ ok: false, message: `域名 ${cleanDomain} 已在黑名单中` });
      }
    }
  );
});

// 删除域名黑名单
app.delete('/api/blacklist/domains/:id', (req, res) => {
  const id = req.params.id;
  db.run(
    'DELETE FROM blacklist WHERE id = ?',
    [id],
    function (err) {
      if (err) return res.status(500).json({ error: '删除失败:' + err.message });
      if (this.changes > 0) {
        res.json({ ok: true, message: '域名已从黑名单移除' });
      } else {
        res.json({ ok: false, message: '域名不存在于黑名单中' });
      }
    }
  );
});

// 获取IP黑名单
app.get('/api/blacklist/ips', (req, res) => {
  db.all('SELECT id, ip_address, reason, created_at FROM ip_blacklist ORDER BY ip_address', (err, rows) => {
    if (err) return res.status(500).json({ error: '获取IP黑名单失败:' + err.message });
    // 转换字段名以保持一致性
    const formattedRows = rows.map(row => ({
      ...row,
      ip: row.ip_address // 添加ip字段作为兼容
    }));
    res.json(formattedRows);
  });
});

// 添加IP黑名单
app.post('/api/blacklist/ips/add', (req, res) => {
  // 同时支持ip和ip_address字段
  const ip_address = req.body.ip_address || req.body.ip;
  const reason = req.body.reason;
  
  if (!ip_address || !/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(ip_address)) {
    return res.status(400).json({ error: '请输入有效IP地址（如：192.168.1.1）' });
  }
  const cleanIp = ip_address.trim();
  db.run(
    'INSERT OR IGNORE INTO ip_blacklist (ip_address, reason) VALUES (?, ?)',
    [cleanIp, reason || '无理由'],
    function (err) {
      if (err) return res.status(500).json({ error: '添加失败:' + err.message });
      if (this.lastID) {
        res.json({ ok: true, message: `IP地址 ${cleanIp} 已加入黑名单`, success: true });
      } else {
        res.json({ ok: false, message: `IP地址 ${cleanIp} 已在黑名单中` });
      }
    }
  );
});

// 删除IP黑名单 - 同时支持按id和按ip删除
app.delete('/api/blacklist/ips/:id', (req, res) => {
  const id = req.params.id;
  
  // 如果参数看起来像IP地址而不是ID，则按IP地址删除
  if (/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(id)) {
    db.run(
      'DELETE FROM ip_blacklist WHERE ip_address = ?',
      [id],
      function (err) {
        if (err) return res.status(500).json({ error: '删除失败:' + err.message });
        if (this.changes > 0) {
          res.json({ ok: true, message: 'IP地址已从黑名单移除', success: true });
        } else {
          res.json({ ok: false, message: 'IP地址不存在于黑名单中', error: 'IP不存在' });
        }
      }
    );
  } else {
    // 否则按ID删除
    db.run(
      'DELETE FROM ip_blacklist WHERE id = ?',
      [id],
      function (err) {
        if (err) return res.status(500).json({ error: '删除失败:' + err.message });
        if (this.changes > 0) {
          res.json({ ok: true, message: 'IP地址已从黑名单移除', success: true });
        } else {
          res.json({ ok: false, message: 'IP地址不存在于黑名单中', error: 'IP不存在' });
        }
      }
    );
  }
});

// 检查域名或IP是否在黑名单中（用于学生端快速验证）
app.post('/api/blacklist/check', (req, res) => {
  const { domain, ip } = req.body;
  let isBlacklisted = false;
  let reason = '';
  let type = '';
  
  // 检查域名
  if (domain) {
    db.get('SELECT reason FROM blacklist WHERE ? LIKE "%" || domain || "%"', [domain], (err, row) => {
      if (row) {
        isBlacklisted = true;
        reason = row.reason || '该域名在黑名单中';
        type = 'domain';
      }
      // 如果域名不在黑名单，检查IP
      if (!isBlacklisted && ip) {
        db.get('SELECT reason FROM ip_blacklist WHERE ip_address = ?', [ip], (err, ipRow) => {
          if (ipRow) {
            isBlacklisted = true;
            reason = ipRow.reason || '该IP地址在黑名单中';
            type = 'ip';
          }
          res.json({ blacklisted: isBlacklisted, reason, type });
        });
      } else {
        res.json({ blacklisted: isBlacklisted, reason, type });
      }
    });
  } else if (ip) {
    // 只检查IP
    db.get('SELECT reason FROM ip_blacklist WHERE ip_address = ?', [ip], (err, row) => {
      if (row) {
        isBlacklisted = true;
        reason = row.reason || '该IP地址在黑名单中';
        type = 'ip';
      }
      res.json({ blacklisted: isBlacklisted, reason, type });
    });
  } else {
    res.status(400).json({ error: '请提供域名或IP地址' });
  }
});

// 兼容GET请求的黑名单检查API
app.get('/api/check/blacklist', (req, res) => {
  const { url, ip } = req.query;
  
  // 从URL提取域名
  let domain = '';
  if (url) {
    try {
      if (url.includes('://')) {
        domain = url.split('://')[1].split('/')[0].replace(/^www\./, '').toLowerCase();
      } else {
        domain = url.split('/')[0].replace(/^www\./, '').toLowerCase();
      }
    } catch (e) {
      domain = url.trim().toLowerCase();
    }
  }
  
  // 检查域名黑名单
  if (domain) {
    db.get('SELECT reason FROM blacklist WHERE ? LIKE "%" || domain || "%"', [domain], (err, row) => {
      if (row) {
        res.json({ blacklisted: true, type: 'domain', reason: row.reason || '域名在黑名单中' });
      } else if (ip) {
        // 如果域名不在黑名单中，检查IP
        db.get('SELECT reason FROM ip_blacklist WHERE ip_address = ?', [ip], (err, ipRow) => {
          if (ipRow) {
            res.json({ blacklisted: true, type: 'ip', reason: ipRow.reason || 'IP在黑名单中' });
          } else {
            res.json({ blacklisted: false });
          }
        });
      } else {
        res.json({ blacklisted: false });
      }
    });
  } else if (ip) {
    // 只检查IP
    db.get('SELECT reason FROM ip_blacklist WHERE ip_address = ?', [ip], (err, row) => {
      if (row) {
        res.json({ blacklisted: true, type: 'ip', reason: row.reason || 'IP在黑名单中' });
      } else {
        res.json({ blacklisted: false });
      }
    });
  } else {
    res.status(400).json({ error: '缺少必要参数' });
  }
});

// 接收学生端上报
app.post('/api/report', (req, res) => {
  const { student_id, student_ip, url, domain: client_domain, title } = req.body;
  if (!student_id || !url) {
    return res.status(400).json({ error: '缺少必填参数（student_id/url）' });
  }

  // 使用学生端提供的域名，如果没有则自己提取
  let domain = client_domain || '';
  if (!domain) {
    try {
      // 提取域名并清理
      if (url.includes('://')) {
        domain = url.split('://')[1].split('/')[0].replace(/^www\./, '').toLowerCase();
      } else {
        domain = url.split('/')[0].replace(/^www\./, '').toLowerCase();
      }
    } catch (e) {
      domain = url.trim().toLowerCase();
    }
  }

  // 检查域名黑名单
  db.get(
    'SELECT 1 FROM blacklist WHERE ? LIKE "%" || domain || "%"',
    [domain],
    (err, row) => {
      const blacklisted = !!row;

      db.run(
        `INSERT INTO browsing_records 
         (student_id, student_ip, url, original_url, title) 
         VALUES (?, ?, ?, ?, ?)`,
        [
          student_id.trim(),
          student_ip || '未知IP',
          domain, // 存储清理后的域名
          url,    // 存储原始完整URL
          (title || '无标题').trim()
        ],
        (err) => {
          if (err) return res.status(500).json({ error: '记录存储失败:' + err.message });
          res.json({ 
            ok: true, 
            blacklisted,
            message: blacklisted ? '访问已记录（域名在黑名单中）' : '访问已记录'
          });
        }
      );
    }
  );
});

// 获取带过滤功能的浏览记录
app.get('/api/records', (req, res) => {
  const { student_id, domain, start_time, end_time, blacklisted, page = 1, page_size = 50 } = req.query;
  const limit = Math.min(Number(page_size) || 50, 100);
  const offset = (Number(page) - 1) * limit;
  
  let whereClause = [];
  let params = [];
  
  // 构建过滤条件
  if (student_id) {
    whereClause.push('r.student_id = ?');
    params.push(student_id);
  }
  
  if (domain) {
    whereClause.push('r.url LIKE ?');
    params.push('%' + domain + '%');
  }
  
  if (start_time) {
    whereClause.push('r.timestamp >= ?');
    params.push(start_time);
  }
  
  if (end_time) {
    whereClause.push('r.timestamp <= ?');
    params.push(end_time);
  }
  
  if (blacklisted === 'true') {
    whereClause.push('b.id IS NOT NULL');
  } else if (blacklisted === 'false') {
    whereClause.push('b.id IS NULL');
  }
  
  const whereStr = whereClause.length > 0 ? 'WHERE ' + whereClause.join(' AND ') : '';
  
  // 查询记录
  db.all(`
    SELECT 
      r.id,
      r.student_id,
      r.student_ip,
      r.url,
      r.original_url,
      r.title,
      r.timestamp,
      CASE WHEN b.id IS NOT NULL THEN 1 ELSE 0 END AS blacklisted,
      b.reason AS blacklist_reason
    FROM browsing_records r
    LEFT JOIN blacklist b ON r.url LIKE '%' || b.domain || '%'
    ${whereStr}
    ORDER BY r.timestamp DESC
    LIMIT ? OFFSET ?`,
    [...params, limit, offset],
    (err, rows) => {
      if (err) return res.status(500).json({ error: '获取记录失败:' + err.message });
      
      // 查询总数
      db.get(
        `SELECT COUNT(*) as total FROM browsing_records r
         LEFT JOIN blacklist b ON r.url LIKE '%' || b.domain || '%'
         ${whereStr}`,
        params,
        (countErr, countRow) => {
          if (countErr) return res.status(500).json({ error: '获取总数失败:' + countErr.message });
          
          const formattedRows = rows.map(row => ({
            ...row,
            student_ip: row.student_ip || '—',
            title: row.title || '—',
            timestamp: new Date(row.timestamp).toLocaleString('zh-CN')
          }));
          
          res.json({
            data: formattedRows,
            pagination: {
              current_page: Number(page),
              page_size: limit,
              total_items: countRow.total,
              total_pages: Math.ceil(countRow.total / limit)
            }
          });
        }
      );
    }
  );
});

// 获取最新记录（保持兼容性）
app.get('/api/latest', (req, res) => {
  const limit = Math.min(Number(req.query.limit) || 50, 100);

  db.all(`
    SELECT 
      r.id,
      r.student_id,
      r.student_ip,
      r.url,
      r.title,
      r.timestamp,
      CASE WHEN b.id IS NOT NULL THEN 1 ELSE 0 END AS blacklisted
    FROM browsing_records r
    LEFT JOIN blacklist b ON r.url LIKE '%' || b.domain || '%'
    ORDER BY r.timestamp DESC
    LIMIT ?`,
    [limit],
    (err, rows) => {
      if (err) return res.status(500).json({ error: '获取记录失败:' + err.message });
      const formattedRows = rows.map(row => ({
        ...row,
        student_ip: row.student_ip || '—',
        title: row.title || '—',
        timestamp: new Date(row.timestamp).toLocaleString('zh-CN')
      }));
      res.json(formattedRows);
    }
  );
});

// 获取统计信息
app.get('/api/stats', (req, res) => {
  // 获取总记录数
  db.get('SELECT COUNT(*) as total_records FROM browsing_records', (err1, row1) => {
    // 获取黑名单访问数
    db.get(`
      SELECT COUNT(*) as blacklisted_count 
      FROM browsing_records r
      JOIN blacklist b ON r.url LIKE '%' || b.domain || '%'`,
      (err2, row2) => {
        // 获取学生数
        db.get('SELECT COUNT(DISTINCT student_id) as student_count FROM browsing_records', (err3, row3) => {
          // 获取访问最多的域名
          db.all(`
            SELECT url, COUNT(*) as visit_count 
            FROM browsing_records 
            GROUP BY url 
            ORDER BY visit_count DESC 
            LIMIT 10`,
            (err4, topDomains) => {
              res.json({
                total_records: row1?.total_records || 0,
                blacklisted_count: row2?.blacklisted_count || 0,
                student_count: row3?.student_count || 0,
                top_domains: topDomains || []
              });
            }
          );
        });
      }
    );
  });
});

// 导出数据到Excel
app.get('/api/export/excel', async (req, res) => {
  const { student_id, domain, start_time, end_time, blacklisted } = req.query;
  
  try {
    // 构建查询条件
    let whereClause = [];
    let params = [];
    
    if (student_id) {
      whereClause.push('r.student_id = ?');
      params.push(student_id);
    }
    
    if (domain) {
      whereClause.push('r.url LIKE ?');
      params.push('%' + domain + '%');
    }
    
    if (start_time) {
      whereClause.push('r.timestamp >= ?');
      params.push(start_time);
    }
    
    if (end_time) {
      whereClause.push('r.timestamp <= ?');
      params.push(end_time);
    }
    
    if (blacklisted === 'true') {
      whereClause.push('b.id IS NOT NULL');
    } else if (blacklisted === 'false') {
      whereClause.push('b.id IS NULL');
    }
    
    const whereStr = whereClause.length > 0 ? 'WHERE ' + whereClause.join(' AND ') : '';
    
    // 查询数据
    const rows = await new Promise((resolve, reject) => {
      db.all(`
        SELECT 
          r.student_id,
          r.student_ip,
          r.url,
          r.title,
          r.timestamp,
          CASE WHEN b.id IS NOT NULL THEN '是' ELSE '否' END AS blacklisted,
          b.reason AS blacklist_reason
        FROM browsing_records r
        LEFT JOIN blacklist b ON r.url LIKE '%' || b.domain || '%'
        ${whereStr}
        ORDER BY r.timestamp DESC`,
        params,
        (err, rows) => {
          if (err) reject(err);
          else resolve(rows);
        }
      );
    });
    
    // 创建Excel工作簿
    const workbook = new ExcelJS.Workbook();
    workbook.creator = '学生监控系统';
    workbook.lastModifiedBy = '学生监控系统';
    workbook.created = new Date();
    workbook.modified = new Date();
    
    // 添加工作表
    const worksheet = workbook.addWorksheet('浏览记录');
    
    // 设置列宽
    worksheet.columns = [
      { header: '学生ID', key: 'student_id', width: 15 },
      { header: '学生IP', key: 'student_ip', width: 15 },
      { header: '访问域名', key: 'url', width: 30 },
      { header: '页面标题', key: 'title', width: 40 },
      { header: '访问时间', key: 'timestamp', width: 25 },
      { header: '是否黑名单', key: 'blacklisted', width: 12 },
      { header: '黑名单原因', key: 'blacklist_reason', width: 20 }
    ];
    
    // 添加数据
    rows.forEach(row => {
      worksheet.addRow({
        student_id: row.student_id,
        student_ip: row.student_ip || '—',
        url: row.url,
        title: row.title || '—',
        timestamp: new Date(row.timestamp).toLocaleString('zh-CN'),
        blacklisted: row.blacklisted,
        blacklist_reason: row.blacklist_reason || ''
      });
    });
    
    // 设置表头样式
    const headerRow = worksheet.getRow(1);
    headerRow.font = { bold: true, color: { argb: 'FFFFFF' } };
    headerRow.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: '4472C4' } };
    headerRow.border = {
      top: { style: 'thin' },
      left: { style: 'thin' },
      bottom: { style: 'thin' },
      right: { style: 'thin' }
    };
    
    // 设置所有单元格的边框
    worksheet.eachRow({ includeEmpty: false }, (row, rowNumber) => {
      if (rowNumber > 1) {
        row.eachCell((cell) => {
          cell.border = {
            top: { style: 'thin' },
            left: { style: 'thin' },
            bottom: { style: 'thin' },
            right: { style: 'thin' }
          };
        });
      }
    });
    
    // 添加统计信息工作表
    const statsSheet = workbook.addWorksheet('统计信息');
    statsSheet.addRow(['学生监控系统 - 数据统计报告']).font = { bold: true, size: 14 };
    statsSheet.addRow(['生成时间:', new Date().toLocaleString('zh-CN')]);
    statsSheet.addRow(['总记录数:', rows.length]);
    statsSheet.addRow(['']);
    
    // 统计学生访问次数
    const studentStats = {};
    rows.forEach(row => {
      if (!studentStats[row.student_id]) {
        studentStats[row.student_id] = 0;
      }
      studentStats[row.student_id]++;
    });
    
    statsSheet.addRow(['学生ID', '访问次数']).font = { bold: true };
    Object.entries(studentStats)
      .sort((a, b) => b[1] - a[1])
      .forEach(([studentId, count]) => {
        statsSheet.addRow([studentId, count]);
      });
    
    // 设置响应头
    res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    res.setHeader('Content-Disposition', `attachment; filename=学生访问记录_${new Date().toISOString().slice(0, 10)}.xlsx`);
    
    // 发送文件
    await workbook.xlsx.write(res);
    res.end();
  } catch (error) {
    console.error('导出Excel失败:', error);
    res.status(500).json({ error: '导出Excel失败: ' + error.message });
  }
});

// 清空所有记录（谨慎使用）
app.delete('/api/records/clear', (req, res) => {
  db.run('DELETE FROM browsing_records', function(err) {
    if (err) return res.status(500).json({ error: '清空记录失败: ' + err.message });
    res.json({ ok: true, message: `已清空 ${this.changes} 条记录`, deleted_count: this.changes });
  });
});

// 错误处理
process.on('uncaughtException', (err) => {
  console.error('🚨 未捕获的异常:', err);
});

process.on('unhandledRejection', (reason, promise) => {
  console.error('🚨 未处理的Promise拒绝:', reason);
});

// 启动服务
const server = app.listen(PORT, '0.0.0.0', () => {
  console.log(`✅ 学生监控系统服务启动成功`);
  console.log(`✅ 服务地址: http://localhost:${PORT}`);
  console.log(`✅ 监控页面: http://localhost:${PORT}/index.html`);
  console.log(`✅ 管理页面: http://localhost:${PORT}/admin.html`);
  console.log(`✅ 注意: 请确保防火墙允许端口 ${PORT} 的访问`);
  console.log(`✅ 服务器正在运行中...`);
});

// 保持服务器运行
server.on('error', (err) => {
  console.error('🚨 服务器错误:', err);
});

// 防止进程过早退出
setInterval(() => {
  console.log(`⏰ 服务器运行状态检查 - ${new Date().toLocaleString()}`);
}, 60000); // 每分钟记录一次服务器状态