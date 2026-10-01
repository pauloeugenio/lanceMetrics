from .video_tools import tool_path,tool_env
"""Latest-frame JPEG preview, bounded memory. This is not the network transport."""
import asyncio
from .video_command import FFmpegCommandBuilder

class VideoPreviewService:
    def __init__(self,manager):self.manager=manager;self.frames={};self.events={};self.stats={}
    async def start(self,key,local_port,folder):
        process=await self.manager.spawn(key,FFmpegCommandBuilder.receiver(local_port),{'type':'video_receiver'},env=tool_env())
        self.stats[key]={'frames':0,'status':'DECODING','pid':process.pid}
        async def stderr():
            with (folder/'ffmpeg_receiver.log').open('ab') as log:
                while chunk:=await process.stderr.read(8192):log.write(chunk)
        async def decode():
            buffer=bytearray()
            while chunk:=await process.stdout.read(16384):
                buffer.extend(chunk)
                while True:
                    begin=buffer.find(b'\xff\xd8');end=buffer.find(b'\xff\xd9',max(0,begin)+2)
                    if begin>=0 and end>begin:
                        self.frames[key]=bytes(buffer[begin:end+2]);del buffer[:end+2]
                        self.stats[key]['frames']+=1;self.stats[key]['status']='LIVE'
                        self.events.setdefault(key,asyncio.Event()).set()
                    else:break
                if len(buffer)>4*1024*1024:buffer.clear()
            self.stats[key]['status']='ENDED'
        tasks=[asyncio.create_task(stderr()),asyncio.create_task(decode())]
        return process,tasks
    async def stop(self,key,tasks):
        await self.manager.stop(key,grace_seconds=.5)
        await asyncio.gather(*tasks,return_exceptions=True)
        self.stats.get(key,{}).update(status='ENDED')
        self.frames.pop(key,None)
        self.events.setdefault(key,asyncio.Event()).set()
