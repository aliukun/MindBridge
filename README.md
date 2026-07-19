# MindBridge Learn

从零实现的校园心理支持智能体学习项目。它用于学习 FastAPI、数据库、AI Provider、
隐私保护与安全分流的完整工程链路，不是医学诊断工具，也不应直接作为真实危机干预
系统部署。

## 当前版本

v0.9.0

## 当前已完成

### 应用、数据与安全基础

- FastAPI 应用工厂、lifespan 资源管理和集中配置管理
- 公开健康检查、统一公共错误响应和 `X-Request-ID` 链路标识
- SQLAlchemy 数据库基础设施与 SQLite 本地持久化
- 非空数据库 Schema 兼容性只读检查
- SQLite 每连接强制启用外键约束和数据库级 `ON DELETE CASCADE`
- 受保护的开发数据库重建脚本
- UserAccount、ChatSession、ChatMessage 和 PsychologicalReport 实体
- Argon2id 密码哈希、HTTP Basic 身份认证和学生/管理员角色授权
- 创建会话、保存用户消息、保存助手消息和查询聊天历史
- 会话所有权隔离；其他用户的会话统一按不存在处理
- 密码、密钥、Authorization 和数据库凭据日志脱敏

### 风险、隐私与完整非流式聊天轮次

- LOW、MEDIUM、HIGH 风险等级和确定性关键词硬规则
- 高风险优先判断、Unicode 文本归一化和规则版本记录
- MEDIUM/HIGH 后台心理安全报告，以及消息与报告的原子写入
- 报告幂等创建和风险只升不降更新
- 手机号、邮箱、身份证号和带标签学号的 Provider 前脱敏
- 带版本号的 `analysis_v1` 与 `reply_v1` Prompt
- CHAT、CONSULT、RISK 三类内部意图
- 严格 JSON analysis 解析、固定字段校验、枚举校验和额外字段拒绝
- 硬规则与模型建议的单调风险合并：模型只能提高风险，不能降低风险
- 普通轮次一次 analysis，加至多一次 reply 的模型调用上限
- 硬规则 HIGH 零模型调用并直接使用固定安全回复
- analysis 将风险升级为 HIGH 后不再生成自由文本，直接使用固定安全回复
- MEDIUM 在 Provider 故障时使用明确、固定的支持性降级回复
- LOW 在 Provider 故障时返回稳定 503，同时保留已经提交的用户消息
- A/B/C 三段短事务，避免在网络等待期间长期占用数据库事务
- `POST /api/chat/sessions/{session_public_id}/turns` 非流式安全单轮 API
- 学生 DTO 不暴露意图、风险等级、命中信号、报告或模型分析过程

### AI Provider 与本地模型

- 内部 AI 消息、请求、完成结果和流式块契约
- system、user、assistant AI 角色边界和请求参数范围校验
- 稳定的 AI 异常层级和异步 `AiProvider` Protocol
- 离线确定性 Mock Provider
- Ollama 非流式与 NDJSON 流式 Provider
- OpenAI-compatible 非流式与 SSE 流式 Provider
- 严格 Provider Factory；未知名称拒绝启动，不静默回退 Mock
- 共享 `httpx.AsyncClient` 生命周期、分阶段超时和整次调用总时限
- 真实 Provider 网络与协议错误的稳定内部映射
- 本地模型 asset、server、registration、inference 四层 readiness
- 管理员 AI 状态接口，以及 Windows 模型检查和显式注册脚本
- 本机 Ollama 托管 GGUF 的真实注册、最小推理和 `/turns` 调用链已验收

### 工程质量

- unittest 自动测试和分支覆盖率门槛
- Ruff 代码检查与统一格式检查
- mypy 渐进式类型检查和 compileall 语法编译检查
- pip 依赖一致性检查
- 本地与 GitHub Actions 共用同一套质量脚本
- GitHub Actions 在 Python 3.12 环境执行质量门槛

## 尚未实现

- v0.10.0 的 HTTP SSE 流式聊天、断线取消和慢客户端处理
- RAG 知识检索
- 多智能体协作
- 管理员报告查询
- 风险个案工作流
- Excel 台账导出
- 邮件或日志预警
- 管理后台界面

