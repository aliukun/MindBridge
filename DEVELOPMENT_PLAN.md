# MindBridge Learn 开发计划

> 本文档于 2026-07-18 基于 MindBridge Learn v0.5.0 的真实代码、测试结果和最终版 MindBridge 的实现重新审阅后制定，并根据开发者对开发期数据库数据可丢弃的决定再次调整。
>
> 目标不是逐文件照抄最终版，而是保留学习版已有的更好设计，吸收最终版中真正重要的技术链路，并把每个大问题拆成适合初学者编码、测试和提交 GitHub 的小阶段。
>
> v0.7.0 的代码、测试、离线 Mock 手工验收和文档同步已于 2026-07-19 完成。当前共有 96 个测试，综合分支覆盖率为 93%；本阶段没有复制模型、安装 Ollama、接入聊天路由或改变数据库 Schema，Codex 也没有执行暂存、提交、打标签或推送。

## 一、如何使用这份计划

1. 严格按版本顺序推进；当前阶段没有达到验收标准时，不进入下一阶段。
2. 每个阶段都先写最小数据契约和测试，再写实现，最后接 API 或界面。
3. 自动化测试默认使用 SQLite、Mock Provider、Fake Redis、Fake Embedding 和 Fake Tool，不依赖真实模型或外部服务。
4. Ollama、OpenAI-compatible、Redis、MySQL、Chroma、SMTP 和 MCP 都必须有明确的不可用处理，不能让外部依赖故障破坏基础聊天和高风险硬规则。
5. 学生接口只返回学生真正需要看到的内容；风险等级、命中信号、内部 prompt、trace、工具任务和模型状态均不得意外外显。
6. 每个阶段验收通过后，再由开发者本人在本地检查、commit、tag 和 push。Codex 只提醒时机，不代为推送。
7. 路线中的版本号代表学习里程碑，不要求与最终版的版本号一致。
8. 当前学习和开发阶段把本地 SQLite 数据视为可丢弃数据；ORM 实体是 Schema 的唯一事实来源，结构变化后通过删除开发数据库并执行 create_all 从零重建。
9. 本路线不引入 Alembic，也不承诺保留已有数据库数据完成跨版本 Schema 升级。若未来开始保存不可丢弃的真实数据，必须暂停结构修改并单独重新评估版本化数据库迁移方案。

状态约定：

- 已完成：代码、测试和文档均已核验。
- 待开发：尚未开始，不应提前加入依赖。
- 可选增强：不属于最小可交付链路，但值得作为进阶学习。
- 阻塞：前置阶段未通过，不能开始。

## 二、v0.5.0 当前真实基线

审阅时的仓库状态：

- 项目目录：C:\Users\刘坤\Desktop\MindBridge-Learn
- 当前分支：main
- 当前提交：da1531c
- 当前标签：v0.5.0
- 与 origin/main 一致
- 工作区干净
- 项目虚拟环境依赖完整
- 自动化测试：50 个，全部通过

当前已完成：

| 版本 | 能力 | 状态 |
| --- | --- | --- |
| v0.1.0 | FastAPI 应用工厂、集中配置、健康检查、测试和 CI | 已完成 |
| v0.2.0 | SQLAlchemy、SQLite、数据库 Session、用户实体和建表 | 已完成 |
| v0.3.0 | Argon2id、HTTP Basic、学生与管理员角色、401/403 | 已完成 |
| v0.4.0 | 会话、消息、公开 UUID、所有权隔离和聊天历史 | 已完成 |
| v0.5.0 | 确定性风险硬规则、后台报告、事务和隐私边界 | 已完成 |

当前尚未安装或实现：

- AI Provider 和模型调用
- Ollama、本地 GGUF 模型和 OpenAI-compatible API
- AI 意图识别、AI 风险建议和安全回复
- SSE 流式聊天
- 学生端和管理端页面
- 知识库、RAG、Embedding 和 Chroma
- Redis 记忆和记忆压缩
- Skills、Agent runtime、LangGraph 和事件驱动协作
- 风险个案、工具队列、Excel、预警、MCP
- MySQL、Docker Compose 和发布打包

这说明 v0.5.0 的边界是清楚的；后续不应为了“看起来像最终版”而一次加入全部依赖。

## 三、必须保留的学习版优势

以下设计比最终版更安全或更清晰，后续不得为了复刻而退回。

### 1. 身份认证和密码

- 继续使用带盐 Argon2id，不改成普通 SHA-256。
- 继续要求至少 12 位密码。
- 密码来自本地 .env，不在代码中写死演示密码。
- 配置中的密码和 API key 继续使用 SecretStr。
- 未知用户名继续验证 dummy hash，降低基于响应时间枚举账户的风险。

### 2. 数据最小化

- PsychologicalReport 继续通过 message_id 关联原消息，不重复保存用户、会话和完整消息正文。
- 不保存具体命中的敏感关键词，只保存信号类别。
- 没有真实校准数据时，不把模型自报分数包装成可信的统计置信度。
- 不新增学生可访问的后台报告接口。

### 3. 权限和公开标识

- 内部整数主键与公开 UUID 继续分离。
- 所有用户资源都使用“资源公开 ID + 当前用户 ID”同时查询。
- 他人资源和不存在资源继续统一返回 404，避免泄露资源是否存在。
- 输入和输出继续使用独立 Pydantic Schema，并保留 extra="forbid"。

### 4. 事务边界

- 低层服务只 add 和 flush，不随意 commit。
- 当前用户消息与硬规则报告继续是一个原子业务单元。
- commit 和 rollback 由上层用例服务或路由统一控制。
- 后续等待几十秒的模型网络调用时，不长时间占用数据库事务。

### 5. 风险安全边界

- 高风险确定性硬规则永远先执行。
- NFKC、大小写和空白归一化继续保留。
- 模型只能提高最终风险，不能降低硬规则已经判定的等级。
- HIGH 场景即使模型、Redis、RAG 或工具全部离线，也必须能返回预先审核的安全指引。
- 风险结果只用于支持强度和人工分流，不宣称诊断。

### 6. 应用和测试

- 继续使用 FastAPI lifespan，不退回已逐步弃用的 startup/shutdown 装饰器。
- 内存 SQLite 继续使用 StaticPool，保证 TestClient 跨线程测试稳定。
- 每个阶段继续使用独立临时数据库和确定性测试替身。

## 四、最终版中值得吸收、但原计划遗漏的能力

原计划只有 AI Provider、SSE、RAG、记忆与多智能体、管理预警、完整交付六个大标题，跨度过大。对照最终版后，至少需要显式补齐下列能力。

| 能力 | 原计划问题 | 新规划位置 |
| --- | --- | --- |
| 开发期 Schema 重建策略 | 未明确可丢弃 SQLite 的安全重建流程和约束验收 | v0.6.0 |
| AI 请求/响应契约和统一异常 | 只列 Provider 名称 | v0.7.0 |
| 确定性 Mock 和依赖注入 | 未说明如何在没有模型时测试 | v0.7.0 |
| GGUF、Modelfile、Ollama 注册和状态 | 完全遗漏模型资产生命周期 | v0.8.0 |
| 隐私脱敏和 prompt 版本 | 未定义进入模型的数据边界 | v0.9.0 |
| AI 结构化解析、风险合并和高风险降级 | README 承诺但计划未覆盖 | v0.9.0 |
| 非流式完整闭环 | Provider 后直接跳到 SSE | v0.9.0 |
| 流式失败、取消和持久化状态 | 只写“异常事件” | v0.10.0 |
| 尽早验证学生端交互 | 原计划拖到 v1.0 | v0.11.0 |
| 知识文档摄取和生命周期 | RAG 只写检索算法 | v0.12.0 |
| 离线 BM25、动态路由和本地降级 | 未拆出可离线基线 | v0.13.0 |
| 向量库重建、快照和 RAG 评测 | 未覆盖运维和质量判断 | v0.14.0 |
| Redis 失败回退、TTL、压缩和上下文预算 | 与多 Agent 混在一个阶段 | v0.15.0 |
| 标准 Skills 的加载、校验和选择 | 完全遗漏 | v0.16.0 |
| 单轮 runtime harness 和 trace | 完全遗漏 | v0.17.0 |
| 有界自研多 Agent | 与 Redis 一次实现，过大 | v0.18.0 |
| LangGraph 行为等价和框架回退 | 完全遗漏 | v0.19.0 |
| 事件驱动任务板、黑板和安全审查 | 完全遗漏 | v0.20.0 |
| 风险个案生命周期 | 原计划只写“风险个案” | v0.21.0 |
| 工具授权、幂等、重试、限流和死信 | 原计划只写“工具队列” | v0.22.0 |
| MCP 工具边界 | 完全遗漏 | v0.23.0 |
| 管理端运维视图 | 原计划只写“管理后台” | v0.24.0 |
| MySQL 空库兼容、Redis、容器初始化和模型外置 | 全部挤到 v1.0 | v0.25.0 |
| 工程 harness、隐私审计和故障注入 | 完全遗漏 | v1.0.0 |

## 五、最终版不能原样照抄的地方

最终版用于识别技术链路，不是逐行质量标准。审阅时发现以下实现不应复制：

