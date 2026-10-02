from typing import Any, Dict, Optional

class JarvisBaseException(Exception):
    def __init__(self, message: str, code: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}

class UnauthorizedException(JarvisBaseException):
    def __init__(self, message: str = "Access denied by Zero-Trust policy", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, code="UNAUTHORIZED", details=details)

class BiometricVerificationFailedException(JarvisBaseException):
    def __init__(self, message: str = "Speaker biometric verification rejected", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, code="BIOMETRIC_REJECTED", details=details)

class EntityNotFoundException(JarvisBaseException):
    def __init__(self, entity_type: str, entity_id: str):
        super().__init__(
            message=f"Entity {entity_type} with ID '{entity_id}' not found",
            code="ENTITY_NOT_FOUND",
            details={"entity_type": entity_type, "entity_id": entity_id}
        )

class AgentExecutionException(JarvisBaseException):
    def __init__(self, agent_name: str, message: str, details: Optional[Dict[str, Any]] = None):
        merged_details = {"agent_name": agent_name}
        if details:
            merged_details.update(details)
        super().__init__(message=message, code="AGENT_EXECUTION_FAILURE", details=merged_details)

class SandboxSecurityException(JarvisBaseException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, code="SANDBOX_VIOLATION", details=details)