## 安装

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

## 本地配置

复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

在私有 `.env` 中设置学生和管理员密码。密码必须至少 12 位，`.env` 不能提交到
Git。仓库中的 `.env.example` 始终保持 `AI_PROVIDER=mock`，因此新环境默认不依赖
Ollama、GGUF 或公网服务。

## 运行

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## 接口

公开健康检查：

```text
GET /actuator/health
```

当前用户与管理员权限检查：

```text
GET /api/users/me
GET /api/admin/ping
```

创建聊天会话：

```text
POST /api/chat/sessions
```

只保存用户消息并执行后台风险硬规则：

```text
POST /api/chat/sessions/{session_public_id}/messages
```

保存用户消息、调用 AI Provider 并返回完整助手回复：

```text
POST /api/chat/sessions/{session_public_id}/turns
```

查询聊天历史：

```text
GET /api/chat/sessions/{session_public_id}/messages
```

管理员 AI 与本地模型状态：

```text
GET /api/admin/ai/status
GET /api/admin/ai/status?run_inference=true
```

第二种形式会显式执行一次不包含用户数据的最小 Ollama 推理；默认状态请求不会执行
推理。当前没有公开的风险评估接口或报告查询接口。

### 真实 `/turns` 调用示例

先确保应用正在 `127.0.0.1:8000` 运行，并且私有 `.env` 已配置学生账户密码。
下面使用 `Get-Credential` 在交互窗口中读取密码，不把真实密码写进命令、README 或
Shell 历史。`AllowUnencryptedAuthentication` 只可用于这里的本机回环 HTTP；部署到
其他机器时必须改用 HTTPS。

```powershell
$credential = Get-Credential -UserName "student" -Message "输入私有 .env 中的学生密码"
$auth = @{
    Authentication = "Basic"
    Credential = $credential
    AllowUnencryptedAuthentication = $true
}

$session = Invoke-RestMethod @auth `
    -Method Post `
    -Uri "http://127.0.0.1:8000/api/chat/sessions" `
    -ContentType "application/json; charset=utf-8" `
    -Body (@{ title = "v0.9 本地模型联调" } | ConvertTo-Json)

$turn = Invoke-RestMethod @auth `
    -Method Post `
    -Uri "http://127.0.0.1:8000/api/chat/sessions/$($session.public_id)/turns" `
    -ContentType "application/json; charset=utf-8" `
    -Body (@{ content = "最近学习任务很多，我该怎样安排今天的计划？" } | ConvertTo-Json)

$turn | ConvertTo-Json -Depth 5
```

成功响应只包含公开会话字段和完整的 `assistant_message`：

```json
{
  "session": {
    "public_id": "会话 UUID",
    "title": "v0.9 本地模型联调",
    "created_at": "时间戳",
    "updated_at": "时间戳"
  },
  "assistant_message": {
    "role": "assistant",
    "content": "模型生成或安全策略选出的完整回复",
    "created_at": "时间戳"
  }
}
```

风险等级、命中信号、内部意图、分析 JSON、报告摘要、Prompt 和 Provider 错误均不会
出现在学生响应中。

## v0.9.0 单轮处理逻辑

`/turns` 的处理顺序不是“收到消息后直接问模型”，而是一个安全编排流程：

1. 校验当前用户确实拥有目标会话。
2. 事务 A 保存用户原文，并把硬规则产生的 MEDIUM/HIGH 报告一起提交。
3. 如果硬规则已经是 HIGH，零次调用 Provider，直接进入固定安全回复。
4. 其他情况先从原文生成脱敏副本，再用 `analysis_v1` Prompt 调用一次 Provider。
5. 严格解析模型返回的 JSON analysis，并把模型建议与硬规则做单调合并。
6. 如果模型提高了风险，事务 B 先幂等升级后台报告，再继续生成回复。
7. 最终 HIGH 直接使用固定安全回复；LOW/MEDIUM 才至多调用一次 reply。
8. 事务 C 只保存最终完整的助手消息，不把半条回复写进数据库。

