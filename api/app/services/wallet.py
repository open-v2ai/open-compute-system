from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, WalletTransaction

MICROS_PER_CENT = 10_000


async def debit_cents(
    db: AsyncSession,
    *,
    user: User,
    amount_cents: int,
    transaction_type: str,
    idempotency_key: str,
    description: str,
    order_id: str | None = None,
) -> WalletTransaction | None:
    """Debit whole cents from a locked user. Returns existing row on idempotent replay."""
    if amount_cents <= 0:
        raise ValueError("debit amount must be positive")
    existing = await db.scalar(
        select(WalletTransaction).where(
            WalletTransaction.user_id == user.id,
            WalletTransaction.idempotency_key == idempotency_key,
        )
    )
    if existing:
        return existing
    if user.balance_cents < amount_cents:
        return None
    user.balance_cents -= amount_cents
    row = WalletTransaction(
        user_id=user.id,
        order_id=order_id,
        transaction_type=transaction_type,
        amount_cents=-amount_cents,
        balance_after_cents=user.balance_cents,
        idempotency_key=idempotency_key,
        description=description,
    )
    db.add(row)
    return row


async def credit_cents(
    db: AsyncSession,
    *,
    user: User,
    amount_cents: int,
    transaction_type: str,
    idempotency_key: str,
    description: str,
    order_id: str | None = None,
) -> WalletTransaction:
    """Credit whole cents to a locked user. Idempotent on key."""
    if amount_cents <= 0:
        raise ValueError("credit amount must be positive")
    existing = await db.scalar(
        select(WalletTransaction).where(
            WalletTransaction.user_id == user.id,
            WalletTransaction.idempotency_key == idempotency_key,
        )
    )
    if existing:
        return existing
    user.balance_cents += amount_cents
    row = WalletTransaction(
        user_id=user.id,
        order_id=order_id,
        transaction_type=transaction_type,
        amount_cents=amount_cents,
        balance_after_cents=user.balance_cents,
        idempotency_key=idempotency_key,
        description=description,
    )
    db.add(row)
    return row


def cost_micros_for_tokens(
    *,
    prompt_tokens: int,
    completion_tokens: int,
    price_prompt_per_mtok_cents: int,
    price_completion_per_mtok_cents: int,
) -> int:
    """Convert token usage to micros (1 cent = 10_000 micros)."""
    weighted = (
        prompt_tokens * price_prompt_per_mtok_cents
        + completion_tokens * price_completion_per_mtok_cents
    )
    return (weighted * MICROS_PER_CENT) // 1_000_000


def settle_inference_micros(user: User, cost_micros: int) -> int:
    """Apply sub-cent cost to remainder; return whole cents to debit (may be 0)."""
    if cost_micros < 0:
        raise ValueError("cost_micros must be non-negative")
    total = user.inference_remainder_micros + cost_micros
    debit_cents = total // MICROS_PER_CENT
    user.inference_remainder_micros = total % MICROS_PER_CENT
    return debit_cents


def estimate_max_cost_micros(
    *,
    prompt_tokens: int,
    max_completion_tokens: int,
    price_prompt_per_mtok_cents: int,
    price_completion_per_mtok_cents: int,
) -> int:
    return cost_micros_for_tokens(
        prompt_tokens=prompt_tokens,
        completion_tokens=max_completion_tokens,
        price_prompt_per_mtok_cents=price_prompt_per_mtok_cents,
        price_completion_per_mtok_cents=price_completion_per_mtok_cents,
    )


def available_micros(user: User) -> int:
    return user.balance_cents * MICROS_PER_CENT + user.inference_remainder_micros
