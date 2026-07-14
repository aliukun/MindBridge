# MindBridge Learn

从零实现的校园心理支持智能体项目。

## 当前版本

v0.2.0

## 当前已完成

- FastAPI 应用工厂
- 集中配置管理
- 健康检查接口
- SQLAlchemy 数据库基础设施
- SQLite 本地持久化
- UserAccount 用户实体
- unittest 自动测试
- GitHub Actions

## 尚未实现

- 用户认证与角色授权
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

## 运行

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
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

数据库文件属于运行时数据，不提交到 Git。