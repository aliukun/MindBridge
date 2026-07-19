# MindBridge 微调模型资产

这个目录只提交说明和 `Modelfile`，不提交模型权重。

预期由开发者本人迁移的文件：

```text
mindbridge-qwen2.5-7b-ft-q4_k_m.gguf
```

已知文件信息：

- 大小：4,683,073,536 bytes
- SHA-256：`D992DEE2688614EBD24200ED85EF7CA6135DA22C961F8F78C307FD576D8F2C8D`
- Ollama 注册名：`mindbridge-qwen2.5-7b-ft:latest`

## 安全迁移顺序

1. 保持 `.env` 中 `AI_PROVIDER=mock`。
2. 把 GGUF 文件复制到本目录。
3. 执行 `git status --ignored`，确认 GGUF 显示为 ignored。
4. 执行 `scripts/check_local_model.ps1 -VerifyChecksum`。首次注册前脚本会因为模型仍是
   `UNREGISTERED` 而返回退出码 1；只要 `asset_status=READY` 和
   `checksum_status=READY`，这就是预期状态，不代表 GGUF 损坏。
5. 执行 `scripts/register_local_model.ps1 -WhatIf` 预览。
6. 由本人确认后执行注册脚本。
7. 再执行检查脚本，必要时显式加 `-RunInference`。
8. 四层 readiness 正确后，才把 `AI_PROVIDER` 改为 `ollama`。

应用通过 Ollama HTTP API 调用模型，Python 不直接加载这个 4.68 GB GGUF。
脚本不会安装或启动 Ollama，也不会下载或提交模型文件。检查脚本不会复制模型；
注册脚本会调用 `ollama create`，因此 Ollama 会把 GGUF 内容摄取到自己的模型仓库并
占用相应磁盘空间，但不会在项目目录内创建一份新的受 Git 管理的权重文件。

## Windows 中文用户目录排障

Ollama 0.31.1 在 Windows 上可能把包含中文的模型存储路径错误传递给其
`llama-quantize` 子进程。典型现象是 SHA-256 校验通过，但 `ollama create`
仍以 `failed to validate GGUF with llama-quantize` 失败，并在日志中把用户名
显示为乱码。这不是 GGUF 损坏，也不能通过修改 `Modelfile` 参数解决。

为 Ollama 使用纯 ASCII 模型目录：

```powershell
New-Item -ItemType Directory -Force -Path C:\OllamaModels
[Environment]::SetEnvironmentVariable(
    "OLLAMA_MODELS",
    "C:\OllamaModels",
    "User"
)
```

设置后必须彻底退出 Ollama 托盘程序及旧的 `ollama serve` 进程，再重新登录
Windows 或从继承新环境变量的终端重新启动 Ollama。确认 `/api/tags` 能看到
目标模型后，再执行 `check_local_model.ps1 -RunInference`。不要因为这个路径
问题重新量化 4.68 GB GGUF，也不要把模型权重移入仓库。
