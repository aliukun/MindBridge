# MindBridge Learn

从零实现的校园心理支持智能体项目。

## 当前版本

v0.5.0

## 当前已完成

- FastAPI 应用工厂
- 集中配置管理
- 健康检查接口
- SQLAlchemy 数据库基础设施
- SQLite 本地持久化
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
- unittest 自动测试
- GitHub Actions

## 尚未实现

- AI 模型调用
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

风险等级、命中信号和报告摘要不会出现在学生消息响应中。

## 测试

```powershell
python -m unittest discover -s tests -v
```

也可以执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check.ps1
```

## 当前数据库

开发环境暂时使用 SQLite：

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