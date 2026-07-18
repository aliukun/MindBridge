# MindBridge Learn 开发计划

## 开发原则

- 每个阶段只实现一个明确的基础能力。
- 每个功能必须配套自动化测试。
- 所有测试通过后才能进入下一阶段。
- `.env`、数据库文件、虚拟环境和密钥不能提交。
- 每个标志性版本在 GitHub 保留独立提交和标签。

## v0.1.0：Web 应用基础

状态：已完成

- FastAPI 应用工厂
- 集中配置管理
- 健康检查接口
- unittest 自动测试
- GitHub Actions

## v0.2.0：数据库持久化基础

状态：已完成

- 加入 SQLAlchemy
- 使用 SQLite 作为零配置开发数据库
- 建立 Engine、Session 和 Base
- 建立 UserAccount ORM 实体
- 应用启动时自动创建数据库表
- 使用内存 SQLite 测试建表和数据读写

完成标准：

- 全部 unittest 通过
- 应用能够正常启动
- data/mindbridge.db 能够生成
- user_accounts 表能够创建
- 数据库文件不会进入 Git

## v0.3.0：身份认证和角色

状态：已完成

- 安全密码哈希
- 用户初始化
- HTTP Basic 身份认证
- 学生和管理员角色
- 401 与 403 测试

## v0.4.0：聊天数据基础

状态：已完成

- ChatSession 实体
- ChatMessage 实体
- 创建会话
- 保存用户消息和助手消息
- 查询历史消息

## v0.5.0：心理风险评估

状态：已完成

- 风险等级枚举
- 关键词硬规则
- 心理评估结果
- 后台报告
- 高风险测试

## v0.6.0：AI Provider

- Mock Provider
- Ollama Provider
- OpenAI-compatible Provider
- Provider 配置切换
- 无真实模型时的测试替身

## v0.7.0：SSE 流式聊天

- 流式响应协议
- 聊天状态事件
- 异常事件
- 断开连接处理

## v0.8.0：RAG

- 校园心理知识库
- 文档切块
- 关键词检索
- 向量检索
- 混合排序
- RAG 评测

## v0.9.0：记忆和多智能体

- Redis 短期记忆
- Supervisor
- Knowledge Agent
- Risk Guardian
- Companion Agent
- Counselor Agent
- 有限循环保护

## v0.10.0：管理和预警

- 管理员报告接口
- 风险个案
- Excel 台账
- 邮件或日志预警
- 工具任务队列

## v1.0.0：完整交付

- 学生端页面
- 管理端页面
- Docker
- 完整回归测试
- 安全检查
- 部署文档