三段短事务之间是 Provider 网络调用，因此数据库事务不会跨越模型等待。事务 A 在
首次模型调用前已经提交，所以 LOW 轮次即使最终收到 503，用户原文仍可在聊天历史中
看到。事务 B 则保证模型发现的风险升级不会因为后续回复生成失败而丢失。

不同分支的行为如下：

| 场景 | Provider 调用 | 学生可见结果 |
| --- | ---: | --- |
| 硬规则 HIGH | 0 | 固定 HIGH 安全回复 |
| analysis 将风险提高到 HIGH | 1 | 固定 HIGH 安全回复 |
| LOW/MEDIUM 正常完成 | 最多 2 | 一次 analysis 后返回完整 reply |
| MEDIUM 的 analysis 或 reply 故障 | 1～2 | 固定支持性降级回复 |
| LOW 的 analysis 或 reply 故障 | 1～2 | 503 `AI_SERVICE_UNAVAILABLE`，用户消息保留 |

## 隐私数据流与公开 DTO 边界

用户原文只写入 MindBridge 自己的业务数据库，以便会话所有者查询历史。准备调用
Provider 时，应用复制原文并在副本上替换当前规则能够识别的手机号、邮箱、身份证号
和带标签学号；发送给 Provider 和放入 Prompt 的是脱敏副本，脱敏过程不会覆盖数据库
中的原文。

```text
用户输入
  ├─ 原文 ──> MindBridge 数据库
  └─ 脱敏副本 ──> analysis/reply Prompt ──> AI Provider
```

这是一条明确的数据边界，但不是“已经识别所有个人信息”的承诺。姓名、地址、特殊
格式账号和上下文中可推断的身份仍可能超出当前规则能力，因此接入任何远程 Provider
前仍需单独完成隐私、合规与数据保留评估。

模型的 analysis 只用于内部意图路由与安全分流。学生 DTO 使用白名单字段构造，不会
把风险等级、心理报告、模型依据或内部错误序列化出去；会话所有者仍能通过历史接口
读取自己曾提交的原文。

## 测试与质量门槛

只运行全部单元测试：

```powershell
python -m unittest discover -s tests -v
```