1. 最终版密码使用普通 SHA-256，且启动数据中写死短密码；学习版继续使用 Argon2id 和 SecretStr。
2. 最终版未知 AI_PROVIDER 会静默进入 Mock；学习版必须把拼写错误视为配置错误，Mock 只能被显式选择。
3. 最终版模型状态只检查 GGUF 和 Modelfile，不检查 Ollama 服务、模型注册和最小推理；学习版必须分层检查。
4. 最终版多个服务内部直接 commit，难以保证一次业务操作的原子性；学习版继续由用例层控制事务。
5. 最终版 ToolGovernanceService 虽被定义和导入，但队列执行链并未真正调用；学习版必须写集成测试证明策略在执行前生效。
6. 最终版 ReportService 存在方法缩进和挂载问题，说明仅有模块文件并不等于功能真的可用；学习版必须用 API 测试覆盖公开行为。
7. 最终版 Dockerfile 没有复制 skills 目录，容器中的 Skill 加载可能与本地不一致；学习版发布检查必须核对运行资产清单。
8. 最终版报告重复保存完整消息、用户和会话信息，并使用未经校准的分数；学习版继续坚持数据最小化。
9. 最终版没有明确说明 create_all 只会创建缺失表；学习版开发阶段可以继续使用 create_all，但必须明确采用“可丢弃数据库 + 安全重建”策略，不能把它描述成已有数据库的无损升级机制。
10. 最终版 Bash 脚本偏向 macOS/Linux；学习版开发环境是 Windows，优先提供 PowerShell 操作流程。

## 六、目标目录和职责边界

后续建议逐步演进为下面的结构。目录只在对应阶段创建，不要一次建空壳。

    MindBridge-Learn/
    ├── app/
    │   ├── ai/
    │   │   ├── contracts.py
    │   │   ├── errors.py
    │   │   ├── factory.py
    │   │   ├── prompts.py
    │   │   ├── parsing.py
    │   │   └── providers/
    │   │       ├── mock.py
    │   │       ├── ollama.py
    │   │       └── openai_compatible.py
    │   ├── agents/
    │   │   ├── contracts.py
    │   │   ├── runtime.py
    │   │   ├── langgraph_runtime.py
    │   │   └── event_driven/
    │   ├── api/
    │   ├── core/
    │   ├── harness/
    │   ├── knowledge/
    │   ├── mcp_tools/
    │   ├── models/
    │   ├── rag_eval/
    │   ├── schemas/
    │   ├── services/
    │   └── static/
    ├── models/
    │   └── mindbridge-qwen2.5-7b-ft/
    │       ├── README.md
    │       └── Modelfile
    ├── skills/
    ├── scripts/
    │   ├── check.ps1
    │   └── reset_dev_database.ps1
    └── tests/

必须区分两个 models：

- app/models：SQLAlchemy ORM Python 代码。
- 根目录 models：本地 AI 模型资产。

最终的单轮主链路应当是：

    HTTP / SSE
        ↓
    Turn Harness
        ↓
    所有权校验 → 原始消息落库 + 硬规则报告
        ↓
    脱敏模型输入
        ↓
    意图路由 → 记忆 → RAG → Skills → 风险合并
        ↓
    Provider / Agent Runtime
        ↓
    安全审查 → 学生回复
        ↓
    助手消息、trace 和事务型 outbox
        ↓
    工具队列 → 个案 / Excel / log 或 SMTP / MCP

## 七、详细后续路线

### v0.6.0：可重建开发数据库与工程护栏

状态：已完成

实际完成内容：

- 原有功能与新增功能合计 71 个自动化测试全部通过。
- 新增只读 Schema 契约检查：空数据库允许由 ORM 创建；非空数据库只有结构与 ORM 完全兼容时才继续启动。
- 不兼容数据库会抛出稳定的 IncompatibleDatabaseSchemaError；检查过程不会补表、改表、删库或改变原数据库文件。
- 每个 SQLite 连接都会执行 PRAGMA foreign_keys=ON，三个外键都使用数据库级 ON DELETE CASCADE，并由原始 SQL 删除测试证明级联真实生效。
- 新增受保护的 scripts/reset_dev_database.ps1，支持 -WhatIf 和显式确认，并拒绝 production、非 SQLite、非 .db 以及项目 data 目录外的路径。
- 已清理未采用的 Alembic 配置、迁移草稿、开发依赖和虚拟环境安装，继续采用 ORM + create_all 的可重建开发数据库路线。
- 新增统一应用错误、请求 ID 中间件和异常处理器；成功与错误响应都带 X-Request-ID，422 与 500 不回显敏感内部信息。
- 新增安全日志基础，对密码、API Key、Authorization、SecretStr、数据库 URL 密码和异常消息正文进行屏蔽；SQLAlchemy 关闭 echo 并隐藏绑定参数。
- requirements-dev.txt 已锁定 coverage、httpx、mypy 和 Ruff 的精确版本。
- scripts/check.ps1 已统一执行 pip check、Ruff lint、Ruff format check、mypy、compileall、coverage unittest 和 coverage report，任一步失败立即停止。
- GitHub Actions 固定使用 Python 3.12，并通过 pwsh 复用本地 check.ps1。
- README、.env.example、集中配置和本地 .env 的版本号已更新到 v0.6.0。
- 最终完整质量链通过：71 个测试全部通过，综合分支覆盖率为 92%，高于 90% 门槛。

本次路线调整：

- 本地 data 目录中的 SQLite 只承载学习和开发数据，允许在 Schema 变化时删除并重建。
- Base.metadata 和 app/models 中的 ORM 实体继续作为数据库结构的唯一事实来源。
- 正常开发和测试继续使用 create_schema / Base.metadata.create_all 创建空数据库，不引入 Alembic。
- create_all 的重复执行只代表“已有结构一致时不会重复建表”，不代表它能修改已有表。
- 如果未来数据库开始保存不可丢弃的真实数据，必须先重新制定版本化迁移方案，再继续修改实体结构。
- Alembic 草稿文件、配置和依赖已经清理；后续阶段不再按迁移框架路线继续开发。

验收前提（已满足）：

- v0.5.0 的 50 个测试全部通过。
- 明确接受开发数据库中的用户、会话、消息和报告在重建时被删除。
- 删除文件前必须停止正在运行的 FastAPI 进程，避免数据库仍在写入。

阶段目标：

- 建立明确、可重复且受保护的开发 SQLite 重建流程。
- 保证每次 ORM 实体变化后，都能从空数据库生成完整表、索引和约束。
- 启用 SQLite 外键检查，并用数据库级 CASCADE 保证用户、会话、消息和报告之间的一致性。
- 建立稳定的公共错误响应和不会泄露秘密的日志基础。
- 让本地检查与 GitHub Actions 执行相同的质量门槛。

为什么先做：

- 后续会新增知识文档、trace、风险个案和工具任务等实体，必须先统一“修改 ORM 后如何重建数据库”的开发流程。
- 即使开发数据可以删除，外键、唯一索引和 CheckConstraint 仍必须在真实 SQLite 中生效，不能只停留在 Python 对象关系上。
- 把数据库数据定义为可丢弃可以降低当前学习成本，但必须同时写清适用边界，避免将来误认为系统支持生产数据无损升级。

实际完成顺序：

1. 清理未采用的 Alembic 初始化草稿、配置、开发依赖和当前虚拟环境中的 Alembic 安装。
2. 保留现有 create_schema 和 bootstrap_database，但把启动初始化分成两条明确路径：
   - 数据库完全为空时，允许 Base.metadata.create_all 创建当前完整结构并初始化配置中启用的账户。
   - 数据库已经有业务表时，先执行只读 Schema 兼容性检查；结构与当前 ORM 不一致就抛出稳定错误并提示手工重建，不允许 create_all 偷偷补一部分表后继续运行。
   - 启动代码和兼容性检查都绝不能自动删除数据库文件。
3. 在 app/core/database.py 为每一个 SQLite 新连接执行 PRAGMA foreign_keys=ON；不能只在某一个临时连接中执行一次。
4. 在三个 ORM 外键中加入 ondelete="CASCADE"：
   - chat_sessions.user_id → user_accounts.id
   - chat_messages.session_id → chat_sessions.id
   - psychological_reports.message_id → chat_messages.id
5. 在对应的父端 relationship 中加入 passive_deletes=True，同时保留现有 delete-orphan 关系语义。
6. 扩展数据库测试，检查四张表、六个索引、两个 CheckConstraint 和三个 CASCADE 外键真实存在。
7. 新增非法外键写入测试，证明 SQLite foreign_keys 已真正开启。
8. 新增原始 SQL DELETE 测试；直接删除用户后，会话、消息和报告必须由数据库而不是 ORM 自动级联删除。
9. 创建 scripts/reset_dev_database.ps1，提供受保护的开发数据库重建入口：
   - 只允许 environment=development。
   - 只允许 SQLite 文件数据库。
   - 只允许删除解析后位于项目 data 目录内的 .db 文件。
   - 删除前显示绝对路径并要求明确确认。
   - 脚本不自动备份；如临时需要保留副本，先按 README 在 data 目录中手工复制。
   - 不得删除 .env、上传文件、模型文件或 data 目录外的任何路径。
   - 不得由 FastAPI 启动流程、scripts/check.ps1 或 CI 自动调用，只能由开发者明确手工执行。
10. 使用独立临时数据库测试“文件不存在 → 建表 → 初始化用户 → 再次执行不重复建表”的完整流程。
11. 新建 app/core/errors.py，定义稳定的应用错误和公共错误响应，不把堆栈返回客户端。
12. 新建 app/core/logging.py，统一日志格式；禁止记录密码、Authorization、API key、SecretStr 原值、数据库 URL 密码和完整 prompt；SQLAlchemy 保持 echo 关闭并隐藏绑定参数。
13. 将 scripts/check.ps1 扩展为 pip check、Ruff lint、Ruff format check、mypy、compileall、coverage unittest 和 coverage report，并确保任一步失败立即退出。
14. 修改 .github/workflows/test.yml，在 Python 3.12 下安装 requirements-dev.txt 并通过 pwsh 复用本地 check.ps1。
15. 保持 coverage fail-under=90；以后只在真实覆盖率提高后上调，不为通过 CI 随意降低。
16. 更新 README、.env.example、应用版本号和本规划状态。

每次 ORM Schema 变化时的统一开发流程：

