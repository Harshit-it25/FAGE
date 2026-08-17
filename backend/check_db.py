import os
import sys
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.path.abspath('backend'))
from app.db import SessionLocal, AlertModel
db = SessionLocal()
count = db.query(AlertModel).count()
print(f'Total alerts in DB: {count}')
