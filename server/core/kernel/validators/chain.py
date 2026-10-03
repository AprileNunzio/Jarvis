from typing import Sequence

from server.core.kernel.application.ports import NodeValidator
from server.core.kernel.domain.node import NodeSpec
from server.core.kernel.domain.outcome import NodeResult, Verdict


class ValidatorChain:
    def __init__(self, validators: Sequence[NodeValidator]) -> None:
        self._validators = tuple(validators)

    async def judge(self, node: NodeSpec, result: NodeResult) -> Verdict:
        for validator in self._validators:
            verdict = await validator.judge(node, result)
            if not verdict.accepted:
                return verdict
        return Verdict.accept()
