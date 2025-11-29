-- 学生监控系统数据库设计

-- 浏览记录表 - 存储学生上网记录
CREATE TABLE IF NOT EXISTS browsing_records (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id TEXT NOT NULL,     -- 学生ID/学号
  student_ip TEXT,              -- 学生机IP地址
  url TEXT NOT NULL,            -- 访问的URL/域名（清理后）
  original_url TEXT,            -- 原始完整URL
  title TEXT,                   -- 网页标题
  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP -- 访问时间戳
);

-- 创建索引提升查询性能
CREATE INDEX IF NOT EXISTS idx_records_student_id ON browsing_records(student_id);
CREATE INDEX IF NOT EXISTS idx_records_timestamp ON browsing_records(timestamp);
CREATE INDEX IF NOT EXISTS idx_records_url ON browsing_records(url);

-- 域名黑名单表 - 用于管控不允许访问的网站
CREATE TABLE IF NOT EXISTS blacklist (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  domain TEXT NOT NULL UNIQUE,  -- 域名（唯一）
  reason TEXT,                  -- 加入黑名单的原因
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP -- 创建时间
);

-- IP黑名单表 - 用于管控不允许访问的IP地址
CREATE TABLE IF NOT EXISTS ip_blacklist (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ip_address TEXT NOT NULL UNIQUE, -- IP地址（唯一）
  reason TEXT,                  -- 加入黑名单的原因
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP -- 创建时间
);

-- 插入初始黑名单数据
INSERT OR IGNORE INTO blacklist (domain, reason) VALUES 
('qq.com', '社交娱乐'),
('youku.com', '视频网站'),
('games.com', '游戏站点'),
('douyu.com', '直播平台');

-- 插入初始IP黑名单数据（示例）
INSERT OR IGNORE INTO ip_blacklist (ip_address, reason) VALUES 
('192.168.1.100', '测试IP黑名单'),
('10.0.0.254', '测试IP黑名单');