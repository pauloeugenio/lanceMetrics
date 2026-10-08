"""Bounded, file-only ffprobe metadata and packet-window analysis."""
import asyncio, json, math, shutil

from .video_tools import tool_path,tool_env

class VideoProbeService:
    @staticmethod
    def parse(data):
        def numeric(v):
            try:
                n=float(v)
                return n if math.isfinite(n) and n>=0 else None
            except (TypeError,ValueError):return None
        fmt=data.get('format',{}); streams=data.get('streams',[])
        video=next((s for s in streams if s.get('codec_type')=='video'),None)
        if not video:raise ValueError('No decodable video stream found')
        audio=next((s for s in streams if s.get('codec_type')=='audio'),{})
        fps=None
        for key in ('avg_frame_rate','r_frame_rate'):
            try:
                numerator,denominator=video.get(key,'0/0').split('/')
                fps=float(numerator)/float(denominator)
                if not math.isfinite(fps) or fps<=0:fps=None
                if fps:break
            except (ValueError,ZeroDivisionError):pass
        return {'duration':numeric(fmt.get('duration',video.get('duration'))),'size':numeric(fmt.get('size')),
                'container':fmt.get('format_name'),'video_codec':video.get('codec_name'),'audio_codec':audio.get('codec_name'),
                'width':video.get('width'),'height':video.get('height'),'fps':fps,
                'source_bps':numeric(fmt.get('bit_rate')),'stream_bps':numeric(video.get('bit_rate'))}

    async def probe(self,path):
        if not tool_path('ffprobe'):raise ValueError('ffprobe is missing. Install FFmpeg and run Diagnostics.')
        p=await asyncio.create_subprocess_exec(tool_path('ffprobe'),'-v','error','-protocol_whitelist','file,pipe','-show_format','-show_streams','-of','json',str(path),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,env=tool_env('ffprobe'))
        try:
            async def read_limited(stream,limit):
                chunks=[];size=0
                while chunk:=await stream.read(8192):
                    size+=len(chunk)
                    if size>limit:raise ValueError('Probe output exceeds metadata limit')
                    chunks.append(chunk)
                return b''.join(chunks)
            output,error=await asyncio.wait_for(asyncio.gather(read_limited(p.stdout,2*1024*1024),read_limited(p.stderr,64*1024)),30)
            await p.wait()
            if p.returncode:raise ValueError('Invalid video: '+error.decode(errors='replace')[:500])
            if len(output)>2*1024*1024:raise ValueError('Probe metadata exceeds limit')
            return self.parse(json.loads(output))
        finally:
            if p.returncode is None:p.kill();await p.wait()

    async def temporal(self,path,window,duration):
        if not tool_path('ffprobe'):raise ValueError('ffprobe is missing')
        # Packet payload sizes from ALL original streams; excludes container overhead.
        p=await asyncio.create_subprocess_exec(tool_path('ffprobe'),'-v','error','-protocol_whitelist','file,pipe','-show_packets','-show_entries','packet=pts_time,dts_time,size','-of','compact=p=0:nk=0',str(path),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL,env=tool_env('ffprobe'))
        bins={};minimum=None
        try:
            async def read_packets():
                nonlocal minimum
                async for line in p.stdout:
                    parts=dict(item.split('=',1) for item in line.decode(errors='replace').strip().split('|') if '=' in item)
                    try:
                        t=float(parts.get('pts_time',parts.get('dts_time','nan')));size=int(parts['size'])
                        if not math.isfinite(t) or size<0:continue
                        if minimum is None:minimum=t
                        index=max(0,int((t-minimum)//window));bins[index]=bins.get(index,0)+size
                        if len(bins)>100000:raise RuntimeError('Temporal analysis exceeds 100000 windows')
                    except (ValueError,KeyError):continue
                await p.wait()
            await asyncio.wait_for(read_packets(),600)
            if p.returncode:raise ValueError('ffprobe packet analysis failed')
            return [{'elapsed_time':i*window,'seconds':min(window,max(.001,duration-i*window)) if duration else window,
                     'bytes':size,'source_bps':size*8/(min(window,max(.001,duration-i*window)) if duration else window),
                     'metric_source':'ffprobe_original_packet_payload'} for i,size in sorted(bins.items())]
        finally:
            if p.returncode is None:p.kill();await p.wait()
