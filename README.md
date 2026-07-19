# MindBridge Learn

从零实现的校园心理支持智能体项目。

## 当前版本

v0.8.0

## 当前已完成

- FastAPI 应用工厂
- 集中配置管理
- 健康检查接口
- SQLAlchemy 数据库基础设施
- SQLite 本地持久化
- 非空数据库 Schema 兼容性只读检查
- SQLite 每连接强制启用外键约束
- 数据库级 ON DELETE CASCADE
- 受保护的开发数据库重建脚本
- UserAccount 用户实体
- Argon2id 密码哈希
- HTTP Basic 身份认证
- 学生和管理员角色授权
- ChatSession 聊天会话实体
- ChatMessage 聊天消息实体
- 创建聊天会话
- 保存用户消息
- 服务层保存助手消息
- 查询聊天历史
- 会话所有权隔离
- LOW、MEDIUM、HIGH 风险等级
- 确定性关键词风险硬规则
- 高风险优先判断
- Unicode 文本归一化
- 规则版本记录
- MEDIUM/HIGH 后台心理安全报告
- 消息与报告原子事务
- 后台风险标签不向学生接口暴露
- 统一公共错误响应（code、detail、request_id）
- 成功与错误响应的 X-Request-ID 链路标识
- 密码、密钥、Authorization 和数据库凭据日志脱敏
- unittest 自动测试
- Ruff 代码检查和统一格式检查
- mypy 渐进式类型检查
- compileall 语法编译检查
- 分支覆盖率检查，当前最低门槛为 90%
- pip 依赖一致性检查
- 本地与 GitHub Actions 共用同一套质量检查
- GitHub Actions
- 内部 AI 消息、请求、完成结果和流式块契约
- system、user、assistant AI 角色边界
- AI 请求参数范围校验
- 稳定的 AI 异常层级
- 异步 AiProvider Protocol
- 离线确定性 Mock Provider
- 严格 Provider Factory
- 应用组装层中的 Provider 与默认请求选项
- Ollama 非流式与 NDJSON 流式 Provider
- OpenAI-compatible 非流式与 SSE 流式 Provider
- 共享 httpx.AsyncClient 生命周期与三层超时
- 稳定的真实 Provider 网络和协议异常映射
- 本地模型四层 readiness 与管理员状态接口
- Windows 模型检查与显式注册脚本

## 尚未实现

- AI 与硬规则风险结果合并
- 高风险安全回复
- SSE 流式聊天
- RAG
- 多智能体
- 管理员报告查询
- 风险个案
- Excel 台账
- 邮件或日志预警
- 管理后台

## 安装

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

## 本地账户配置

复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

在本地 `.env` 中设置学生和管理员密码。

密码必须至少 12 位，并且 `.env` 不能提交到 Git。

## 运行

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## 接口

公开健康检查：

```text
GET /actuator/health
```

当前用户：

```text
GET /api/users/me
```

管理员权限检查：

```text
GET /api/admin/ping
```

创建聊天会话：

```text
POST /api/chat/sessions
```

保存用户消息并执行后台风险硬规则：

```text
POST /api/chat/sessions/{session_public_id}/messages
```

查询聊天历史：

```text
GET /api/chat/sessions/{session_public_id}/messages
```

当前没有公开的风险评估接口或报告查询接口。

管理员 AI 与本地模型状态：

```text
GET /api/admin/ai/status
GET /api/admin/ai/status?run_inference=true
```

第二种形式会显式执行一次不包含用户数据的最小 Ollama 推理；默认状态请求不会执行推理。

风险等级、命中信号和报告摘要不会出现在学生消息响应中。

## 测试

只运行全部单元测试：

```powershell
python -m unittest discover -s tests -v
```

提交代码前，推荐运行完整质量检查：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check.ps1
```

这个脚本会依次执行：

1. `pip check`，检查已安装依赖之间是否冲突。
2. `ruff check`，查找导入、语法和常见静态问题。
3. `ruff format --check`，确认代码已经按统一格式整理。
4. `mypy`，检查 `app` 目录中的类型使用。
5. `compileall`，确认 Python 文件都能被编译。
6. 在 coverage 中运行全部 unittest。
7. 输出分支覆盖率，并执行 90% 的最低门槛。

任意一步失败，脚本都会立即停止并返回非零退出码。GitHub Actions 在
Python 3.12 环境中调用同一个脚本，避免本地检查与 CI 使用不同标准。

当前 v0.8.0 质量基线：

- 132 个自动化测试全部通过
- 综合分支覆盖率为 92%，高于 90% 门槛
- 61 个 Python 文件通过 Ruff 格式检查
- 38 个应用源文件通过 mypy

## 当前 AI Provider 边界

v0.8.0 支持 `mock`、`ollama` 和 `openai_compatible` 三种显式 Provider。
未知名称会拒绝启动，绝不静默回退 Mock。默认仍是完全离线、确定性的 Mock；
现有聊天 API 仍未调用 Provider，隐私脱敏、风险合并和安全单轮闭环属于 v0.9.0。

应用在 lifespan 中创建一个共享 `httpx.AsyncClient`，所有真实 Provider 只借用
这个客户端；应用退出时统一关闭连接池。HTTPX 的 connect/read/write/pool
分阶段超时与 `asyncio.timeout` 的整次调用总时限分别配置。当前流式总时限包含
消费者处理增量的时间，进入 HTTP SSE 阶段时会再次评估慢客户端与取消传播。

OpenAI-compatible 适配器采用 Chat Completions 形状，因为它是最终版和多种兼容
服务的共同协议。OpenAI 官方当前建议 OpenAI 原生新项目优先考虑 Responses API；
本学习版没有默认远程模型，只有显式配置 base URL、SecretStr API key 和 model
后才能选择这个 Provider。

AI 的 system 消息只属于模型上下文，不会写入当前只允许 user 和 assistant 的
聊天消息表。Provider 状态、内部 prompt 和模型错误也不会通过学生接口外显。

## 本地模型与 Ollama readiness

根目录 `models` 保存 AI 模型资产，和保存 SQLAlchemy 代码的 `app/models` 不是
同一个目录。仓库只提交 `README.md` 与 `Modelfile`；GGUF、safetensors、bin、pt、
pth 和模型压缩包均被忽略。

状态按四层报告，不能把“文件存在”误认为“模型可用”：

1. `asset_status`：GGUF 与 Modelfile 是否同时存在，FROM 是否匹配。
2. `server_status`：Ollama `/api/tags` 是否可达并返回有效数据。
3. `registration_status`：目标模型是否已注册。
4. `inference_status`：只有管理员显式请求时才运行固定最小 prompt。

模型文件尚未迁移时保持 `AI_PROVIDER=mock`。检查与注册脚本不会安装或启动
Ollama，不会下载、复制或提交 GGUF：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check_local_model.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\register_local_model.ps1 -WhatIf
```

