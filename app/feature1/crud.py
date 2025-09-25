# Simulated in-memory CRUD for users
from typing import Dict, List

db: Dict[int, Dict] = {}
current_id = 1

def create_user(user_data: Dict) -> Dict:
    global current_id
    user = {"id": current_id, **user_data}
    db[current_id] = user
    current_id += 1
    return user

def get_user(user_id: int) -> Dict | None:
    return db.get(user_id)

def list_users() -> List[Dict]:
    return list(db.values())
