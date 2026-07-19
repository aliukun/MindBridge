from pathlib import Path

import httpx

from app.ai.contracts import (
    AiMessage,
    AiRequest,
    AiRequestOptions,
    AiRole,
)
from app.ai.errors import AiConfigurationError, AiProviderError
from app.ai.providers.ollama import (
    OllamaProvider,
    fetch_ollama_models,
)
from app.ai.readiness import (
    LocalModelReadiness,
    ModelAssetState,
    ModelAssetStatus,
    ModelInferenceState,
    ModelInferenceStatus,
    ModelRegistrationState,
    ModelRegistrationStatus,
    OllamaServerState,
    OllamaServerStatus,
)
from app.core.config import PROJECT_ROOT, Settings

MODELFILE_NAME = "Modelfile"
READINESS_PROMPT = "Reply with one short word: READY"


def _safe_model_directory(
    settings: Settings,
) -> tuple[Path, str]:
    models_root = (PROJECT_ROOT / "models").resolve()
    model_directory = (PROJECT_ROOT / settings.finetuned_model_dir).resolve()

    if not model_directory.is_relative_to(models_root):
        raise AiConfigurationError(
            "Fine-tuned model directory must stay inside the project models directory."
        ) from None

    relative_directory = model_directory.relative_to(PROJECT_ROOT).as_posix()

    return model_directory, relative_directory


def _modelfile_source(
    modelfile_path: Path,
) -> str | None:
    try:
        content = modelfile_path.read_text(
            encoding="utf-8",
        )
    except (OSError, UnicodeError):
        return None

    sources: list[str] = []

    for line in content.splitlines():
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            continue

        directive, separator, value = stripped.partition(" ")

        if directive.casefold() != "from":
            continue

        if not separator or not value.strip():
            return None

        sources.append(value.strip().strip('"').replace("\\", "/"))

    if len(sources) != 1:
        return None

    return sources[0]


def inspect_local_model_assets(
    settings: Settings,
) -> ModelAssetStatus:
    """只检查磁盘资产，不读取 GGUF 内容，也不访问网络。"""

    model_directory, relative_directory = _safe_model_directory(settings)
    model_path = model_directory / settings.finetuned_model_file
    modelfile_path = model_directory / MODELFILE_NAME

    model_exists = model_path.is_file()
    modelfile_exists = modelfile_path.is_file()

    common = {
        "relative_directory": relative_directory,
        "model_file": settings.finetuned_model_file,
        "modelfile": MODELFILE_NAME,
    }

    if not model_exists and not modelfile_exists:
        return ModelAssetStatus(
            state=ModelAssetState.MISSING,
            detail="The local GGUF file and Modelfile are missing.",
            **common,
        )

    if not model_exists or not modelfile_exists:
        return ModelAssetStatus(
            state=ModelAssetState.INCOMPLETE,
            detail="The local GGUF file and Modelfile are not both present.",
            **common,
        )

    source = _modelfile_source(modelfile_path)
    expected_source = f"./{settings.finetuned_model_file}"

    if source != expected_source:
        return ModelAssetStatus(
            state=ModelAssetState.INVALID,
            detail="The Modelfile FROM directive does not match the configured GGUF file.",
            **common,
        )

    return ModelAssetStatus(
        state=ModelAssetState.READY,
        detail="The local GGUF file and matching Modelfile are present.",
        **common,
    )


async def inspect_local_model_readiness(
    settings: Settings,
    *,
    http_client: httpx.AsyncClient,
    run_inference: bool = False,
) -> LocalModelReadiness:
    """分别检查资产、服务、注册和可选推理四个层次。"""

    asset_status = inspect_local_model_assets(settings)

    try:
        registered_models = await fetch_ollama_models(
            http_client,
            base_url=settings.ollama_base_url,
            total_timeout_seconds=(settings.ai_total_timeout_seconds),
        )
    except AiProviderError:
        return LocalModelReadiness(
            ollama_model=settings.ollama_model,
            asset_status=asset_status,
            server_status=OllamaServerStatus(
                state=OllamaServerState.UNAVAILABLE,
                detail="Ollama did not provide a valid model list.",
            ),
            registration_status=ModelRegistrationStatus(
                state=ModelRegistrationState.NOT_CHECKED,
                detail="Registration was not checked because Ollama is unavailable.",
            ),
            inference_status=ModelInferenceStatus(
                state=ModelInferenceState.NOT_CHECKED,
                detail="Inference was not checked because Ollama is unavailable.",
            ),
        )

    server_status = OllamaServerStatus(
        state=OllamaServerState.READY,
        detail="Ollama returned a valid model list.",
    )

    if settings.ollama_model not in registered_models:
        return LocalModelReadiness(
            ollama_model=settings.ollama_model,
            asset_status=asset_status,
            server_status=server_status,
            registration_status=ModelRegistrationStatus(
                state=ModelRegistrationState.UNREGISTERED,
                detail="The configured model is not registered in Ollama.",
            ),
            inference_status=ModelInferenceStatus(
                state=ModelInferenceState.NOT_CHECKED,
                detail="Inference requires a registered model.",
            ),
        )

    registration_status = ModelRegistrationStatus(
        state=ModelRegistrationState.REGISTERED,
        detail="The configured model is registered in Ollama.",
    )

    if not run_inference:
        return LocalModelReadiness(
            ollama_model=settings.ollama_model,
            asset_status=asset_status,
            server_status=server_status,
            registration_status=registration_status,
            inference_status=ModelInferenceStatus(
                state=ModelInferenceState.NOT_CHECKED,
                detail="Minimal inference was not requested.",
            ),
        )

    provider = OllamaProvider(
        http_client=http_client,
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        total_timeout_seconds=(settings.ai_total_timeout_seconds),
    )
    request = AiRequest(
        messages=(
            AiMessage(
                role=AiRole.USER,
                content=READINESS_PROMPT,
            ),
        ),
        options=AiRequestOptions(
            temperature=0.0,
            max_tokens=8,
        ),
    )

    try:
        await provider.complete(request)
    except AiProviderError:
        inference_status = ModelInferenceStatus(
            state=ModelInferenceState.FAILED,
            detail="The explicit minimal inference check failed.",
        )
    else:
        inference_status = ModelInferenceStatus(
            state=ModelInferenceState.READY,
            detail="The explicit minimal inference check succeeded.",
        )

    return LocalModelReadiness(
        ollama_model=settings.ollama_model,
        asset_status=asset_status,
        server_status=server_status,
        registration_status=registration_status,
        inference_status=inference_status,
    )
