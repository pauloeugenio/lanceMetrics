"""Extension boundary for phase 2; dataset replay is intentionally not implemented."""
from typing import Protocol
from ..schemas import TestConfig
class TrafficGenerator(Protocol):
    async def start(self, config: TestConfig, profile: dict | None = None) -> dict: ...
    async def stop(self, experiment_id: int) -> None: ...
from .iperf_runner import IperfRunner as IperfTrafficGenerator
# IperfTrafficGenerator satisfies this protocol. Dataset implementations must preserve provenance.
