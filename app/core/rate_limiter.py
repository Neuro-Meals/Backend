import hashlib

import redis
from fastapi import HTTPException, Request, status

from app.core.config import settings


redis_client = redis.Redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
)


def get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    if request.client:
        return request.client.host

    return "unknown"


def normalize_identifier(value: str) -> str:
    return value.strip().lower()


def hash_key(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def rate_limit(
    key: str,
    limit: int,
    window_seconds: int,
):
    current = redis_client.incr(key)

    if current == 1:
        redis_client.expire(key, window_seconds)

    if current > limit:
        ttl = redis_client.ttl(key)

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "message": "Too many attempts. Please try again later.",
                "retry_after_seconds": ttl,
            },
        )