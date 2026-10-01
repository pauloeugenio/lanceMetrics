"""FFmpeg arguments; no shell or user supplied command fragments."""
from .video_tools import tool_path

class FFmpegCommandBuilder:
    @staticmethod
    def sender(config,path,local_port,rtcp_port=None):
        args=[tool_path('ffmpeg') or 'ffmpeg','-hide_banner','-nostdin','-loglevel','warning','-progress','pipe:1','-stats_period','0.5']
        if config.playback=='realtime':args+=['-re']
        args+=['-protocol_whitelist','file,pipe','-i',str(path),'-map','0:v:0','-map','0:a?']
        if config.encoding_mode=='preserve':args+=['-c','copy']
        else:
            bitrate=str(round(config.target_mbps*1e6))
            args+=['-c:v','libx264','-preset',config.preset,'-b:v',bitrate,'-maxrate',bitrate,'-bufsize',bitrate,'-pix_fmt','yuv420p','-c:a','aac']
            if config.low_latency:args+=['-tune','zerolatency']
        # Frequent TS headers help receivers join streams; RTP uses standardized MPEG-TS payload type 33.
        args+=['-mpegts_flags','+resend_headers','-muxdelay','0','-muxpreload','0','-f','rtp_mpegts' if config.transport=='rtp' else 'mpegts',(f'rtp://127.0.0.1:{local_port}?pkt_size=1316&rtcpport={rtcp_port or local_port+1}' if config.transport=='rtp' else f'udp://127.0.0.1:{local_port}?pkt_size=1316')]
        return args

    @staticmethod
    def receiver(local_port):
        return [tool_path('ffmpeg') or 'ffmpeg','-hide_banner','-nostdin','-loglevel','warning','-fflags','+discardcorrupt',
                '-analyzeduration','100000','-probesize','32768','-f','mpegts','-i',
                f'udp://127.0.0.1:{local_port}?fifo_size=8192&overrun_nonfatal=1',
                '-an','-vf','fps=8,scale=640:360:force_original_aspect_ratio=decrease','-c:v','mjpeg','-q:v','5','-threads','1','-f','image2pipe','pipe:1']
