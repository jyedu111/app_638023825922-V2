## 测试说明（tests）

此目录包含对后端服务的简单测试脚本：

- `tests/test_api.js` — 使用 Node.js 的原生 `http` 发起一组 API 请求（stats、黑名单增删、上报、查询）。
- `tests/test_report.py` — 用 Python 向后端发送上报数据的演示脚本（支持命令行参数）。

先决条件
- 已安装 Node.js（建议 v16+）和 npm
- 已安装 Python（建议 3.8+）以及 `pip`
- 后端服务正在运行（默认 `http://localhost:3003`）。如果未启动，请在项目根目录运行：

```powershell
Set-Location -LiteralPath 'e:\VSCODE\NEW-student-monitor'
node server.js
```

运行前准备
- 安装 Node 依赖（若尚未安装）：

```powershell
npm.cmd install
```

- 安装 Python 依赖（若尚未安装）：

```powershell
python -m pip install -r requirements.txt
```

如何运行测试

- 仅运行 JS 脚本：

```powershell
Set-Location -LiteralPath 'e:\VSCODE\NEW-student-monitor'
node tests/test_api.js
```

- 仅运行 Python 脚本（示例）：

```powershell
Set-Location -LiteralPath 'e:\VSCODE\NEW-student-monitor'
python tests/test_report.py --server http://localhost:3003 --student-id demo_pc --count 2 --interval 1 --timestamp
```

- 使用 npm 脚本（更方便）：

```powershell
Set-Location -LiteralPath 'e:\VSCODE\NEW-student-monitor'
npm.cmd run test:js   # 运行 JS 测试
npm.cmd run test:py   # 运行 Python 测试
npm.cmd run test:all  # 先运行 JS，再运行 Python
```

注意事项
- 如果 PowerShell 报错提示 `npm.ps1 被禁止运行`，请改用 `npm.cmd`（上面的命令已使用 `npm.cmd` 以兼容 PowerShell 策略）。
- Python 脚本默认上报到 `http://localhost:3003`，可以用 `--server` 指定其它地址。
- 这些测试是演示/集成级别的快速验证，不是完整的单元测试套件。如需 CI 集成或更完整的测试，我可以帮助把它们迁移到 `jest`/`pytest`。

如果你希望，我可以：
- 把这些命令加入项目根 `README.md`；
- 或将测试迁移为 `jest`/`pytest` 风格并添加到 CI。 
