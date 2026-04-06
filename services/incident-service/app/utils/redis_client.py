"""
Client Redis synchrone pour incident-service.
Utilisé pour PUBLISH incidents.new après création d'un incident.
"""
import json
import logging

import redis

from ..config import settings

logger = logging.getLogger(__name__)

_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis | None:
    """Retourne le client Redis global (lazy init). None si Redis indisponible."""
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            _redis_client.ping()
        except redis.RedisError as exc:
            logger.warning("Redis indisponible au démarrage : %s", exc)
            _redis_client = None
    return _redis_client


def publish_incident(payload: dict) -> None:
    """
    PUBLISH incidents.new avec le payload JSON.
    Ne lève jamais d'exception — Redis est non-bloquant pour la création d'incident.
    """
    client = get_redis()
    if client is None:
        logger.warning("PUBLISH incidents.new ignoré — Redis indisponible")
        return
    try:
        client.publish("incidents.new", json.dumps(payload))
    except redis.RedisError as exc:
        logger.warning("PUBLISH incidents.new échoué : %s", exc)
