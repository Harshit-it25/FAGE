import sys
import os
sys.path.insert(0, os.path.abspath('.'))

os.environ['FAGE_ENV'] = 'test'

from app.auth import authenticate_user, USERS, _DEMO_PLAIN

print("\nUSERS:")
print(USERS)
print("\nDEMO_PLAIN:")
print(_DEMO_PLAIN)
print("\nAdmin Auth:")
print(authenticate_user("admin", "admin123"))
