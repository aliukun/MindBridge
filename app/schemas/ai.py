from pydantic import BaseModel, ConfigDict

from app.ai.contracts import ProviderStatus
from app.ai.readiness import (
    ModelAssetState,
    ModelInferenceState,
    ModelRegistrationState,
    OllamaServerState,
)


class ModelAssetStatusPublic(BaseModel):
    state: ModelAssetState
    detail: str
    relative_directory: str
    model_file: str
    modelfile: str

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
    )


class OllamaServerStatusPublic(BaseModel):
    state: OllamaServerState
    detail: str

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
    )


class ModelRegistrationStatusPublic(BaseModel):
    state: ModelRegistrationState
    detail: str

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
    )


class ModelInferenceStatusPublic(BaseModel):
    state: ModelInferenceState
    detail: str

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
    )


class LocalModelReadinessPublic(BaseModel):
    ollama_model: str
    asset_status: ModelAssetStatusPublic
    server_status: OllamaServerStatusPublic
    registration_status: ModelRegistrationStatusPublic
    inference_status: ModelInferenceStatusPublic

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
    )


class AiStatusPublic(BaseModel):
    active_provider: ProviderStatus
    local_model: LocalModelReadinessPublic

    model_config = ConfigDict(
        extra="forbid",
    )
