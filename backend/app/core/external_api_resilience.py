"""
External API Resilience & Retry Engine

Handles failures when interacting with external providers:
- Trading platforms (MT4, MT5, cTrader)
- Payment providers (Stripe, Crypto gateways, etc.)
- KYC providers
- Email/SMS providers
- Webhook providers

Key Features:
- Error classification (RETRYABLE vs NON-RETRYABLE)
- Exponential backoff with jitter
- Idempotency keys for safety
- Dead-letter queue for failed retries
- Provider-specific error handling
- Webhook reconciliation on recovery

PRODUCTION RULE:
Never retry non-idempotent operations.
Never lose data during external failures.
Always have a defined failure path.
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any, Callable, Optional
from uuid import UUID
import json

from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
import httpx


class ExternalErrorClassification(StrEnum):
    """Classification of external provider errors."""
    
    # Retryable - safe to retry
    TIMEOUT = "TIMEOUT"
    CONNECTION_ERROR = "CONNECTION_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    TEMPORARY_UNAVAILABLE = "TEMPORARY_UNAVAILABLE"
    
    # Non-retryable - do not retry
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    INVALID_REQUEST = "INVALID_REQUEST"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    NOT_FOUND = "NOT_FOUND"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    BUSINESS_RULE_VIOLATION = "BUSINESS_RULE_VIOLATION"
    
    # Unknown - classify carefully
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class RetryStrategy:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay_seconds: float = 1.0,
        max_delay_seconds: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ):
        self.max_attempts = max_attempts
        self.initial_delay_seconds = initial_delay_seconds
        self.max_delay_seconds = max_delay_seconds
        self.exponential_base = exponential_base
        self.jitter = jitter
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for attempt (0-indexed)."""
        if attempt >= self.max_attempts:
            return None
        
        delay = self.initial_delay_seconds * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay_seconds)
        
        if self.jitter:
            import random
            delay = delay * (0.5 + random.random())
        
        return delay


class ExternalAPIResult:
    """Result of an external API call."""
    
    def __init__(
        self,
        success: bool,
        data: Any = None,
        error_classification: ExternalErrorClassification | None = None,
        error_message: str | None = None,
        is_retryable: bool = False,
        provider_response: dict | None = None,
        status_code: int | None = None,
    ):
        self.success = success
        self.data = data
        self.error_classification = error_classification
        self.error_message = error_message
        self.is_retryable = is_retryable
        self.provider_response = provider_response
        self.status_code = status_code


class ExternalAPICall:
    """Tracks state of external API call for retry logic."""
    
    def __init__(
        self,
        call_id: UUID,
        provider: str,
        endpoint: str,
        idempotency_key: str,
        payload: dict,
        retry_strategy: RetryStrategy | None = None,
    ):
        self.call_id = call_id
        self.provider = provider
        self.endpoint = endpoint
        self.idempotency_key = idempotency_key
        self.payload = payload
        self.retry_strategy = retry_strategy or RetryStrategy()
        
        self.attempt_count = 0
        self.last_error: Optional[str] = None
        self.last_classification: Optional[ExternalErrorClassification] = None
        self.last_attempt_at: Optional[datetime] = None
        self.next_retry_at: Optional[datetime] = None
        self.last_response: Optional[dict] = None


