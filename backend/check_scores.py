import os
import sys
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.path.abspath('backend'))
from app.db import SessionLocal, AlertModel
db = SessionLocal()
max_score = db.query(AlertModel).order_by(AlertModel.risk_score.desc()).first()
count = db.query(AlertModel).filter(AlertModel.id.like('ALT-TGT-%')).count()
print(f'Max score: {max_score.risk_score if max_score else 0}')
print(f'Target count: {count}')
