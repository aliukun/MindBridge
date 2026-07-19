class AiError(Exception):
    """所有 MindBridge AI 层异常的共同父类。"""


class AiConfigurationError(AiError):
    """AI 配置无效，继续启动或调用没有意义。"""


class AiProviderError(AiError):
    """调用 AI Provider 期间发生的共同父异常。"""


class AiUnavailableError(AiProviderError):
    """Provider 当前不可连接或不可用。"""


class AiTimeoutError(AiProviderError):
    """Provider 调用超过允许时间。"""


class AiAuthenticationError(AiProviderError):
    """Provider 拒绝了认证信息。"""


class AiModelNotFoundError(AiProviderError):
    """Provider 中不存在指定模型。"""


class AiRateLimitError(AiProviderError):
    """Provider 拒绝了超过限额的请求。"""


class AiResponseError(AiProviderError):
    """Provider 返回了无法进一步分类的非成功 HTTP 状态。"""


class AiProtocolError(AiProviderError):
    """Provider 返回了不符合契约的数据。"""
