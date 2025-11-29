const http = require('http');

const host = 'localhost';
const port = 3003;

function req(options, data=null) {
  return new Promise((resolve, reject) => {
    const r = http.request(options, (res) => {
      let body = '';
      res.on('data', (chunk) => body += chunk);
      res.on('end', () => {
        try {
          const parsed = JSON.parse(body);
          resolve({ status: res.statusCode, body: parsed });
        } catch (e) {
          resolve({ status: res.statusCode, body: body });
        }
      });
    });
    r.on('error', reject);
    if (data) {
      r.write(JSON.stringify(data));
    }
    r.end();
  });
}

async function run() {
  console.log('1) GET /api/stats');
  console.log(await req({ hostname: host, port, path: '/api/stats', method: 'GET', headers: { 'Content-Type': 'application/json' } }));

  console.log('\n2) GET /api/blacklist/domains');
  console.log(await req({ hostname: host, port, path: '/api/blacklist/domains', method: 'GET', headers: { 'Content-Type': 'application/json' } }));

  console.log('\n3) POST /api/blacklist/domains/add (example.com)');
  console.log(await req({ hostname: host, port, path: '/api/blacklist/domains/add', method: 'POST', headers: { 'Content-Type': 'application/json' } }, { domain: 'example.com', reason: '测试' }));

  console.log('\n4) POST /api/report (test student report)');
  console.log(await req({ hostname: host, port, path: '/api/report', method: 'POST', headers: { 'Content-Type': 'application/json' } }, { student_id: 'test-student', student_ip: '192.168.1.100', url: 'http://example.com/test', title: '测试页面' }));

  console.log('\n5) GET /api/records?student_id=test-student');
  console.log(await req({ hostname: host, port, path: '/api/records?student_id=test-student', method: 'GET', headers: { 'Content-Type': 'application/json' } }));

  console.log('\n完成测试。');
}

run().catch(err => {
  console.error('测试脚本出错:', err);
  process.exit(1);
});