1. 先修改 ORM 实体和相应测试。
2. 停止 FastAPI、测试进程以及可能占用数据库的控制台。
3. 确认当前数据库数据允许丢弃；如临时需要保留，手工创建本地备份。
4. 通过受保护脚本删除开发 SQLite 文件，不手工拼接任意删除路径。
5. 启动应用或运行明确的初始化入口，让 create_all 从空数据库创建最新结构。
6. 检查表、索引、约束、初始用户和 foreign_keys。
7. 运行当前模块测试、完整测试和 scripts/check.ps1。

重点测试：

- 空临时 SQLite 文件可由 create_all 从零生成当前全部结构。
- 对结构一致的数据库第二次执行 create_all 不报错、不重复建表。
- build_engine 创建的每一个 SQLite 新连接都显示 PRAGMA foreign_keys=1。
- 写入不存在的 user_id 或 session_id 时抛出 IntegrityError。
- 使用原始 SQL 删除用户后，会话、消息和报告由数据库级 CASCADE 删除。
- Schema 契约测试能发现缺少的表、索引、CheckConstraint 或外键动作。
- 非空但结构过期的开发数据库会安全拒绝启动，且不会被自动改表或删除。
- 重建脚本拒绝非 development 环境、非 SQLite URL 和 data 目录外路径。
- 应用启动、质量检查和 CI 都不会自动触发删除数据库的重建脚本。
- 日志脱敏测试不出现密码、Authorization、API key 和 SecretStr 原值。
- 原有测试与新增测试合计 71 个，全部通过。

手工验收：

- 旧 v0.5 开发数据库被 Schema 防护安全拒绝，检查前后文件 SHA-256 一致。
- -WhatIf 只显示目标绝对路径，不删除或改变数据库；production 和 data 目录外路径均被拒绝。
- 在开发者明确允许丢弃数据后，旧开发数据库已通过受保护脚本删除，并由 v0.6 ORM 从空库重建。
- 新数据库包含 4 张表、3 个 CASCADE 外键，PRAGMA foreign_keys=1，并按 .env 重新创建 2 个初始账户。
- 重建后 schema_differences 为空，会话、消息和报告从 0 开始。
- 健康检查返回 200、版本 v0.6.0，并正确回传请求 ID。
- scripts/check.ps1 完整通过：71 个测试、92% 覆盖率，Ruff、mypy、compileall 和依赖检查全部通过。

明确能力边界：

- 当前方案支持空数据库首次创建和可丢弃开发数据库重建。
- 当前方案不支持给已有表自动增加字段或修改约束。
- 当前方案不支持保留已有 SQLite 或 MySQL 数据进行跨版本 Schema 升级。
- 如果未来进入真实长期运行、多人共享数据或生产部署，版本化数据库迁移将成为必须重新评估的独立阶段。

本阶段不做：

- 不引入 Alembic 或其他数据库迁移框架。
- 不切换 MySQL。
- 不安装 AI、Redis、Chroma 或 MCP。
- 不修改风险判定行为。

Git 里程碑：

- 建议 commit：chore(engineering): add safe schema reset and quality gates
- 建议 tag：v0.6.0
- 本轮按开发者要求未执行暂存、提交、打标签或推送；以上仅保留为以后本地操作提醒。

### v0.7.0：AI 调用契约与确定性 Mock

状态：已完成

实际完成内容：

- 通用 AI 配置、请求参数边界和应用版本已更新到 v0.7.0。
- AI 内部契约固定放在 app/ai/contracts.py，不复用 HTTP DTO 或 ORM 实体。
- 在原规划基础上补充 AiRequest，集中校验 1 至 64 条消息和不可变请求选项。
- 已定义 AiRole、AiFinishReason、ProviderState、AiMessage、AiRequestOptions、AiRequest、AiCompletion、AiStreamChunk 和 ProviderStatus。
- 契约模型统一禁止额外字段并设为不可变；消息保留有意义的原始排版，但拒绝纯空白内容。
- 已建立 AiError、AiConfigurationError、AiProviderError 及超时、认证、模型不存在、限流、不可用和协议错误层级。
- 已建立结构化 AiProvider Protocol；complete 和 status 为异步调用，stream 返回可直接 async for 的 AsyncIterator。
- 已实现 DeterministicMockProvider，不读取网络、时间、随机数、UUID、数据库或全局配置。
- Mock 使用稳定 JSON 和 SHA-256 生成跨实例确定结果，不回显完整用户输入。
- Mock 流式输出使用固定切片，所有 delta 可完整重组 completion，最后只产生一个带 finish reason 的终止块。
- Provider Factory 对名称执行 strip 和 casefold；未知或空名称抛 AiConfigurationError，不静默回退 Mock。
- create_app 作为 composition root 构造 Provider 和不可变默认请求选项，并保存到 application.state。
- 当前聊天 API 未读取或调用 Provider；以后由 FastAPI dependency 取出，再通过构造参数注入业务服务，避免 Service Locator。
- AI_PROVIDER、AI_TEMPERATURE 和 AI_MAX_TOKENS 已提前到本阶段；非法数值在 Settings 创建时失败，未知 Provider 在应用组装时失败。
- 没有新增运行时依赖，也没有引入 Ollama、模型文件、API key 或真实网络客户端。

自动化验收：

- 原有 71 个测试与新增测试合计 96 个，全部通过。
- contracts.py、errors.py、factory.py 和 Provider Protocol 达到 100% 覆盖率，Mock Provider 达到 98%。
- 项目综合分支覆盖率为 93%，高于 90% 门槛。
- pip check、Ruff lint、Ruff format check、mypy 和 compileall 全部通过。
- Ruff 确认 50 个文件格式正确，mypy 确认 32 个应用源文件无问题。
- 自动测试证明 Mock complete、stream 和 status 不调用 socket.create_connection。
- 相同请求跨实例结果一致，不同请求产生不同指纹。
- 非法角色、空白消息、额外字段、空消息集合、超过 64 条消息、非法 temperature、NaN 和超大 max_tokens 均被拒绝。
- 未知 Provider 在工厂和 create_app 组装路径中均被拒绝。
- 原有健康检查、认证、聊天、事务、风险规则、报告和 Schema 防护测试全部无回归。

手工验收：

- 在独立 Python 进程中通过工厂创建 Mock Provider，status 返回 READY。
- 对同一请求执行两次 complete，结果相等。
- stream 的全部 delta 可重新拼成 complete 文本，并且终止块数量为 1。
- 本阶段没有改变 ORM 或数据库 Schema，因此没有删除或重建开发 SQLite。

本阶段不做：

- 不调用真实 Ollama。
- 不复制模型文件。
- 不接聊天路由。
- 不做 SSE。
- 不添加 Embedding 配置。

Git 里程碑：

- 建议 commit：feat(ai): add provider contracts and deterministic mock
- 建议 tag：v0.7.0
- Codex 未执行暂存、提交、打标签或推送；由开发者在本地完成最终 Git 操作。

### v0.8.0：真实 Provider 与本地微调模型资产

状态：待开发

前置条件：

- v0.7.0 的 Provider 契约稳定。

阶段目标：

- 参考最终版 models 目录，完成 Ollama 托管 GGUF 的调用链。
- 支持 OpenAI-compatible 聊天接口。
- 模型文件可以以后再由开发者自行迁移，缺失时不影响 Mock 模式。

关键原理：

    GGUF + Modelfile
        ↓ 手工执行 ollama create
    模型注册到 Ollama
        ↓ HTTP /api/chat
    Python Provider 调用 Ollama

Python 不直接 import 或加载 4.68 GB GGUF。

编码顺序：

1. 将 httpx 加入运行时 requirements.txt。
2. 复用 v0.7.0 已完成的通用配置和契约：
   - ai_provider
   - ai_temperature
   - ai_max_tokens
   - AiRequest、AiCompletion、AiStreamChunk 和 ProviderStatus
3. 新增真实网络 Provider 专属配置：
   - ai_timeout_seconds
   - ollama_base_url
   - ollama_model
   - openai_compatible_base_url
   - openai_compatible_api_key，使用 SecretStr
   - openai_compatible_model
4. 创建根目录 models/mindbridge-qwen2.5-7b-ft/README.md。
5. 创建或迁移与模型匹配的 Modelfile；提交 Modelfile，不提交 GGUF。
6. 确认 .gitignore 继续忽略 gguf、safetensors、bin 和模型压缩包。
7. 实现 app/services/model_assets.py，但把状态拆成四层：
   - assetStatus：权重和 Modelfile 是否存在
   - serverStatus：Ollama /api/tags 是否可达
   - registrationStatus：指定模型名是否已注册
   - inferenceStatus：可选的最小推理是否成功
8. 检查 Modelfile 的 FROM 文件名是否与配置一致。
9. 实现 Ollama Provider：
   - 非流式 /api/chat
   - 流式 NDJSON 解析
   - 连接、读取和总超时
   - 404 模型不存在、非 2xx、坏 JSON 的异常映射
10. 实现 OpenAI-compatible Provider：
   - /chat/completions
   - 非流式响应
   - data: 流式事件解析
   - 401、404、429、超时和错误 JSON 映射
11. 将 AsyncClient 作为可注入依赖，测试时使用 httpx.MockTransport；真实客户端的创建和关闭进入 lifespan，不在 Provider 方法中反复创建。
12. 新增管理员模型状态接口；不向学生暴露绝对磁盘路径和密钥。
13. 新增 scripts/check_local_model.ps1，只做检查。
14. 新增 scripts/register_local_model.ps1，显式调用 ollama create。
15. 脚本不得自动安装 Ollama、自动下载模型或在应用启动时自动注册模型。

用户以后迁移模型时的边界：

