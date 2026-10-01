"""Conservative parser: absence is null; sender flags determine provenance."""
FIELDS=('sender_bps','receiver_bps','sender_bytes','receiver_bytes','packets_sent','packets_received','packets_lost','loss_percent','jitter_ms','retransmissions')
class IperfParser:
    @staticmethod
    def row(s, sender, protocol):
        r={k:None for k in FIELDS}
        side='sender' if sender else 'receiver'
        r[side+'_bps']=s.get('bits_per_second'); r[side+'_bytes']=s.get('bytes')
        if sender:
            r['packets_sent']=s.get('packets') if protocol=='udp' else None
            r['retransmissions']=s.get('retransmits')
        elif protocol=='udp':
            r.update(packets_lost=s.get('lost_packets'),loss_percent=s.get('lost_percent'),jitter_ms=s.get('jitter_ms'))
            # iperf receiver packets is the expected total, including lost datagrams.
            if s.get('packets') is not None and s.get('lost_packets') is not None:
                r['packets_received']=max(0,s['packets']-s['lost_packets'])
        return r
    @classmethod
    def intervals(cls,doc,protocol):
        rows=[]
        for interval in doc.get('intervals',[]):
            s=interval.get('sum',{})
            if s.get('omitted') or 'sender' not in s: continue
            r=cls.row(s,s['sender'],protocol)
            r.update(elapsed_time=s.get('end'),interval_start=s.get('start'),seconds=s.get('seconds'),metric_source='iperf_interval_sender' if s['sender'] else 'iperf_interval_receiver')
            rows.append(r)
        return rows
    @classmethod
    def summary(cls,doc,protocol,local_role=None):
        end=doc.get('end',{}); r={k:None for k in FIELDS}
        for key,sender in [('sum_sent',True),('sum_received',False)]:
            if key in end and (local_role is None or (local_role=='sender')==sender):
                r.update({k:v for k,v in cls.row(end[key],sender,protocol).items() if v is not None})
        # Old UDP aggregate is ambiguous: never assign its throughput to both roles.
        s=end.get('sum',{})
        if protocol=='udp' and local_role!='sender' and 'sum_received' not in end and s:
            for k in ('jitter_ms','loss_percent','packets_lost','packets_received'):
                r[k]=cls.row(s,False,protocol)[k]
        return r
