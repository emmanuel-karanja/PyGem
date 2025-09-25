from app.feature1.crud import create_user, get_user, list_users
from app.config.factory import get_logger, get_redis_client

logger = get_logger("feature1_service")
redis_client = get_redis_client(logger)

async def register_user(user_data: dict) -> dict:
    user = create_user(user_data)
    # Optionally cache user in Redis
    await redis_client.set(f"user:{user['id']}", user, ttl=3600)
    logger.info("User registered", extra={"user_id": user["id"]})
    return user

async def retrieve_user(user_id: int) -> dict | None:
    cached = await redis_client.get(f"user:{user_id}")
    if cached:
        return cached
    return get_user(user_id)

async def list_all_users() -> list[dict]:
    return list_users()