- 可以把最终版根目录 models/mindbridge-qwen2.5-7b-ft 复制到学习版根目录 models。
- 复制后先用 git status --ignored 确认 GGUF 被忽略。
- 手工执行 PowerShell 注册脚本。
- 再检查 ollama list、/api/tags 和最小推理。
- 只有确认 READY 后，才把 AI_PROVIDER 从 mock 改为 ollama。

重点测试：

- 没有模型目录时返回 MISSING，Mock 模式仍可启动。
- 只有 GGUF 时不能错误显示 READY。
- Ollama 可达但模型未注册时返回 UNREGISTERED。
- MockTransport 验证 Ollama 请求体、模型名和 options。
- 正确解析多行 NDJSON。
- 正确解析 OpenAI-compatible data 事件和 DONE。
- 401、404、429、超时、断流和坏 JSON 映射到正确异常。
- API key 不出现在 repr、日志和状态接口中。

手工验收：

- 未迁移模型时，管理员状态接口准确报告缺失。
- 如本机已有可用 Ollama 小模型，可用它做一次可选联调；自动测试仍不得依赖它。

本阶段不做：

- 不让应用自动启动 Ollama。
- 不把 GGUF 放入 Git、Docker 镜像或发布包。
- 不接心理评估和聊天业务。
- 不实现 Embedding Provider。

Git 里程碑：

- 建议 commit：feat(ai): add real providers and local model readiness
- 建议 tag：v0.8.0

### v0.9.0：隐私边界、AI 风险合并与非流式单轮闭环

状态：待开发

前置条件：

- v0.8.0 的 Mock、Ollama 和 OpenAI-compatible 契约一致。

阶段目标：

- 先完成可调试的非流式完整聊天，再进入 SSE。
- 保证模型不能降低硬规则风险，模型不可用也不会丢失高风险安全响应。

编码顺序：

1. 新建 app/services/privacy_service.py：
   - 手机号
   - 邮箱
   - 身份证号
   - 可扩展的校园学号
   - 使用固定占位符，不在日志保留原值
2. 明确数据边界：
   - 原始消息只写业务数据库
   - 风险硬规则在原始消息上执行
   - 发送给模型、Redis、trace 的是脱敏副本
3. 新建 app/ai/prompts.py：
   - 意图分类 prompt
   - 心理风险建议 prompt
   - 普通聊天 prompt
   - 心理支持 prompt
   - 高风险安全 prompt
   - 每个模板有版本号
4. 定义 CHAT、CONSULT、RISK 意图。
5. 定义严格的模型评估 Schema。模型输出只视为建议，不视为临床事实。
6. 新建 app/ai/parsing.py：
   - 提取 JSON
   - Pydantic 校验
   - 枚举校验
   - 长度限制
   - 解析失败回退
7. 实现风险合并：
   - final_risk = max(hard_rule_risk, model_suggested_risk)
   - 硬规则 HIGH 不调用模型评估，或调用结果绝不能改变 HIGH
   - 模型超时、坏 JSON 和非法枚举回退硬规则
8. 不把模型自报的 confidence 当作真实概率；如为调试保存，字段名必须明确为 model_reported_confidence，且不对学生展示。
9. 实现经人工审阅的确定性 HIGH 安全回复模板：
   - 先承接情绪
   - 关注当下安全
   - 建议联系身边可信任的人、校心理中心、辅导员或当地紧急资源
   - 不提供危险细节
   - 最多问一个与当前安全直接相关的问题
10. 新建 app/services/turn_service.py，将单轮分为短事务和外部调用：
    - 事务 A：保存用户消息和硬规则报告，commit
    - 事务外：脱敏、意图识别、模型评估、生成回复
    - 事务 B：如模型提高风险，幂等地升级或创建报告
    - 事务 C：保存完整助手消息
11. Provider 故障时：
    - HIGH 返回确定性安全回复
    - 普通场景返回明确的服务暂不可用，不伪装为真实模型回复
    - 已保存的用户消息和风险报告不能回滚
12. 新增非流式 turns API，同时保留原来的消息保存和历史查询 API，避免一次破坏现有接口。
13. 学生响应只包含会话和公开助手消息，不包含意图、风险、prompt、provider 错误细节和 trace。

重点测试：

- 脱敏副本不包含手机号、邮箱和身份证号，原始数据库消息仍完整。
- 硬规则 HIGH 时模型无法降低风险。
- 模型把 LOW 提到 MEDIUM 时报告被幂等升级。
- 模型坏 JSON、超时和离线时回退正确。
- HIGH 在 Provider 完全离线时仍返回安全回复。
- AI 调用期间没有长时间持有写事务。
- 事务 A 失败时消息和报告全部回滚。
- 事务 B 重试时同一消息仍只有一份报告。
- 助手保存失败不删除已经落库的高风险用户消息和报告。
- 学生 DTO 不外显后台字段。

手工验收：

- 使用 Mock 分别发送普通、咨询、中风险和高风险消息。
- 检查数据库消息顺序和报告数量。
- 暂时配置一个不可达的 Ollama URL，验证普通错误与 HIGH 安全回复。

本阶段不做：

- 不做 SSE。
- 不做 RAG、Redis 或 Agent。
- 不在 prompt 中塞入全部历史。

Git 里程碑：

- 建议 commit：feat(chat): add safe ai turn orchestration
- 建议 tag：v0.9.0

### v0.10.0：可靠的 SSE 流式协议

状态：待开发

前置条件：

- v0.9.0 非流式闭环稳定。

阶段目标：

- 在不破坏持久化和安全边界的情况下提供流式回复。

编码顺序：

1. 定义统一 SSE 事件 Schema：
   - meta：sessionId、turnId
   - token：文本增量
   - error：公开错误码和可读消息
   - done：完成状态
   - heartbeat：可选
2. 所有 data 都是 JSON；禁止手工拼接未经转义的用户文本。
3. 在 Provider 契约中统一 AsyncIterator[AiStreamChunk]。
4. Ollama 和 OpenAI-compatible 都转换成相同内部 chunk。
5. 新建 GenerationRun 或 TurnRun 实体，记录：
   - PENDING
   - STREAMING
   - COMPLETED
   - FAILED
   - CANCELLED
6. 用户消息和硬规则报告在打开流之前完成短事务。
7. token 只缓存在服务器内存；只有收到完整完成信号后才保存一条完整助手消息。
8. 明确部分输出策略：
   - 断流或取消时不把半条助手消息当成完整历史
   - GenerationRun 记录失败原因的安全错误码
   - 不把 Provider 原始响应和密钥写入错误记录
9. 使用 request.is_disconnected 或取消信号停止上游请求。
10. 如果 Provider 在第一个 token 前失败，发送 error 后结束，不发送假的 done。
11. 如果 HIGH 场景真实 Provider 失败，切换到确定性安全回复流，并在后台记录 fallback 原因。
12. 设置 Cache-Control、X-Accel-Buffering 等必要响应头，并在文档解释代理缓冲问题。

重点测试：

- meta → token... → done 顺序固定。
- error 后不会再出现 done。
- 空 chunk、坏 NDJSON、坏 SSE 行被安全处理。
- 客户端取消会取消上游请求。
- 中途失败不会保存半条 assistant 消息。
- 成功完成只保存一条 assistant 消息。
- 同一 turn 重试不会产生重复完整回复。
- HIGH 离线 fallback 仍符合学生端隐私边界。

手工验收：

- 使用 curl 或 PowerShell 观察逐事件输出。
- 主动关闭客户端，检查 GenerationRun 为 CANCELLED。
- 重启服务后历史中没有半条消息。

本阶段不做：

- 不写浏览器页面。
- 不做 RAG 和多 Agent。

Git 里程碑：

- 建议 commit：feat(chat): add reliable sse streaming
- 建议 tag：v0.10.0

### v0.11.0：最小学生端页面

状态：待开发

前置条件：

- SSE 协议稳定。

阶段目标：

- 尽早从真实浏览器验证认证、会话、流式输出、错误和取消，而不是等到 v1.0。

编码顺序：

1. 创建 app/static/student.html、student.js 和最小 styles.css。
2. 页面只包含：
   - 本地学习阶段登录
   - 新建会话
   - 继续当前会话
   - 消息列表
   - 输入框
   - 发送、取消和重试
   - READY、THINKING、DONE、ERROR 状态
3. 使用 fetch 读取 ReadableStream 解析 SSE，不把 EventSource 用在需要 POST body 的场景。
4. 使用 textContent 渲染所有用户和模型文本，禁止把模型输出直接写入 innerHTML。
5. HTTP Basic 凭据最多保存在当前标签页的 sessionStorage，并在页面说明 Base64 不是加密，只适用于本地学习。
6. 管理员账户不得进入学生聊天。
7. 高风险回复正常显示，但页面不出现 HIGH、命中词、报告、分数和后台状态。
8. 静态路由放在 API 路由之后，避免根挂载吞掉 /api。

重点测试：

- 静态页面可访问。
- API 仍优先匹配。
- 管理员发送聊天得到 403。
- HTML/脚本字符串作为普通文本显示，不执行。
- SSE error 会恢复输入框，不留下永久 THINKING。

手工验收：

- 普通聊天、咨询、高风险、Provider 离线、取消五条路径逐一操作。
- 刷新页面后不会错误地复用已取消的 turn。

本阶段不做：

- 不做完整视觉设计。
- 不做管理后台。
- 不把 HTTP Basic 当作公网生产认证。

Git 里程碑：

- 建议 commit：feat(ui): add minimal student streaming chat
- 建议 tag：v0.11.0

### v0.12.0：知识文档摄取与生命周期

状态：待开发

前置条件：

- 单轮聊天链路稳定，开发数据库安全重建流程和 Schema 契约测试已可用。

阶段目标：

- 先把“知识从哪里来、如何更新、如何切块”做好，再写检索算法。

编码顺序：

