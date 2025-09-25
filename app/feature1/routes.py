from fastapi import APIRouter
from app.feature1.services import register_user, retrieve_user, list_all_users

router = APIRouter()

@router.post("/users")
async def create_user_endpoint(payload: dict):
    return await register_user(payload)

@router.get("/users/{user_id}")
async def get_user_endpoint(user_id: int):
    user = await retrieve_user(user_id)
    if user is None:
        return {"error": "User not found"}
    return user

@router.get("/users")
async def list_users_endpoint():
    return await list_all_users()
