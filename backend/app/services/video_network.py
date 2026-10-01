"""Application UDP payload counters, measured independently of FFmpeg/probe.
TX means successful sendto submission, not physical NIC delivery. RTP loss
is sequence-number based, jitter RFC3550 with 90 kHz MPEG-TS timestamp clock.
"""
import struct,time

class VideoNetworkMonitor:
    def __init__(self,role,transport):
        self.role=role;self.transport=transport;self.started=time.monotonic();self.last=self.started
        self.bytes=0;self.packets=0;self.last_bytes=0;self.last_packets=0
        self.first_seq=None;self.high_seq=None;self.received=set();self.ssrc=None
        self.jitter=0.;self.last_transit=None;self.last_timestamp=None;self.timestamp_cycles=0
        self.invalid_packets=0;self.duplicates=0;self.loss_complete=True;self.before_first=0;self.jitter_total=0.;self.jitter_samples=0

    def observe(self,data,arrival=None):
        self.bytes+=len(data);self.packets+=1
        if self.transport!='rtp':return data
        try:
            if len(data)<12 or data[0]>>6!=2 or data[1]&127!=33:raise ValueError('Expected RTP MPEG-TS payload type 33')
            offset=12+4*(data[0]&15)
            if data[0]&16:
                if len(data)<offset+4:raise ValueError('RTP extension')
                offset+=4+4*struct.unpack_from('!H',data,offset+2)[0]
            end=len(data)
            if data[0]&32:
                padding=data[-1]
                if not padding or padding>end-offset:raise ValueError('RTP padding')
                end-=padding
            if offset>=end:raise ValueError('RTP header')
            seq,stamp,ssrc=struct.unpack_from('!HII',data,2)
            if self.ssrc is None:self.ssrc=ssrc
            if ssrc!=self.ssrc:raise ValueError('SSRC changed: new session required')
            if self.high_seq is None:extended=seq;self.first_seq=seq;self.high_seq=seq
            else:
                extended=(self.high_seq&~65535)+seq
                if extended-self.high_seq>32768:extended-=65536
                elif self.high_seq-extended>32768:extended+=65536
                self.high_seq=max(self.high_seq,extended)
            if extended in self.received:self.duplicates+=1
            if self.loss_complete:
                if extended<self.first_seq and extended not in self.received:self.before_first+=1
                self.received.add(extended)
            # Bound state to maximum video duration/rate; exact counters remain practical for typical datasets.
            if len(self.received)>2000000:self.loss_complete=False;self.received.clear()
            ticks=int((arrival if arrival is not None else time.monotonic())*90000)&0xffffffff
            transit=(ticks-stamp)&0xffffffff
            if self.last_transit is not None:
                difference=((transit-self.last_transit+2147483648)&0xffffffff)-2147483648
                self.jitter+=(abs(difference)-self.jitter)/16
            self.last_transit=transit;self.jitter_total+=self.jitter;self.jitter_samples+=1
            return data[offset:end]
        except (ValueError,struct.error,IndexError):self.invalid_packets+=1;return None

    def loss(self):
        if self.transport!='rtp' or self.first_seq is None or self.invalid_packets or not self.loss_complete:return None,None,None
        expected=self.high_seq-self.first_seq+1
        lost=max(0,expected-(len(self.received)-self.before_first))
        return expected,lost,100*lost/expected if expected else None

    def sample(self,session_id,offset=0):
        end=time.monotonic();seconds=max(.000001,end-self.last);elapsed=end-self.started
        expected,lost,percent=self.loss()
        row={'timestamp':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
             'session_id':session_id,'elapsed_time':offset+elapsed,'seconds':seconds,'interval_start':offset+self.last-self.started,
             f'{"sender" if self.role=="sender" else "receiver"}_bps':(self.bytes-self.last_bytes)*8/seconds,
             f'{"sender" if self.role=="sender" else "receiver"}_bytes':self.bytes,
             f'packets_{"sent" if self.role=="sender" else "received"}':self.packets,
             'packets_lost':lost if self.role=='receiver' else None,'packets_expected':expected if self.role=='receiver' else None,
             'loss_percent':percent if self.role=='receiver' else None,
             'jitter_ms':self.jitter/90 if self.role=='receiver' and expected and not self.invalid_packets else None,
             'invalid_packets':self.invalid_packets,'duplicate_packets':self.duplicates,
             'metric_source':'udp_payload_sendto' if self.role=='sender' else 'udp_payload_recvfrom',
             'counter_scope':'UDP application payload; excludes IP/UDP/link headers'}
        self.last=end;self.last_bytes=self.bytes;self.last_packets=self.packets
        return row

    def summary(self):
        duration=max(.000001,time.monotonic()-self.started);expected,lost,percent=self.loss()
        return {'duration':duration,f'average_{"tx" if self.role=="sender" else "rx"}_bitrate':8*self.bytes/duration,
                f'bytes_{"sent" if self.role=="sender" else "received"}':self.bytes,
                f'packets_{"sent" if self.role=="sender" else "received"}':self.packets,
                'packets_expected':expected if self.role=='receiver' else None,
                'packets_lost':lost if self.role=='receiver' else None,'loss_percent':percent if self.role=='receiver' else None,
                'jitter':self.jitter_total/self.jitter_samples/90 if self.role=='receiver' and self.jitter_samples and not self.invalid_packets else None}
