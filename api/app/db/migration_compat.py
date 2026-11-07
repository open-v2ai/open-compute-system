"""Compatibility for the unnamed unique constraint in the immutable initial revision."""

import sqlalchemy as sa
from sqlalchemy.engine import Connection

INITIAL_REVISION = "3edf12b7c297"
OUTBOX_REVISION = "65f1010f9f45"
LEGACY_REVISIONS = {INITIAL_REVISION, OUTBOX_REVISION}


def normalize_legacy_order_constraint(connection: Connection) -> None:
    """Preserve uniqueness while making PostgreSQL's auto-name match revision 9a8b7c6d5e4f."""
    if connection.dialect.name != "postgresql":
        return
    constraints = sa.inspect(connection).get_unique_constraints("orders")
    expected = "uq_orders_idempotency_key"
    if any(item["name"] == expected for item in constraints):
        return
    candidates = [item for item in constraints if item["column_names"] == ["idempotency_key"]]
    if len(candidates) != 1 or not candidates[0]["name"]:
        raise RuntimeError("Unrecognized legacy orders uniqueness; refusing automatic repair")
    quote = connection.dialect.identifier_preparer.quote
    actual = quote(candidates[0]["name"])
    connection.execute(sa.text(
        f"ALTER TABLE orders RENAME CONSTRAINT {actual} TO {quote(expected)}"
    ))
