"""FFmpeg arguments; no shell or user supplied command fragments."""
from .video_tools import tool_path

class FFmpegCommandBuilder:
    @staticmethod
    def sender(config,path,local_port,rtcp_port=None):
        args=[tool_path('ffmpeg') or 'ffmpeg','-hide_banner','-nostdin','-loglevel','warning','-progress','pipe:1','-stats_period','0.5']
        if config.playback=='realtime':args+=['-re']
        # AVI often supplies DTS without PTS. Generate missing presentation
        # timestamps before remuxing, as MPEG-TS requires both on its first packet.
        args+=['-fflags','+genpts','-protocol_whitelist','file,pipe','-i',str(path),'-map','0:v:0']
        if config.include_audio:args+=['-map','0:a?']
        else:args+=['-an']
        if config.encoding_mode=='preserve':args+=['-c','copy']
        else:
            bitrate=str(round(config.target_mbps*1e6))
            args+=['-c:v','libx264','-preset',config.preset,'-b:v',bitrate,'-maxrate',bitrate,'-bufsize',bitrate,'-pix_fmt','yuv420p','-c:a','aac']
            if config.resolution!='source':
                width,height=config.resolution.split('x')
                args+=['-vf',f'scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2']
            if config.output_fps is not None:args+=['-r',str(config.output_fps)]
            if config.keyframe_frames is not None:args+=['-g',str(config.keyframe_frames),'-keyint_min',str(config.keyframe_frames),'-sc_threshold','0']
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
