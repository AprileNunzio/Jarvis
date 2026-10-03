from typing import Dict

from server.core.kernel.application.ports import NodeValidator
from server.core.kernel.domain.node import NodeSpec
from server.core.kernel.domain.outcome import NodeResult, Verdict

DEFAULT_VALIDATOR_ID = "default"
SUCCESS_STATUS = "SUCCESS"


class DefaultNodeValidator:
    async def judge(self, node: NodeSpec, result: NodeResult) -> Verdict:
        status = result.output.get("status", SUCCESS_STATUS)
        if status != SUCCESS_STATUS:
            return Verdict.reject("agent_status", f"agent reported status {status}", status=status)
        if not result.speech.strip() and not result.output.get("data"):
            return Verdict.reject("empty_result", "node produced no content")
        return Verdict.accept()


class ValidatorCatalog:
    def __init__(self) -> None:
        self._validators: Dict[str, NodeValidator] = {DEFAULT_VALIDATOR_ID: DefaultNodeValidator()}

    def register(self, validator_id: str, validator: NodeValidator) -> None:
        self._validators[validator_id] = validator

    def resolve(self, validator_id: str) -> NodeValidator:
        try:
            return self._validators[validator_id]
        except KeyError:
            raise LookupError(f"no validator registered for {validator_id!r}") from None
