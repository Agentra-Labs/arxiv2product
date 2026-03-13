class AgenticaConnectionError(RuntimeError):
    """Raised when the Agentica backend cannot be reached."""


class AgentExecutionError(RuntimeError):
    """Raised when an Agentica invocation fails or times out."""