提交代码前运行完整质量检查：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check.ps1
```

脚本依次执行：

1. `pip check`，检查已安装依赖是否冲突。
2. `ruff check`，检查导入、语法和常见静态问题。
3. `ruff format --check`，确认代码已统一格式化。
4. `mypy app`，检查应用代码中的类型使用。
5. `compileall`，确认应用与测试文件可以编译。
6. 在 coverage 中运行全部 unittest。
7. 输出分支覆盖率，并执行 90% 的最低门槛。

任一步失败，脚本都会停止并返回非零退出码。GitHub Actions 在 Python 3.12 环境中
调用同一个脚本，避免本地检查与 CI 使用不同标准。自动测试使用 Mock/Fake 或
`httpx.MockTransport`，不要求 Ollama 在线，也不会读取、复制或加载数 GB GGUF。

当前 v0.9.0 质量基线：

- 179 个自动化测试全部通过
- 综合分支覆盖率为 93%，高于 90% 门槛
- 74 个 Python 文件通过 Ruff 格式检查
- 43 个应用源文件通过 mypy

## 当前 AI Provider 边界

v0.9.0 支持 `mock`、`ollama` 和 `openai_compatible` 三种显式 Provider。未知名称会
拒绝启动，绝不静默回退 Mock。`/turns` 已经真正调用所选 Provider；`/messages`
仍然只是保存用户消息并执行硬规则，不生成助手回复。

应用在 lifespan 中创建一个共享 `httpx.AsyncClient`，所有真实 Provider 只借用这个
客户端，应用退出时统一关闭连接池。HTTPX 的 connect/read/write/pool 分阶段超时与
`asyncio.timeout` 的整次调用总时限分别配置。当前 Provider 已具备流式适配能力，但
把增量安全地暴露为 HTTP SSE、处理客户端断线和取消传播属于 v0.10.0。

OpenAI-compatible 适配器采用 Chat Completions 形状，因为它是最终版和多种兼容服务
的共同协议。本学习版没有默认远程模型；只有显式配置 base URL、`SecretStr` API key
和 model 后才能选择该 Provider。接入远程服务前必须重新评估脱敏规则与数据合规。

AI 的 system 消息只属于模型上下文，不会写入当前只允许 user 和 assistant 的聊天
消息表。Provider 状态、内部 Prompt、模型分析和底层异常也不会通过学生接口外显。

## 本地模型与 Ollama readiness

根目录 `models` 保存 AI 模型资产，和保存 SQLAlchemy 代码的 `app/models` 不是同一
个目录。仓库只提交说明与 `Modelfile`；GGUF、safetensors、bin、pt、pth 和模型压缩包
均被 `.gitignore` 忽略。其他人克隆仓库后不会自动得到模型权重。

v0.9.0 已在本机完成真实部署验收：

- Ollama 版本：0.31.1
- 注册名：`mindbridge-qwen2.5-7b-ft:latest`
- Ollama 元数据：Qwen2、7.6B、Q4_K_M
- `asset_status=READY`
- `server_status=READY`
- `registration_status=REGISTERED`
- `inference_status=READY`
- 真实非流式 `/turns` 调用链可用

四层状态必须分别理解，不能把“GGUF 文件存在”误认为“模型已经可用”：

1. `asset_status`：GGUF 与 Modelfile 是否同时存在，`FROM` 是否匹配。
2. `server_status`：Ollama `/api/tags` 是否可达并返回有效数据。
3. `registration_status`：目标模型是否已注册到当前 Ollama 模型仓库。
4. `inference_status`：只有显式请求时才执行固定、无用户数据的最小推理。

检查与注册脚本不会安装或启动 Ollama，也不会下载、量化或提交 GGUF。检查脚本不会
复制模型；注册脚本会显式调用 `ollama create`，由 Ollama 把 GGUF 内容摄取到它自己
的模型仓库。这不会在项目目录内再生成一份受 Git 管理的模型文件，但 Ollama 仓库会
占用相应磁盘空间：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check_local_model.ps1 -VerifyChecksum
powershell -ExecutionPolicy Bypass -File .\scripts\register_local_model.ps1 -VerifyChecksum -WhatIf
powershell -ExecutionPolicy Bypass -File .\scripts\register_local_model.ps1 -VerifyChecksum -Confirm
powershell -ExecutionPolicy Bypass -File .\scripts\check_local_model.ps1 -RunInference
```

在全新环境第一次注册之前，第一条检查命令即使输出
`checksum_status=READY`，仍会同时输出 `registration_status=UNREGISTERED` 并以退出码
1 结束；这是“资产正确、但还没有注册”的预期状态，不代表 GGUF 损坏。确认资产和
校验和为 READY 后继续预览、执行注册，注册完成后再用最后一条命令验收四层状态。

仓库的 `.env.example` 仍然保持安全默认值：

```env
AI_PROVIDER=mock
```

只有四层 readiness 都符合预期后，才在不提交 Git 的私有 `.env` 中切换：

```env
APP_VERSION=0.9.0
AI_PROVIDER=ollama
AI_TEMPERATURE=0.35
AI_READ_TIMEOUT_SECONDS=120.0
AI_TOTAL_TIMEOUT_SECONDS=180.0
```

### Windows 中文用户路径排障

本机使用 Ollama 0.31.1 验收时，发现默认模型仓库位于 Windows 中文用户名路径下会
触发路径兼容缺陷，可能表现为注册后不可见、模型 blob 打不开或推理失败。如果 GGUF
的 SHA-256 校验已经通过，这不是 GGUF 损坏，也不需要重新下载或做耗时的重新量化。

把 Ollama 自己的模型仓库迁到纯英文绝对路径：

```powershell
New-Item -ItemType Directory -Force -Path C:\OllamaModels
[Environment]::SetEnvironmentVariable(
    "OLLAMA_MODELS",
    "C:\OllamaModels",
    "User"
)
```

