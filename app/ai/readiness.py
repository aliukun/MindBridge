from dataclasses import dataclass
from enum import StrEnum


class ModelAssetState(StrEnum):
    """本地模型资产的静态完整性。"""

    MISSING = "MISSING"
    INCOMPLETE = "INCOMPLETE"
    INVALID = "INVALID"
    READY = "READY"


class OllamaServerState(StrEnum):
    """Ollama HTTP 服务是否可达。"""

    UNAVAILABLE = "UNAVAILABLE"
    READY = "READY"


class ModelRegistrationState(StrEnum):
    """目标模型是否已注册到 Ollama。"""

    NOT_CHECKED = "NOT_CHECKED"
    UNREGISTERED = "UNREGISTERED"
    REGISTERED = "REGISTERED"


class ModelInferenceState(StrEnum):
    """显式最小推理的结果。"""

    NOT_CHECKED = "NOT_CHECKED"
    FAILED = "FAILED"
    READY = "READY"


@dataclass(frozen=True)
class ModelAssetStatus:
    state: ModelAssetState
    detail: str
    relative_directory: str
    model_file: str
    modelfile: str


@dataclass(frozen=True)
class OllamaServerStatus:
    state: OllamaServerState
    detail: str


@dataclass(frozen=True)
class ModelRegistrationStatus:
    state: ModelRegistrationState
    detail: str


@dataclass(frozen=True)
class ModelInferenceStatus:
    state: ModelInferenceState
    detail: str


@dataclass(frozen=True)
class LocalModelReadiness:
    ollama_model: str
    asset_status: ModelAssetStatus
    server_status: OllamaServerStatus
    registration_status: ModelRegistrationStatus
    inference_status: ModelInferenceStatus