1. 新增 KnowledgeDocument：
   - public_id
   - source
   - media_type
   - content_hash
   - version
   - status
   - created_at、updated_at
2. 新增 KnowledgeChunk：
   - document_id
   - chunk_index
   - stable_key
   - content
   - token_or_char_count
3. 在 SQLAlchemy ORM 中定义知识文档、知识分块及其唯一约束；实体变化后按统一流程重建开发 SQLite，并用 Schema 契约测试确认真实表结构。
4. 创建 app/knowledge 中的内置 Markdown；内容覆盖校园资源、隐私边界、焦虑、睡眠、学业压力、转介和风险政策。
5. 实现确定性 chunk_text：
   - size
   - overlap
   - 非法参数校验
   - 空文本处理
   - 稳定顺序
6. 使用 content_hash 实现幂等同步：内容不变不重建，内容变化事务性替换旧块。
7. 实现管理员文本摄取服务。
8. 加入 python-multipart 和 pypdf 后，再实现 Markdown、txt、PDF 上传。
9. 上传必须校验：
   - 管理员权限
   - 文件大小
   - 扩展名和 MIME
   - 编码
   - 空内容
   - 安全来源名
10. 用户文件名只能作为元数据，不能直接拼接本地路径。
11. 新增知识库状态接口，返回文档数、块数、失败文档，不返回服务器绝对路径。

重点测试：

- 相同文档重复同步不产生重复块。
- 内容变化后旧块被完整替换。
- chunk overlap 和稳定 key 可预测。
- 空文档、超大文件、伪装扩展名和损坏 PDF 被拒绝。
- 非管理员不能摄取知识。
- 一次摄取失败时旧版本仍可用。

手工验收：

- 启动后内置 Markdown 被幂等同步。
- 上传一份小 txt，状态接口块数正确。
- 再次上传相同内容，块数不增加。

本阶段不做：

- 不做向量。
- 不调用聊天模型总结文档。
- 不把上传内容直接放进系统 prompt。

Git 里程碑：

- 建议 commit：feat(rag): add knowledge ingestion lifecycle
- 建议 tag：v0.12.0

### v0.13.0：离线 RAG、动态路由与上下文边界

状态：待开发

前置条件：

- 知识块生命周期稳定。

阶段目标：

- 在完全没有云 API 和向量库时，先实现可解释、可评测的本地检索。

编码顺序：

1. 定义 RetrievalResult：
   - document_id
   - chunk_id
   - source
   - content
   - lexical_score
   - final_score
2. 实现中文和英文基础 tokenize。
3. 实现 BM25。
4. 实现短语命中、查询覆盖率和简单本地 rerank。
5. 对最佳块做有限相邻块扩展，避免只截到半句话。
6. 设置 candidate_k、top_k 和最大上下文字符预算。
7. 动态路由：
   - CHAT 默认不检索
   - CONSULT 和 RISK 才检索
   - HIGH 先走安全规则，RAG 不能延迟安全回复
8. 将知识上下文标记为“参考资料”，禁止知识文档覆盖系统安全规则。
9. 在 trace 中记录 chunk ID、source 和分数，不复制整份文档。
10. 无结果时返回空上下文，回复明确说明知识不足，不编造来源。

重点测试：

- 明确查询能召回预期 source。
- CHAT 不触发 KnowledgeService。
- CONSULT/RISK 才触发检索。
- top_k 和上下文预算有效。
- 邻块扩展不跨文档。
- 恶意知识文本不能修改硬规则优先级。
- 空知识库仍可生成安全通用回复。

手工验收：

- 针对睡眠、考试压力和转介各提一个问题，检查召回来源。
- 普通编程问题确认没有检索。

本阶段不做：

- 不安装 Chroma。
- 不调用 Embedding API。
- 不声称 BM25 是语义检索。

Git 里程碑：

- 建议 commit：feat(rag): add offline retrieval and dynamic routing
- 建议 tag：v0.13.0

### v0.14.0：向量混合 RAG、索引运维与评测

状态：待开发

前置条件：

- 离线 RAG 已有稳定基线和可解释结果。

阶段目标：

- 增加可选语义召回，同时保证向量服务故障时仍可回退离线 RAG。

编码顺序：

1. 定义独立 EmbeddingProvider Protocol，不复用 ChatProvider 接口。
2. 实现 FakeEmbeddingProvider 供测试使用。
3. 选择性实现：
   - OpenAI-compatible Embedding Provider
   - Ollama Embedding Provider
4. 聊天模型名与 embedding 模型名分开配置；微调 Qwen 聊天模型不自动等于 embedding 模型。
5. 引入 Chroma 持久化适配器。
6. 使用数据库 chunk stable_key 与 Chroma ID 一一对应。
7. 支持 upsert、删除旧 source、完整 rebuild 和精确 ID 对账。
8. 混合召回：
   - vector candidates
   - BM25 candidates
   - 分数归一化
   - 配置化权重融合
   - 确定性本地 rerank
9. 支持两种模式：
   - vector_required=false：故障回退 BM25
   - vector_required=true：明确暴露 readiness 失败
10. 新增管理员索引 status、rebuild 和 snapshot。
11. snapshot 必须在一致性边界内完成，不直接假设复制正在写入的目录一定安全。
12. 创建固定 RAG 评测集和 runner。
13. 输出 Recall@K、Precision@K、MRR、NDCG@K 和 HitRate。
14. CI 使用 Fake Embedding；真实 embedding 只做可选本地评测。

重点测试：

- 向量和 BM25 候选正确融合。
- 分数全相等、只有一种召回、空候选时不除零。
- Chroma 不可用时 optional 模式回退。
- required 模式正确失败。
- rebuild 后 ID 与数据库完全一致。
- 更新文档后旧向量被删除。
- 评测指标计算有固定小样本单元测试。

手工验收：

- 运行一次离线评测并保存 JSON 报告。
- 禁用向量后相同 API 仍可通过 BM25 工作。

本阶段不做：

- 不引入 Agent。
- 不把向量命中分数当作心理风险概率。

Git 里程碑：

- 建议 commit：feat(rag): add hybrid vector retrieval and evaluation
- 建议 tag：v0.14.0

### v0.15.0：受限短期记忆与上下文压缩

状态：待开发

前置条件：

- 单轮 prompt 和 RAG 上下文预算已经明确。

阶段目标：

- 让多轮对话有连续性，但不无限增长 prompt，也不让 Redis 成为业务事实来源。

编码顺序：

1. 定义 ShortTermMemoryStore Protocol。
2. 先实现 InMemory/Fake Store 和数据库历史读取。
3. 实现 Redis Store：
   - 每会话独立 key
   - key 包含稳定命名空间
   - TTL
   - 最大消息数
   - socket timeout
4. Redis 是缓存；完整聊天数据库才是 source of truth。
5. Redis 为空时从数据库最近消息回填。
6. Redis 连接、读取和写入失败时记录脱敏警告并回退数据库，不中断聊天。
7. 写入 Redis 前再次脱敏。
8. 实现上下文裁剪：
   - 保留最近 N 条
   - 限制总字符或 token 预算
   - system 指令单独保留
9. 先实现确定性摘要；再把模型摘要作为可选增强。
10. 模型摘要失败时回退确定性摘要。
11. 摘要不得包含诊断、风险标签、后台报告、工具任务和敏感标识符。
12. 对不同用户和会话做隔离测试。

重点测试：

- Redis 空时从数据库回填。
- Redis 完全不可用时聊天仍工作。
- TTL 和最大长度被设置。
- 历史压缩保留最近消息。
- 摘要长度受限并已脱敏。
- 用户 A 无法读到用户 B 的记忆。
- prompt 不因长历史无限增长。

手工验收：

- 连续聊天超过最大消息数，回复仍能引用近期上下文。
- 关闭 Redis 后继续聊天，确认走数据库回退。

本阶段不做：

- 不让 Redis 保存完整永久记录。
- 不做“无限长期人格记忆”。
- 不开始多 Agent。

Git 里程碑：

- 建议 commit：feat(memory): add bounded short-term memory
- 建议 tag：v0.15.0

### v0.16.0：标准 Skills 注册、校验与选择

状态：待开发

前置条件：

- 单 Agent 回复 prompt 已稳定。

阶段目标：

- 把可复用的支持策略从大段硬编码 prompt 中拆出来，并在进入多 Agent 前独立测试。

编码顺序：

1. 创建 skills 目录，每个 Skill 使用独立目录和 SKILL.md。
2. 定义严格元数据：
   - name
   - description
   - version
   - allowed_intents
   - allowed_risks
3. 使用安全的 frontmatter 解析和 Pydantic 校验。
4. 实现 Skill Registry：
   - list
   - get_required
   - validation report
   - 内容 hash/version
5. 实现确定性 Skill Selector。
6. 首批 Skills：
   - supportive_response_baseline
   - high_risk_safety_plan
   - anxiety_grounding_support
   - sleep_routine_support
   - academic_stress_planning
   - referral_resource_guidance
   - counselor_handoff_summary
7. Skills 只提供经过审阅的策略或模板，不自动执行 Python、Shell、网络和工具。
8. 高风险只允许经过白名单的 Skill 进入 prompt。
9. 模板渲染采用显式字段白名单；缺字段应失败，不静默留下占位符。

重点测试：

- 合法 Skill 可加载。
- 缺元数据、重复名称、目录名不一致和非法风险枚举会报告错误。
- CHAT 不加载心理支持 Skills。
- HIGH 必定加载 baseline 和 safety plan。
- 焦虑、睡眠、学业压力选择对应 Skill。
- 模板不会执行任意表达式。
- skill 内容或版本出现在 trace，而不是复制全部正文。

手工验收：

- 查看 Skill 状态报告。
- 用四类输入检查选择结果。

本阶段不做：

