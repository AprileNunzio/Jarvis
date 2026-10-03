class SandboxError(Exception):
    pass


class SpecError(SandboxError, ValueError):
    pass


class SandboxUnavailableError(SandboxError):
    pass


class SandboxRejectedError(SandboxError):
    pass
