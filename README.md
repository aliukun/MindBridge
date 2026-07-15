# MindBridge Learn

从零实现的校园心理支持智能体项目。

## 当前版本

v0.3.0

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
- unittest 自动测试
- GitHub Actions

## 尚未实现

- 聊天会话与消息持久化
- 心理风险评估
- AI 模型调用
- SSE 流式聊天
- RAG
- 多智能体
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

数据库文件和 `.env` 都属于本地运行数据，不提交到 Git。

## 安全提醒

HTTP Basic 只适合当前本地学习阶段。

如果部署到公网，必须使用 HTTPS。