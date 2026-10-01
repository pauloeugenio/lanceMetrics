"""Explicit, authenticated removal of completed experiments and their raw files."""
import logging,shutil,uuid
from ..core import ROOT
from ..database import Session,Experiment,Measurement
log=logging.getLogger(__name__)
class DeletionError(Exception):
    def __init__(self,status,message):self.status=status;super().__init__(message)

def delete_experiments(ids,active_ids):
    ids=list(dict.fromkeys(ids));moved=[];trash=ROOT/'data/.deleting'/str(uuid.uuid4())
    with Session() as db:
        records=db.query(Experiment).filter(Experiment.id.in_(ids)).all()
        if len(records)!=len(ids):raise DeletionError(404,'Um ou mais experimentos não foram encontrados. Nenhum foi excluído.')
        if any(e.status in ('RUNNING','STARTING','STOPPING') or e.id in active_ids for e in records):
            raise DeletionError(409,'Não é possível excluir testes em execução ou finalização. Pare o teste e tente novamente.')
        try:
            for e in records:
                # UUID validation ensures no record can redirect removal outside experiment data.
                name=str(uuid.UUID(e.uuid));folder=ROOT/'data/experiments'/name
                if folder.is_symlink():raise DeletionError(409,'Diretório de experimento inválido; exclusão recusada.')
                if folder.exists():
                    trash.mkdir(parents=True,exist_ok=True);target=trash/name;folder.rename(target);moved.append((folder,target))
            db.query(Measurement).filter(Measurement.experiment_id.in_(ids)).delete(synchronize_session=False)
            db.query(Experiment).filter(Experiment.id.in_(ids)).delete(synchronize_session=False)
            db.commit()
        except Exception:
            db.rollback()
            for folder,target in reversed(moved):
                if target.exists():target.rename(folder)
            if trash.exists():shutil.rmtree(trash)
            raise
    cleanup_pending=False
    if trash.exists():
        try:shutil.rmtree(trash)
        except OSError:cleanup_pending=True;log.exception('experiment raw cleanup pending path=%s',trash)
    log.info('experiments deleted ids=%s cleanup_pending=%s',ids,cleanup_pending)
    return {'deleted_ids':ids,'count':len(ids),'cleanup_pending':cleanup_pending}
