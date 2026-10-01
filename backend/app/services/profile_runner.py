"""Session schedule; profiles never mutate bandwidth inside a running iperf flow."""
import asyncio
from ..schemas import TestConfig
class TrafficProfileRunner:
    transition_pause_seconds = 0.5
    @classmethod
    async def stages(cls,config:TestConfig,profile:dict|None):
        stages=profile['intervals'] if profile else [{'duration':config.duration,'bandwidth_mbps':config.bandwidth_mbps}]
        for index,stage in enumerate(stages):
            if index: await asyncio.sleep(cls.transition_pause_seconds)
            yield index,config.model_copy(update=stage)
