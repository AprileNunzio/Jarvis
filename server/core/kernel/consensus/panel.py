import asyncio
import logging
from typing import Sequence

from server.core.kernel.consensus.ballot import Ballot, Voter
from server.core.kernel.domain.dag import ExecutionDag
from server.core.kernel.domain.outcome import ConsensusVerdict

logger = logging.getLogger("jarvis.kernel.consensus")


class ConsensusPanel:
    def __init__(self, voters: Sequence[Voter], vote_timeout_seconds: float = 180.0) -> None:
        if not voters:
            raise ValueError("a consensus panel needs at least one voter")
        self._voters = tuple(voters)
        self._timeout = vote_timeout_seconds

    async def vote(self, dag: ExecutionDag) -> ConsensusVerdict:
        ballots = await asyncio.gather(*(self._ballot(v, dag) for v in self._voters))
        approvals = sum(1 for b in ballots if b.approve)
        vetoes = [b for v, b in zip(self._voters, ballots) if v.can_veto and not b.approve]
        majority = approvals * 2 > len(ballots)
        objections = tuple(f"{b.voter}: {b.reason}" for b in ballots if not b.approve)
        logger.info("consensus on %s: %d/%d approve, vetoes=%d", dag.fingerprint()[:12], approvals, len(ballots), len(vetoes))
        return ConsensusVerdict(approved=majority and not vetoes, objections=objections)

    async def _ballot(self, voter: Voter, dag: ExecutionDag) -> Ballot:
        try:
            return await asyncio.wait_for(voter.vote(dag), self._timeout)
        except asyncio.TimeoutError:
            return Ballot(voter.name, False, "no answer within the voting deadline")
        except Exception as exc:
            logger.warning("voter %s failed: %s", voter.name, exc.__class__.__name__)
            return Ballot(voter.name, False, f"voter unavailable ({exc.__class__.__name__})")
