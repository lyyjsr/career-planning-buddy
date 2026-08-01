"""Stable internal errors normalized by the Agent Run executor."""


class AgentError(Exception):
    code = "AGENT_ERROR"


class RunCancelledError(AgentError):
    code = "RUN_CANCELLED"


class AgentDeadlineExceededError(AgentError):
    code = "AGENT_DEADLINE_EXCEEDED"


class BudgetExceededError(AgentError):
    code = "AGENT_BUDGET_EXCEEDED"


class ProviderTimeoutError(AgentError):
    code = "PROVIDER_TIMEOUT"


class ProviderConfigurationError(AgentError):
    code = "PROVIDER_CONFIGURATION_INVALID"


class ProviderAuthenticationError(AgentError):
    code = "PROVIDER_AUTHENTICATION_FAILED"


class ProviderRateLimitError(AgentError):
    code = "PROVIDER_RATE_LIMITED"


class ProviderUnavailableError(AgentError):
    code = "PROVIDER_UNAVAILABLE"


class StructuredOutputError(AgentError):
    code = "STRUCTURED_OUTPUT_INVALID"


class ToolValidationError(AgentError):
    code = "TOOL_ARGUMENT_INVALID"


class ToolExecutionError(AgentError):
    code = "TOOL_EXECUTION_FAILED"


class PersistTransactionError(AgentError):
    code = "PERSIST_TRANSACTION_FAILED"