- 不把 Skill 当作任意代码插件。
- 不让模型自行从磁盘读取任意文件。

Git 里程碑：

- 建议 commit：feat(skills): add validated support skills
- 建议 tag：v0.16.0

### v0.17.0：单轮 Runtime Harness、Trace 与工程 Harness

状态：待开发

前置条件：

- AI、RAG、记忆和 Skills 都已有独立服务。

阶段目标：

- 在多 Agent 之前，把一轮业务编排集中到一个可观察、可替换、可测试的边界。

编码顺序：

1. 定义 TurnInput、TurnContext、TurnOutcome 和 TurnFailure。
2. 新建 MindBridgeTurnHarness，统一组织：
   - 用户和会话解析
   - 原始输入与脱敏输入
   - 硬规则
   - 意图
   - 记忆
   - RAG
   - Skills
   - 模型请求
   - 安全回复
   - 持久化计划
3. HTTP 路由只负责认证、输入 DTO 和 SSE 输出，不再承载业务细节。
4. runtime 只返回结果，不在 Agent 节点内部随意 commit。
5. 新增 AgentRunTrace 或 TurnTrace，至少记录：
   - message_id、session_id
   - route
   - 最终风险
   - hard rule version
   - prompt version
   - provider/model
   - skill versions
   - retrieval chunk IDs
   - fallback reason
   - 各步骤耗时
6. Trace 默认不重复保存完整原始输入；引用原消息并保存脱敏模型输入。
7. Trace 不保存 API key、Authorization、完整 Skill 文件、完整知识文档和绝对模型路径。
8. 建立 app/harness/runner.py，使用 Mock、临时 SQLite、Fake Redis、Fake Embedding 和 Fake Tool 验证核心链路。
9. Harness 报告写入 target，target 不进入 Git。
10. 如果 Trace 采用数据库表持久化，完成 ORM 和测试后按统一流程重建开发 SQLite；不得依赖 create_all 给旧表补字段或约束。

重点测试：

- HTTP 层替换成 Fake Harness 后仍能测试协议。
- 同一输入的 Mock trace 稳定可比较。
- trace 不含常见敏感标识符和秘密。
- CHAT、CONSULT、RISK 三条路径步骤正确。
- Provider、Redis、Vector 分别故障时 fallback 原因正确。
- runtime 不直接 commit 的契约测试。

手工验收：

- 一条命令运行工程 Harness。
- 生成 JSON 报告并能定位每个步骤和耗时。

本阶段不做：

- 不拆多 Agent。
- 不把 trace 开放给学生。

Git 里程碑：

- 建议 commit：feat(runtime): add turn harness and sanitized traces
- 建议 tag：v0.17.0

### v0.18.0：有界自研多 Agent Runtime

状态：待开发

前置条件：

- 单轮 Harness 输出契约稳定。

阶段目标：

- 先用普通 Python 实现看得懂、可调试的有限循环，再考虑 LangGraph。

编码顺序：

1. 定义 AgentContext、AgentStep、AgentRunResult 和 StopReason。
2. 定义 Agent Protocol，每个 Agent 只负责一个职责。
3. 第一版角色：
   - MemoryAgent：读取和压缩历史
   - SupervisorAgent：CHAT/CONSULT/RISK 路由
   - KnowledgeAgent：仅必要时检索
   - RiskGuardianAgent：硬规则和模型风险合并
   - CompanionAgent：普通任务回复计划
   - CounselorAgent：心理支持回复计划
4. 先写显式的状态条件，不让 Agent 随机决定顺序。
5. 设置 max_steps 和明确停止原因。
6. HIGH 风险可以安全抢占，不等待非必要 RAG。
7. Response 只产生候选消息，最终安全门由 Harness 控制。
8. runtime 不直接写数据库、不发邮件、不写 Excel。
9. 每一步写入 trace，但不保存完整 prompt。
10. 增加 runtime factory，可在 single 与 custom_multi 之间切换。

重点测试：

- CHAT 跳过 RAG 和心理报告。
- CONSULT 使用记忆、RAG 和 Skills。
- RISK 的硬规则优先。
- max_steps 防止无限循环。
- 没有可运行 Agent 时返回明确 StopReason。
- 相同场景 single 与 custom_multi 的公开安全结果一致。
- Agent 内部不能直接 commit 或执行外部工具。

手工验收：

- 状态接口展示当前 runtime 和最大步数。
- Harness 报告能看到每个 Agent step。

本阶段不做：

- 不安装 LangGraph。
- 不做事件驱动黑板。
- 不为每个 Agent 配多个真实大模型。

Git 里程碑：

- 建议 commit：feat(agents): add bounded custom multi-agent runtime
- 建议 tag：v0.18.0

### v0.19.0：LangGraph 适配与行为等价

状态：待开发

前置条件：

- 自研 runtime 已有稳定输入和输出契约。

阶段目标：

- 把同一状态机适配到 LangGraph，而不是借框架重新发明业务规则。

编码顺序：

1. 将 langgraph 和 langchain-core 作为可选运行依赖加入。
2. 定义 GraphState，仅包含可序列化或明确可追踪的数据。
3. 建立 controller、memory、supervisor、knowledge、risk_guardian、companion、counselor 节点。
4. 每个节点调用现有领域服务，不复制风险规则和 RAG。
5. 配置 recursion_limit 和 max_steps。
6. runtime factory 支持：
   - custom
   - langgraph
7. 请求 langgraph 但未安装时：
   - 开发配置可显式回退 custom
   - required 配置必须 readiness 失败
8. 状态接口同时显示 requested、active、fallbackReason。
9. 建立 runtime parity 测试集。

重点测试：

- 三类意图在两套 runtime 的公开结果一致。
- HIGH 都不被降级。
- 最大步数和停止原因一致。
- LangGraph 不可用时按配置回退或失败。
- LangGraph 节点不直接 commit。

手工验收：

- 分别以 custom 和 langgraph 运行同一 Harness 场景。
- 比较公开结果和 trace。

本阶段不做：

- 不做自由自主协作。
- 不让框架控制工具权限。

Git 里程碑：

- 建议 commit：feat(agents): add langgraph runtime parity
- 建议 tag：v0.19.0

### v0.20.0：事件驱动多 Agent 协作

状态：可选增强，建议在 v0.19.0 后完成

阶段目标：

- 吸收最终版任务认领、追加式黑板、安全审查和修订循环的思想，同时保持有界和可测试。

编码顺序：

1. 定义不可变 AgentTask、AgentMessage、AgentArtifact 和 AgentEvent。
2. 定义 append-only CollaborationBlackboard。
3. 定义 AgentCapability 和 AgentRegistry。
4. Agent 根据能力和显式置信理由认领任务，不按列表固定顺序假装“自主”。
5. Coordinator 只负责：
   - 任务板
   - 优先级
   - 预算
   - 冲突仲裁
   - 最终采纳
6. 实现 Understanding、Safety、Context 和 Response 四类独立 Agent。
7. SafetyAgent 可发布 SAFETY_OVERRIDE。
8. 候选回复必须经过 SafetyAgent 审查；不通过时产生 critique 和有界 revision。
9. 设置：
   - max_rounds
   - max_claims_per_round
   - max_claims_per_agent
   - minimum_acceptance
10. 每 Agent 的模型配置使用类型化 AgentModelProfile 或 AiRequestOptions，不复制并修改全局 Settings。
11. 每 Agent 私有记忆、模型和工具权限先作为明确策略；真正工具执行仍由治理层控制。
12. 所有事件、任务和 artifact 可进入脱敏 trace。

重点测试：

- 黑板更新不修改旧对象。
- artifact 不互相覆盖。
- 高优先级安全任务先被处理。
- 认领预算阻止无限协作。
- HIGH 产生 SAFETY_OVERRIDE。
- 未经安全审查的回复不能被采纳。
- 修订循环达到上限后安全停止。
- 每 Agent 模型覆盖不污染全局默认值。

手工验收：

- Harness 展示任务创建、认领、artifact、review、accept 的完整事件序列。

本阶段不做：

- 不宣称多个 Agent 自动等于更高质量。
- 不允许模型直接执行外部工具。
- 不把这一高级阶段作为安全硬规则的替代品。

Git 里程碑：

- 建议 commit：feat(agents): add event-driven collaboration runtime
- 建议 tag：v0.20.0

### v0.21.0：管理员报告与风险个案生命周期

状态：待开发

前置条件：

- 报告和 trace 已稳定。

阶段目标：

- 把后台报告变成可跟进的个案，而不是只生成一行记录。

编码顺序：

1. 扩展管理员报告查询：
   - 分页
   - 风险筛选
   - 时间筛选
   - 会话查看
2. 报告仍只关联消息，不复制完整正文。
3. 新增 RiskCase：
   - report_id 唯一
   - public_id
   - status
   - owner
   - acknowledged_by/at
   - resolved_by/at
   - created_at/updated_at
4. 明确状态机：
   - OPEN
   - ALERT_QUEUED
   - ALERT_SENT
   - ACKNOWLEDGED
   - RESOLVED
5. 新增 CaseNote，记录 actor、note 和时间。
6. MEDIUM/HIGH 可创建个案；HIGH 优先级更高。
7. 同一报告重复创建必须返回同一个个案。
8. 使用 counselor_handoff_summary Skill 生成最小化交接摘要。
9. 所有写操作要求管理员权限并记录审计 actor。
10. 学生接口继续不提供后台风险明细。
11. RiskCase 和 CaseNote 改变 ORM Schema 后，确认数据可丢弃并重建开发 SQLite，再运行 Schema 契约和完整回归测试。

重点测试：

- 学生不能查看报告、个案、备注和会话审阅。
- 管理员分页和筛选正确。
- 同一 report 只有一个 case。
- 非法状态跳转被拒绝。
- ACKNOWLEDGED 和 RESOLVED 记录 actor 和时间。
- 备注空文本、超长文本被拒绝。
- 404 不泄露不存在与无权限的差别。

