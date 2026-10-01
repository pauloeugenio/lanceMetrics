import os, logging
from pathlib import Path
VERSION = '0.1.0'
ROOT = Path(os.environ.get('LANCE_ROOT', Path(__file__).resolve().parents[2]))
for name in ('data/experiments','data/profiles','logs','run'):
    (ROOT/name).mkdir(parents=True, exist_ok=True)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s', handlers=[logging.FileHandler(ROOT/'logs/lanceMetrics.log'), logging.StreamHandler()])
