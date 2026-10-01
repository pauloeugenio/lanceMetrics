import csv,io,json,re
from ..database import Session,Experiment,Measurement,serialize

def experiment_data(id):
    with Session() as db:
        e=db.get(Experiment,id)
        if not e: return None
        result=serialize(e)
        result['measurements']=[m.values for m in db.query(Measurement).filter_by(experiment_id=id).order_by(Measurement.id)]
        return result

def csv_export(data):
    rows=data['measurements']; output=io.StringIO()
    fields=['experiment_uuid','timestamp','elapsed_time','interval_start','seconds','stage_id','session_id','target_bps','sender_bps','receiver_bps','sender_bytes','receiver_bytes','packets_sent','packets_received','packets_lost','loss_percent','jitter_ms','retransmissions','metric_source']
    writer=csv.DictWriter(output,fields,extrasaction='ignore'); writer.writeheader()
    for row in rows: writer.writerow({'experiment_uuid':data['uuid'],**row})
    return output.getvalue()
def filename(data,ext):
    target=data['config'].get('target','server'); protocol=data['config'].get('protocol','unknown')
    return re.sub(r'[^a-zA-Z0-9_.-]','_',f'lanceMetrics_{data["created_at"][:10]}_{protocol}_{target}_{data["id"]}.{ext}')
