"""Extension boundary for phase 2; dataset replay is intentionally not implemented."""
from typing import Protocol,TypeVar
from ..schemas import TestConfig
Config=TypeVar('Config',contravariant=True)
class TrafficGenerator(Protocol[Config]):
    async def start(self, config: Config, profile: dict | None = None) -> dict: ...
    async def stop(self, experiment_id: int) -> None: ...
from .iperf_runner import IperfRunner as IperfTrafficGenerator
from .video_sender import VideoTrafficGenerator
# IperfTrafficGenerator and VideoTrafficGenerator satisfy this protocol. Dataset implementations must preserve provenance.