迁移 GGUF 后可选择校验已知 SHA-256，再由开发者本人确认注册：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check_local_model.ps1 -VerifyChecksum
powershell -ExecutionPolicy Bypass -File .\scripts\register_local_model.ps1 -VerifyChecksum -Confirm
powershell -ExecutionPolicy Bypass -File .\scripts\check_local_model.ps1 -RunInference
```

## 当前数据库

开发环境使用 SQLite：

```text
data/mindbridge.db
```

当前主要数据表：

```text
user_accounts
chat_sessions
chat_messages
psychological_reports
```

数据库文件和 `.env` 都属于本地运行数据，不提交到 Git。

### 为什么当前数据库可以重建

MindBridge Learn 目前仍是从零学习和复现阶段。`data` 目录中的用户、会话、
消息和报告都被视为可丢弃的本地开发数据，不应存放唯一一份重要资料。

应用通过 SQLAlchemy 的 `Base.metadata.create_all()` 从空数据库创建当前全部
数据表。它适合自动测试和当前本地学习环境，但必须理解它的能力边界：

- 它可以在空数据库中创建表，也可以在结构已经一致时重复执行。
- 它不会把旧表可靠地升级成新的 ORM 结构。
- 它不能代替数据库迁移工具完成新增字段、修改约束、数据转换或回滚。
- 当前项目不支持保留旧 SQLite 数据进行无损跨版本 Schema 升级。
- 如果以后开始保存不可丢弃的真实数据，必须先设计版本化迁移、备份和恢复方案。

应用启动、测试脚本和 CI 都不会自动删除本地数据库。Schema 变化时，需要由
开发者本人确认数据可以丢弃，然后显式执行安全重建。

### 手工安全重建 SQLite

1. 停止正在运行的 FastAPI、测试进程和可能占用数据库的 Python 控制台。
2. 确认数据确实可以丢弃。如果只是临时希望保留一份副本，可以先执行：

```powershell
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
Copy-Item -LiteralPath .\data\mindbridge.db -Destination ".\data\mindbridge-$timestamp.backup.db"
```

备份文件只能用于同一 Schema 下的临时检查；它不代表项目支持跨版本恢复。

3. 先预览受保护的重置操作，不删除文件：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\reset_dev_database.ps1 -WhatIf
```

4. 仔细核对脚本显示的绝对路径，然后由本人确认删除：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\reset_dev_database.ps1 -Confirm
```

重置脚本只允许处理 `development` 环境中、项目 `data` 目录内的文件型 SQLite
`.db` 数据库。它拒绝内存数据库、其他数据库类型和项目目录外的路径；脚本只
删除经过校验的数据库文件，不会启动应用，也不会删除 `.env`、模型或上传文件。

5. 再次启动应用，让 `create_all()` 从空数据库创建最新结构：

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

6. 重新运行完整质量检查。需要的本地初始账户会根据 `.env` 中的配置重新创建。

## 风险模块边界

当前风险模块只使用确定性关键词硬规则。

它的作用是为本地学习项目提供安全分流和后台报告基础。

关键词匹配可能误报，例如教育、新闻、否定表达中包含相同词语；也可能漏掉没有出现在词表中的表达。

因此：

- 命中不等于心理或医学诊断
- LOW 不代表一定不存在风险
- 不应使用结果给学生贴标签
- 不应仅依赖该模块做真实危机决策
- 当前版本不构成危机干预或紧急救助系统
- 当前版本不应作为真实心理服务直接部署

后续接入 AI 时，模型只能提高风险等级，不能降低硬规则已经判定的 HIGH。

## 安全提醒

HTTP Basic 只适合当前本地学习阶段。

如果部署到公网，必须使用 HTTPS。

客户端只能创建用户消息，不能自行指定 assistant 角色。

用户只能查询和修改属于自己的聊天会话。

项目当前不会自动发送邮件、通知老师或联系紧急服务。