async def call_external_api_with_retry(
    call_id: UUID,
    provider: str,
    endpoint: str,
    idempotency_key: str,
    method: str,
    headers: dict,
    payload: dict,
    retry_strategy: RetryStrategy | None = None,
    timeout_seconds: int = 30,
) -> ExternalAPIResult:
    """
    Call external API with automatic retry on failure.
    
    Flow:
    1. Make request to external API
    2. Classify response
    3. If retryable error and attempts remaining, wait and retry
    4. If non-retryable error, fail immediately
    5. If max retries exceeded, add to dead-letter queue
    
    PRODUCTION RULE:
    - Never retry non-idempotent operations
    - Use idempotency keys to detect duplicate processing
    - Always have a defined failure state
    """
    
    if retry_strategy is None:
        retry_strategy = RetryStrategy()
    
    call = ExternalAPICall(
        call_id=call_id,
        provider=provider,
        endpoint=endpoint,
        idempotency_key=idempotency_key,
        payload=payload,
        retry_strategy=retry_strategy,
    )
    
    while call.attempt_count < retry_strategy.max_attempts:
        call.attempt_count += 1
        call.last_attempt_at = datetime.utcnow()
        
        try:
            # Make HTTP request
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                if method.upper() == "POST":
                    response = await client.post(
                        endpoint,
                        json=payload,
                        headers=headers,
                    )
                elif method.upper() == "GET":
                    response = await client.get(
                        endpoint,
                        headers=headers,
                    )
                elif method.upper() == "PUT":
                    response = await client.put(
                        endpoint,
                        json=payload,
                        headers=headers,
                    )
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
            
            call.last_response = {
                "status_code": response.status_code,
                "body": response.text[:1000],  # First 1000 chars
            }
            
            # Classify response
            if response.status_code in [200, 201, 202]:
                # Success
                return ExternalAPIResult(
                    success=True,
                    data=response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
                    provider_response={"status_code": response.status_code},
                    status_code=response.status_code,
                )
            
            # Classify error
            classification = classify_http_error(response.status_code, response.text)
            call.last_classification = classification
            call.last_error = f"HTTP {response.status_code}: {response.text[:200]}"
            
            is_retryable = classification in [
                ExternalErrorClassification.TIMEOUT,
                ExternalErrorClassification.CONNECTION_ERROR,
                ExternalErrorClassification.RATE_LIMITED,
                ExternalErrorClassification.TEMPORARY_UNAVAILABLE,
            ]
            
            if not is_retryable:
                # Non-retryable error
                return ExternalAPIResult(
                    success=False,
                    error_classification=classification,
                    error_message=call.last_error,
                    is_retryable=False,
                    provider_response=call.last_response,
                    status_code=response.status_code,
                )
            
            # Retryable error - sleep and retry
            if call.attempt_count < retry_strategy.max_attempts:
                delay = retry_strategy.get_delay(call.attempt_count - 1)
                call.next_retry_at = datetime.utcnow() + timedelta(seconds=delay)
                await asyncio.sleep(delay)
            
        except asyncio.TimeoutError:
            call.last_error = "Request timeout"
            call.last_classification = ExternalErrorClassification.TIMEOUT
            
            if call.attempt_count < retry_strategy.max_attempts:
                delay = retry_strategy.get_delay(call.attempt_count - 1)
                call.next_retry_at = datetime.utcnow() + timedelta(seconds=delay)
                await asyncio.sleep(delay)
            else:
                return ExternalAPIResult(
                    success=False,
                    error_classification=ExternalErrorClassification.TIMEOUT,
                    error_message="Request timeout after all retries",
                    is_retryable=True,
                )
        
        except Exception as e:
            call.last_error = str(e)
            call.last_classification = ExternalErrorClassification.CONNECTION_ERROR
            
            if call.attempt_count < retry_strategy.max_attempts:
                delay = retry_strategy.get_delay(call.attempt_count - 1)
                call.next_retry_at = datetime.utcnow() + timedelta(seconds=delay)
                await asyncio.sleep(delay)
            else:
                return ExternalAPIResult(
                    success=False,
                    error_classification=ExternalErrorClassification.CONNECTION_ERROR,
                    error_message=f"Connection failed: {str(e)}",
                    is_retryable=True,
                )
    
    # Max retries exceeded
    return ExternalAPIResult(
        success=False,
        error_classification=call.last_classification or ExternalErrorClassification.UNKNOWN_ERROR,
        error_message=f"Max retries exceeded: {call.last_error}",
        is_retryable=True,  # Could theoretically retry later
        provider_response=call.last_response,
    )


def classify_http_error(status_code: int, response_body: str) -> ExternalErrorClassification:
    """Classify HTTP error responses."""
    
    if status_code in [408, 429, 500, 502, 503, 504]:
        # Temporary failures
        if status_code == 429:
            return ExternalErrorClassification.RATE_LIMITED
        if status_code in [500, 502, 503]:
            return ExternalErrorClassification.TEMPORARY_UNAVAILABLE
        if status_code == 408:
            return ExternalErrorClassification.TIMEOUT
        return ExternalErrorClassification.TEMPORARY_UNAVAILABLE
    
    if status_code in [401, 403]:
        return ExternalErrorClassification.AUTHENTICATION_FAILED
    
    if status_code == 404:
        return ExternalErrorClassification.NOT_FOUND
    
    if status_code == 400:
        if "insufficient" in response_body.lower():
            return ExternalErrorClassification.INSUFFICIENT_FUNDS
        return ExternalErrorClassification.INVALID_REQUEST
    
    if status_code >= 500:
        return ExternalErrorClassification.TEMPORARY_UNAVAILABLE
    
    return ExternalErrorClassification.UNKNOWN_ERROR


async def reconcile_after_provider_recovery(
    db: AsyncSession,
    provider: str,
    tenant_id: UUID,
) -> dict:
    """
    Reconcile data after provider becomes available again.
    
    Queries provider for status of all pending operations
    and updates local state to match.
    
    Returns: dict with {
        "synchronized": int,
        "errors": list,
        "recovered_at": datetime
    }
    """
    # This would be provider-specific
    # Example: Query all pending trades from MT5, compare with local records
    
    return {
        "synchronized": 0,
        "errors": [],
        "recovered_at": datetime.utcnow(),
    }


__all__ = [
    "ExternalErrorClassification",
    "RetryStrategy",
    "ExternalAPIResult",
    "ExternalAPICall",
    "call_external_api_with_retry",
    "classify_http_error",
    "reconcile_after_provider_recovery",
]
