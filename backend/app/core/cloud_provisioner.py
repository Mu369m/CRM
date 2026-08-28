"""Cloud database provisioning integrations."""

import asyncio
import logging
import os
from urllib.parse import quote, urlsplit, urlunsplit

import httpx

logger = logging.getLogger(__name__)

_DIGITALOCEAN_DATABASES_URL = "https://api.digitalocean.com/v2/databases"
_REQUEST_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_POLL_INTERVAL_SECONDS = 15


class DigitalOceanProvisioningError(RuntimeError):
    """Raised when DigitalOcean cannot provision or ready a database."""


def _connection_string(connection: dict[str, object]) -> str:
    """Build the SQLAlchemy async URL from DigitalOcean connection fields."""
    raw_uri = connection.get("uri")
    if isinstance(raw_uri, str) and raw_uri:
        parsed = urlsplit(raw_uri)
        if parsed.hostname and parsed.username and parsed.password and parsed.port and parsed.path:
            return urlunsplit(
                ("postgresql+asyncpg", parsed.netloc, parsed.path, "ssl=require", "")
            )

    required = ("user", "password", "host", "port", "database")
    if not all(isinstance(connection.get(key), (str, int)) for key in required):
        raise DigitalOceanProvisioningError("DigitalOcean returned incomplete database credentials")
    user = quote(str(connection["user"]), safe="")
    password = quote(str(connection["password"]), safe="")
    host = str(connection["host"])
    port = int(connection["port"])
    database = quote(str(connection["database"]), safe="")
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}?ssl=require"


async def create_digitalocean_postgres(tenant_slug: str, max_attempts: int = 30) -> str:
    """Create a PostgreSQL 16 cluster and wait until DigitalOcean reports it online."""
    token = os.environ.get("DIGITALOCEAN_API_TOKEN")
    if not token:
        raise DigitalOceanProvisioningError("DIGITALOCEAN_API_TOKEN is not configured")
    if not tenant_slug.strip():
        raise ValueError("tenant_slug must not be empty")
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "name": f"crm-{tenant_slug.strip()}",
        "engine": "pg",
        "version": "16",
        "region": "nyc3",
        "size": "db-s-1vcpu-1gb",
        "num_nodes": 1,
    }

    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            response = await client.post(_DIGITALOCEAN_DATABASES_URL, headers=headers, json=payload)
            response.raise_for_status()
            cluster = response.json().get("database", {})
            cluster_id = cluster.get("id")
            if not isinstance(cluster_id, str) or not cluster_id:
                raise DigitalOceanProvisioningError("DigitalOcean response did not include a cluster ID")

            for attempt in range(1, max_attempts + 1):
                response = await client.get(f"{_DIGITALOCEAN_DATABASES_URL}/{cluster_id}", headers=headers)
                response.raise_for_status()
                cluster = response.json().get("database", {})
                state = cluster.get("status")
                logger.info("DigitalOcean database %s status=%s attempt=%d/%d", cluster_id, state, attempt, max_attempts)
                if state == "online":
                    connection = cluster.get("connection")
                    if not isinstance(connection, dict):
                        raise DigitalOceanProvisioningError("DigitalOcean response did not include connection details")
                    return _connection_string(connection)
                if state in {"error", "failed"}:
                    raise DigitalOceanProvisioningError(f"DigitalOcean database entered terminal status: {state}")
                if attempt < max_attempts:
                    await asyncio.sleep(_POLL_INTERVAL_SECONDS)
    except httpx.HTTPError as error:
        logger.exception("DigitalOcean database provisioning request failed")
        raise DigitalOceanProvisioningError("DigitalOcean database provisioning request failed") from error

    raise DigitalOceanProvisioningError("Timed out waiting for DigitalOcean database to become online")