手工验收：

- 用 HIGH 消息创建个案。
- 管理员确认、添加备注、解决个案。
- 学生端始终看不到后台字段。

本阶段不做：

- 不发真实邮件。
- 不把 Excel 当数据库。
- 不做自动联系紧急服务。

Git 里程碑：

- 建议 commit：feat(admin): add reports and risk case lifecycle
- 建议 tag：v0.21.0

### v0.22.0：工具治理、事务型 Outbox 与可靠队列

状态：待开发

前置条件：

- 风险个案状态机稳定。

阶段目标：

- 把 Excel、个案和预警等副作用放到持久化队列，并真正执行权限策略、幂等、重试和死信。

编码顺序：

1. 定义 ToolPolicy 和 ToolPolicyRegistry。
2. 白名单工具：
   - EXCEL_REPORT
   - CASE_CREATE
   - ALERT_SEND
3. 每个策略明确允许的风险等级、必需输入和前置任务。
4. 新增 ToolJob：
   - kind
   - idempotency_key
   - status
   - attempts
   - max_attempts
   - depends_on_job_id
   - run_after
   - last_error_code
5. 新增 ToolAuditRecord 和 DeadLetterRecord。
6. 在报告/个案事务中同时写 outbox job，避免“报告已提交但任务未入队”的丢失窗口。
7. 队列执行前必须调用治理策略；禁止只写策略单元测试却不接入执行链。
8. 实现适配器：
   - ExcelLedgerAdapter
   - LogAlertAdapter
9. 数据库是事实来源；Excel 只是导出。
10. Excel 使用单写者或锁，重复 report 不重复写行。
11. CASE_CREATE 成功后 ALERT_SEND 才可运行。
12. 实现指数或线性退避、最大次数、死信、服务重启恢复 RUNNING。
13. 为 alert 加每分钟限流。
14. worker 由 lifespan 启停，测试可注入同步 Fake Worker。
15. 工具失败不得阻塞学生 SSE。
16. ToolJob、ToolAuditRecord、DeadLetterRecord 和 outbox 改变 ORM Schema 后，按统一流程重建开发 SQLite，并验证唯一约束、外键和索引。

重点测试：

- 不允许的风险等级被治理层阻止，且适配器未被调用。
- 未知工具永远拒绝。
- 同一 idempotency_key 不产生重复任务。
- 依赖未完成时 alert 不运行。
- 失败按计划重试并最终进入 dead letter。
- 重启后 RUNNING 恢复为可重试状态。
- Excel 重复执行不重复写。
- 对话响应不等待工具完成。
- ToolAudit 记录授权、执行和结果，但不含秘密。

手工验收：

- log 模式运行 HIGH 场景，观察 job → case → alert。
- 故意让 Excel 路径不可写，观察重试和 dead letter。

本阶段不做：

- 不直接启用 SMTP。
- 不让 LLM 自由选择任意工具名。
- 不使用只存在于内存的队列作为唯一任务记录。

Git 里程碑：

- 建议 commit：feat(tools): add governed durable tool queue
- 建议 tag：v0.22.0

### v0.23.0：MCP 工具边界与真实预警适配器

状态：待开发

前置条件：

- 本地工具服务和治理队列已经稳定。

阶段目标：

- 用 MCP 暴露受控工具边界，同时保留直接本地适配器，避免 MCP 故障破坏核心聊天。

编码顺序：

1. 引入 MCP 依赖时明确支持的 Python 版本。
2. 创建 app/mcp_tools/server.py，暴露受限工具：
   - mindbridge_excel_report
   - mindbridge_case_create
   - mindbridge_alert_send
   - mindbridge_alert_ack
   - mindbridge_case_note_add
3. MCP 工具只接收 ID 和必要参数，不接受任意 SQL、文件路径、命令或收件人。
4. MCP 工具复用同一 ToolGovernanceService 和适配器，不复制业务逻辑。
5. 创建 MCP Client Adapter；使用 stdio 时固定当前 Python 和项目根目录。
6. 队列仍是默认执行方式；MCP 作为可替换边界或调试方式。
7. 新增 SMTP Adapter：
   - 默认 delivery_mode=log
   - 只有显式 smtp 才发送
   - SMTP 密码使用 SecretStr
   - TLS/SSL 配置互斥校验
8. SMTP 失败记录为任务失败，不回滚聊天和报告。
9. MCP 返回错误必须映射成稳定工具错误，不能只解析自然语言字符串。
10. 如未来使用远程 MCP，再单独增加身份认证、TLS 和网络策略；当前只做本地 stdio。

重点测试：

- Fake MCP Session 验证工具名和参数。
- 任意路径、未知工具和越权风险被拒绝。
- MCP 和直接适配器产生相同业务结果。
- SMTP Fake 验证主题和收件人，但不发送真实邮件。
- 缺配置时清楚失败，秘密不进日志。
- MCP 子进程失败进入队列重试。

手工验收：

- 本地启动 MCP server 并调用 log 模式工具。
- 不配置 SMTP 时不会误发邮件。

本阶段不做：

- 不让模型绕过队列直接调用 MCP。
- 不自动联系老师、家长、警方或紧急服务。
- 不在测试中发送真实邮件。

Git 里程碑：

- 建议 commit：feat(mcp): add governed tool protocol and alert adapters
- 建议 tag：v0.23.0

### v0.24.0：管理端运维页面

状态：待开发

前置条件：

- 管理 API、知识库 API、trace 和工具队列均已稳定。

阶段目标：

- 为管理员提供可操作但不过度暴露敏感数据的工作台。

编码顺序：

1. 创建 admin.html、admin.js 和对应样式。
2. 页面模块：
   - 报告列表和筛选
   - 风险个案和状态
   - 个案备注
   - 会话审阅
   - 知识库状态、上传、重建、备份
   - 工具任务
   - dead letter
   - 脱敏 trace
   - 工具审计
   - AI/模型 readiness
3. 默认列表只显示摘要，查看完整消息需要明确点击。
4. 所有内容用 textContent 或安全 DOM API。
5. 管理员操作包含确认提示和并发状态处理。
6. 所有 API 仍在服务端做 require_admin；隐藏按钮不是授权。
7. readiness 区分：
   - app liveness
   - database
   - AI Provider
   - Ollama registration
   - Redis
   - vector store
   - tool worker
8. 不在浏览器显示 API key、SMTP 密码和绝对路径。

重点测试：

- 学生访问管理 API 全部 403。
- 空数据、加载中、失败、分页和重试状态正确。
- 用户消息中的 HTML 不执行。
- 个案状态并发修改得到冲突提示。
- 状态接口不泄露秘密。

手工验收：

- 从一条 HIGH 学生消息完整走到管理员确认、备注和工具任务查看。
- 模拟 Redis/Ollama/向量不可用，页面分别显示降级而不是统一“系统坏了”。

本阶段不做：

- 不做复杂前端框架迁移。
- 不用前端权限替代后端授权。

Git 里程碑：

- 建议 commit：feat(ui): add admin operations console
- 建议 tag：v0.24.0

### v0.25.0：MySQL、Redis、Docker 与全新环境交付

状态：待开发

前置条件：

- 全部核心 API 和后台任务已稳定。

阶段目标：

- 把本地开发链路转成可重复创建的学习和演示环境，并确保模型、秘密和运行数据仍然外置。
- 只承诺从空 SQLite、空 MySQL Schema 或空 Compose volume 初始化当前版本，不承诺升级带有旧结构和历史数据的数据库。

编码顺序：

1. 使用当前 SQLAlchemy ORM metadata 在空 MySQL database 中创建完整 Schema，并验证所有必需表、索引和约束存在。
2. 检查当前版本 SQLite 与 MySQL 的：
   - 时区
   - 唯一约束
   - Text 长度
   - 级联
   - 并发任务领取
3. requirements.txt 加入 PyMySQL 和 cryptography。
4. 创建 Dockerfile。
5. Docker 镜像必须复制：
   - app
   - scripts
   - skills
   - 内置 knowledge
   - static
   - rag_eval
   - Modelfile 和模型说明
6. Docker 镜像不得复制：
   - GGUF
   - .env
   - 本地数据库
   - Redis 数据
   - Chroma 运行数据
   - Excel
   - trace/harness 报告
7. 创建 docker-compose：
   - mysql
   - redis
   - 只面向空 database/volume 的一次性 Schema 初始化步骤
   - app
8. Schema 初始化只负责空数据库首次建表；非空数据库必须先通过当前 Schema 契约检查，不兼容时安全退出并提示显式重建。不得把 create_all 描述为旧数据库升级，也不得在应用启动时自动修改或删除旧 volume。
9. Ollama 默认在宿主机或独立服务，由显式 URL 连接；不在应用容器内偷偷下载模型。
10. 为 MySQL 和 Redis 配 healthcheck，应用 readiness 检查依赖状态。
11. 应用 liveness 不因可选向量或 Ollama 离线而失败；readiness 显示精确原因。
12. 不提供写死的生产密码，必须由环境变量或 secret 注入。
13. 创建 Windows PowerShell 发布脚本；可选再提供 Bash。
14. 发布包排除密钥、数据、日志、模型权重和压缩模型。
15. 模型作为独立交付物，记录文件名、大小和校验和。
16. CI 保留 SQLite 快速测试，并增加使用全新临时 MySQL/Redis 的可选集成 job。

重点测试：