设置用户级环境变量后，必须从系统托盘完全退出 Ollama，并确认任务管理器中原有
Ollama 进程已经结束，再重新启动 Ollama。只关闭终端、只新开一个 PowerShell，或者
只重启 FastAPI 都不能让已经运行的 Ollama 服务读取新变量。

新模型仓库最初可能为空，这是预期行为；它不会自动搬运旧仓库的注册记录。Ollama
完全重启后，重新执行注册脚本和 `-RunInference` 检查即可。项目目录里的原始 GGUF
不需要移动，也不要重新量化。

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

MindBridge Learn 目前仍是从零学习和复现阶段。`data` 目录中的用户、会话、消息和
报告都被视为可丢弃的本地开发数据，不应存放唯一一份重要资料。

应用通过 SQLAlchemy 的 `Base.metadata.create_all()` 从空数据库创建当前全部数据表。
它适合自动测试和当前本地学习环境，但必须理解它的能力边界：

- 它可以在空数据库中创建表，也可以在结构已经一致时重复执行。
- 它不会把旧表可靠地升级成新的 ORM 结构。
- 它不能代替数据库迁移工具完成新增字段、修改约束、数据转换或回滚。
- 当前项目不支持保留旧 SQLite 数据进行无损跨版本 Schema 升级。
- 如果以后开始保存不可丢弃的真实数据，必须先设计版本化迁移、备份和恢复方案。

应用启动、测试脚本和 CI 都不会自动删除本地数据库。Schema 变化时，需要由开发者
本人确认数据可以丢弃，然后显式执行安全重建。

### 手工安全重建 SQLite

1. 停止正在运行的 FastAPI、测试进程和可能占用数据库的 Python 控制台。
2. 确认数据确实可以丢弃。如需临时保留同一 Schema 下的副本，可先执行：

```powershell
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
Copy-Item -LiteralPath .\data\mindbridge.db -Destination ".\data\mindbridge-$timestamp.backup.db"
```

3. 预览受保护的重置操作，不删除文件：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\reset_dev_database.ps1 -WhatIf
```

4. 核对脚本显示的绝对路径，再由本人确认删除：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\reset_dev_database.ps1 -Confirm
```

重置脚本只允许处理 `development` 环境中、项目 `data` 目录内的文件型 SQLite `.db`
数据库。它拒绝内存数据库、其他数据库类型和项目目录外的路径；脚本只删除经过校验
的数据库文件，不会启动应用，也不会删除 `.env`、模型或上传文件。

5. 再次启动应用，让 `create_all()` 从空数据库创建最新结构。
6. 重新运行完整质量检查。需要的本地初始账户会根据 `.env` 配置重新创建。

## 风险模块边界

当前风险模块由“确定性硬规则 + 模型安全建议”共同组成，而不是只依赖其中一方。

硬规则先运行，并对明确关键词提供稳定、可测试的最低安全等级。模型 analysis 可以
发现词表没有覆盖的语境，但其建议只允许提高风险；它不能把硬规则 MEDIUM 降为 LOW，
也不能把硬规则 HIGH 降级。模型 JSON 无效时，不使用这次模型建议，硬规则结果仍然
保留。

这套机制只用于安全分流和后台支持基础，仍可能误报或漏报。因此：

- 命中不等于心理或医学诊断
- LOW 不代表一定不存在风险
- 不应使用结果给学生贴标签
- 不应仅依赖该模块做真实危机决策
- 当前版本不构成危机干预或紧急救助系统
- 当前版本不应作为真实心理服务直接部署

## 安全提醒

- HTTP Basic 只适合当前本地学习阶段；部署到公网必须使用 HTTPS。
- 客户端只能创建用户消息，不能自行指定 assistant 角色。
- 用户只能访问自己的聊天会话，并向自己的会话发送消息。
- 项目不会自动发送邮件、通知老师或联系紧急服务。
- 固定 HIGH 回复提供的是现实支持指引，不代表系统已经完成真实救援。

## 下一阶段

v0.10.0 将在现有 Provider 流式契约和 v0.9.0 安全单轮编排之上实现 HTTP SSE，重点
处理增量输出、断线取消、慢客户端、错误事件与流结束语义；RAG 和多智能体继续放在
后续阶段。
