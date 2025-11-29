-- 浏览记录表（新增 screenshot 字段存 base64 缩略图）
CREATE TABLE IF NOT EXISTS browsing_records (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id TEXT NOT NULL,
  url TEXT NOT NULL,
  title TEXT,
  screenshot TEXT,         -- base64 缩略图（可选）
  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 黑名单表（支持动态管理）
CREATE TABLE IF NOT EXISTS blacklist (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  domain TEXT NOT NULL UNIQUE,
  reason TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 初始黑名单（可删改）
INSERT OR IGNORE INTO blacklist (domain, reason) VALUES 
('qq.com', '社交娱乐'),
('youku.com', '视频网站'),
('games.com', '游戏站点'),
('douyu.com', '直播平台');