- 空 MySQL Schema 可由当前 ORM metadata 完整初始化。
- 对结构完全一致的数据库第二次执行 create_all 不报错，并保留已经写入的测试数据。
- 非空但结构不兼容的 MySQL 数据库被拒绝，初始化过程不自动改表、不清空数据。
- SQLite 和 MySQL 核心契约测试一致。
- Compose 的 app 等待数据库健康。
- Redis 故障时应用按设计降级。
- 构建后的镜像确实包含 skills 和 knowledge。
- 镜像和发布包中不存在 gguf、.env、xlsx、db 和密钥。
- 容器能使用 Mock 模式完成 Harness。

手工验收：

- docker compose 从空 volume 启动。
- 从空 volume 初始化 Schema，并运行 Mock 聊天、RAG、个案和 log 工具链。
- 在 Schema 没有变化时重启 Compose，已有测试数据仍然存在。
- 如宿主机模型已迁移并注册，再做一次可选 Ollama 联调。

本阶段不做：

- 不把本地模型权重构建进镜像。
- 不把 Docker Compose 当作真实生产高可用方案。
- 不支持旧版本 SQLite 或 MySQL 数据库的原位结构升级、downgrade 或跨引擎数据转换。
- Schema 发生变化时，学习和演示环境通过明确警告后的 volume 重建获得新结构。
- 如果未来需要保留真实 MySQL 数据，必须先新增版本化迁移、备份恢复和演练阶段，之后才能继续发布。

Git 里程碑：

- 建议 commit：feat(deploy): add containers and safe release packaging
- 建议 tag：v0.25.0

### v1.0.0：完整回归、安全硬化与学习版可交付文档

状态：待开发

前置条件：

- v0.6.0 至 v0.25.0 的必需阶段均达到验收标准。
- v0.20.0 事件驱动 runtime 可以按学习目标选择启用；即使未启用，custom 和 LangGraph 仍需稳定。

阶段目标：

- 不再添加大功能，集中证明现有功能在正常、降级和失败状态下行为可靠。

验收工作顺序：

1. 完整 unittest、API、SSE、空库初始化/开发库重建和端到端回归。
2. 提高 coverage 门槛，并列出刻意不覆盖的外部集成边界。
3. 运行 Ruff、mypy、compileall、依赖检查和秘密扫描。
4. 建立安全回复评测集：
   - 明确高风险
   - 隐晦高风险
   - 否定表达
   - 新闻/教学引用
   - 普通压力
   - 模型离线
5. 验证硬规则误报和漏报边界，不把测试通过描述成临床有效。
6. 固化 RAG 指标基线和最低门槛。
7. 运行 runtime parity 和 Agent 预算测试。
8. 运行工具失败注入：
   - Excel 不可写
   - SMTP 不可达
   - MCP 退出
   - Redis 离线
   - Chroma 损坏或缺失
   - Ollama 超时
9. 测试并发 SSE、客户端取消、重复请求和幂等。
10. 审阅所有日志、trace、错误响应和前端，确认没有密码、密钥、Authorization、完整 prompt 和不必要的敏感副本。
11. 编写：
    - README
    - 本地开发说明
    - 模型迁移与 Ollama 注册说明
    - 开发 SQLite 数据丢失警告、可选备份和安全重建说明
    - 空 SQLite/MySQL 首次初始化说明
    - 当前不支持已有数据库无损升级、downgrade 和跨引擎数据转换的限制说明
    - RAG 重建和备份恢复
    - Redis/MySQL 故障排查
    - 工具队列和 dead letter 处理
    - Docker 部署
    - 发布包清单
    - 安全和隐私边界
12. 明确声明：
    - 项目不是医学或心理诊断系统
    - 项目不是自动危机干预或紧急救助系统
    - 真实部署需要学校制度、持证专业人员、法律合规、隐私评估和人工值守
13. 用户迁移微调模型后，单独执行模型验收：
    - 文件校验和
    - Ollama 注册
    - readiness
    - 普通聊天
    - 心理支持
    - 高风险离线与在线安全回复

最终交付标准：

- 一条命令运行本地质量检查。
- 一条命令运行 Mock 工程 Harness。
- 一套固定 RAG 评测。
- 一套固定安全回复评测。
- Compose 可从空环境启动。
- 同一 ORM Schema 下重复启动不会删除已经写入的数据；Schema 变化时按文档显式重建学习环境。
- 非空但结构不兼容的数据库会安全拒绝启动，不会被 create_all 部分修改，也不会被应用自动删除。
- 外部服务逐个故障时有清楚、可测试的降级行为。
- 学生端不外显后台标签。
- 模型权重、秘密和运行数据均未进入 Git 或应用发布包。
- v1.0.0 只表示学习版功能链路和可重复演示环境完成，不表示已经具备生产数据库无损升级、生产备份恢复或零停机发布能力。

Git 里程碑：

- 建议 commit：release: harden mindbridge learn 1.0
- 建议 tag：v1.0.0

## 八、阶段依赖关系

必须按下面的主链推进：

    v0.5 风险硬规则
      ↓
    v0.6 可重建开发数据库与工程护栏
      ↓
    v0.7 AI 契约和 Mock
      ↓
    v0.8 真实 Provider 和模型资产
      ↓
    v0.9 非流式安全闭环
      ↓
    v0.10 SSE
      ↓
    v0.11 学生端
      ↓
    v0.12 知识摄取
      ↓
    v0.13 离线 RAG
      ↓
    v0.14 向量 RAG 和评测
      ↓
    v0.15 记忆
      ↓
    v0.16 Skills
      ↓
    v0.17 Harness 和 Trace
      ↓
    v0.18 自研多 Agent
      ↓
    v0.19 LangGraph
      ↓
    v0.20 事件驱动协作，可选增强
      ↓
    v0.21 管理报告和个案
      ↓
    v0.22 工具治理和队列
      ↓
    v0.23 MCP 和预警适配器
      ↓
    v0.24 管理端
      ↓
    v0.25 部署和发布
      ↓
    v1.0 回归与硬化

不能颠倒的关键依赖：

- 没有 AI 契约和 Mock，不开始真实 Ollama。
- 没有非流式完整闭环，不开始 SSE。
- 没有知识摄取生命周期，不开始向量索引。
- 没有离线检索基线，不开始混合向量 RAG。
- 没有上下文预算，不开始多 Agent。
- 没有 Skills 和单轮 Harness，不开始多 Agent 拆分。
- 没有个案状态机，不开始真实预警。
- 没有工具治理和持久化队列，不让模型或 MCP 执行副作用。
- 没有 SQLite/MySQL 空库 Schema 契约验证、安全初始化流程和明确的数据丢失边界，不做最终容器交付。
- 没有版本化数据库迁移、备份恢复和演练能力时，不宣称支持已有生产数据库升级。

## 九、每个阶段的统一即时测试顺序

每写完一个小模块，都按下面顺序测试，不要等整个版本写完再一次排错。

1. 只运行当前模块测试，例如：

       python -m unittest tests.test_xxx -v

2. 运行与它直接相邻的服务测试。
3. 运行 API 集成测试。
4. 运行完整测试：

       python -m unittest discover -s tests -v

5. 运行项目检查：

       powershell -ExecutionPolicy Bypass -File .\scripts\check.ps1

6. 查看工作区和空白问题：

       git status
       git diff --check
       git diff

7. 只有全部通过才进入本阶段下一小步。

真实外部服务测试顺序：

1. 先用 Fake 或 MockTransport 测成功和失败。
2. 再用 Mock Provider 跑完整业务链。
3. 再手工联调本地 Ollama、Redis、Chroma、MySQL 或 MCP。
4. 外部服务联调失败不能成为 CI 失败的唯一原因；CI 应测试适配器契约和降级逻辑。

## 十、每个里程碑的本地 Git 操作提醒

以下命令只作为开发者本地操作提醒。Codex 不安装 Git、不执行 commit、不创建 tag、不 push。

### 提交前

    git status
    git diff --check
    git diff
    powershell -ExecutionPolicy Bypass -File .\scripts\check.ps1

确认：

- 没有 .env。
- 没有数据库、Excel、日志、Chroma 数据和 target 报告。
- 没有 GGUF、safetensors、bin 或模型压缩包。
- 没有与本阶段无关的修改。

### 加入暂存区

一次加入多个文件没有问题。确认工作区只包含本阶段修改时，可以：

    git add -A

如果工作区还有不相关修改，使用路径限制范围：

    git add app tests scripts DEVELOPMENT_PLAN.md

然后检查真正准备提交的内容：

    git diff --cached --check
    git diff --cached
    git status

### commit、tag 和 push

    git commit -m "使用本阶段建议的 commit 信息"
    git tag -a vX.Y.Z -m "MindBridge Learn vX.Y.Z"
    git push origin main
    git push origin vX.Y.Z

tag 只在完整验收通过后创建。

如果同一里程碑第一次 commit 漏了文件：

- 尚未 push：检查后可以 git commit --amend --no-edit。
- 已经 push：初学阶段优先追加一个清楚的修复 commit，不随意改写远端历史。

## 十一、当前下一步

v0.7.0 已完成 AI 内部契约、异常层级、Provider Protocol、确定性 Mock、严格工厂、应用组装和完整质量验收。

当前质量基线为 96 个测试全部通过、综合分支覆盖率 93%；聊天 API 仍未调用 Provider，数据库 Schema 没有变化。

下一阶段是 v0.8.0：真实 Provider 与本地微调模型资产。v0.8.0 将复用 v0.7.0 的通用契约和 AI_PROVIDER、AI_TEMPERATURE、AI_MAX_TOKENS，只新增 httpx 运行时依赖、网络超时、Ollama/OpenAI-compatible 配置、真实适配器和模型 readiness。

本地微调模型迁移安排在 v0.8.0：

- 现在不复制。
- 到该阶段先完成目录、忽略规则、状态检查和 MockTransport 测试。
- 然后由开发者本人把最终版根目录 models 中的微调模型目录迁移过来。
- 应用仍通过 Ollama HTTP 调用，不让 Python 直接加载 GGUF。
