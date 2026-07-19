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
4. 执行 `scripts/check_local_model.ps1 -VerifyChecksum`。
5. 执行 `scripts/register_local_model.ps1 -WhatIf` 预览。
6. 由本人确认后执行注册脚本。
7. 再执行检查脚本，必要时显式加 `-RunInference`。
8. 四层 readiness 正确后，才把 `AI_PROVIDER` 改为 `ollama`。

应用通过 Ollama HTTP API 调用模型，Python 不直接加载这个 4.68 GB GGUF。
脚本不会安装或启动 Ollama，不会下载、复制或提交模型文件。
