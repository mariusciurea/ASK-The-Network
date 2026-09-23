"""Distinct value index for the ticket columns.

Two consumers need to know which values actually exist in the database:

* `lookup_column_values` - to turn the user's wording ("link down") into the
  canonical value ("Link Down") before it ends up in a filter.
* `sql_guard` - to detect a value that was pushed into a free-text column
  although it belongs to a structured one.

Values are cached for a short while: the ticket table changes far more slowly
than the agent is queried, and a cache miss must never break a conversation.
"""

import time
from logging import getLogger
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.core.serialization import json_safe_rows
from backend.core.settings import settings
from backend.database.db import engine
from backend.network_agent.sub_agents.ticketing_master.semantic_layer import (
    SemanticLayer,
    load_semantic_layer,
)


logger = getLogger(__name__)

# How long a failed lookup is remembered, so an unreachable database is not
# dialled again for every column of every query.
FAILURE_COOLDOWN_SECONDS = 30

# column -> (expires_at, rows)
_distinct_values_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
# column -> (retry_after, error)
_failed_lookups: dict[str, tuple[float, SQLAlchemyError]] = {}


def _assert_known_column(column: str, layer: SemanticLayer) -> None:
    """Reject any column that is not declared as a lookup column.

    The column name is interpolated into SQL (identifiers cannot be bound as
    parameters), so it must come from the semantic layer, never from the model.
    """

    if column not in layer.lookup_columns:
        valid = ", ".join(sorted(layer.lookup_columns))
        raise ValueError(f"'{column}' is not a lookup column. Valid columns: {valid}")


def distinct_values(column: str, layer: SemanticLayer | None = None) -> list[dict[str, Any]]:
    """Return the distinct values of a lookup column with their ticket counts.

    Args:
        column: Name of a column declared with `lookup: true`.
        layer: Semantic layer override, only used in tests.

    Returns:
        A list of {"value": ..., "ticket_count": ...} sorted by frequency.

    Raises:
        ValueError: If the column is not a declared lookup column.
        SQLAlchemyError: If the database is unreachable.
    """

    layer = layer or load_semantic_layer()
    _assert_known_column(column, layer)

    cached = _distinct_values_cache.get(column)
    if cached and cached[0] > time.monotonic():
        return cached[1]

    failure = _failed_lookups.get(column)
    if failure and failure[0] > time.monotonic():
        raise failure[1]

    query = text(
        f"SELECT {column} AS value, COUNT(*) AS ticket_count "  # noqa: S608 - whitelisted identifier
        f"FROM {layer.dataset.table} "
        f"WHERE {column} IS NOT NULL AND {column} <> '' "
        f"GROUP BY {column} ORDER BY ticket_count DESC"
    )

    try:
        with engine.connect() as connection:
            rows = json_safe_rows([dict(row) for row in connection.execute(query).mappings().all()])
    except SQLAlchemyError as error:
        _failed_lookups[column] = (time.monotonic() + FAILURE_COOLDOWN_SECONDS, error)
        raise

    _failed_lookups.pop(column, None)
    _distinct_values_cache[column] = (time.monotonic() + settings.VALUE_CACHE_TTL_SECONDS, rows)
    logger.info("Cached %s distinct values for column '%s'", len(rows), column)
    return rows


def structured_values(layer: SemanticLayer | None = None) -> dict[str, set[str]]:
    """Return the values a user term could legitimately refer to, per column.

    Combines the enum values declared in the semantic layer with the distinct
    values of the lookup columns. If the database is unreachable the declared
    values are still returned, so the guard degrades instead of failing.

    Args:
        layer: Semantic layer override, only used in tests.

    Returns:
        Mapping of column name to the set of its known values.
    """

    layer = layer or load_semantic_layer()

    values: dict[str, set[str]] = {
        column: set(known) for column, known in layer.known_values().items()
    }

    for column in layer.lookup_columns:
        try:
            values.setdefault(column, set()).update(
                str(row["value"]) for row in distinct_values(column, layer)
            )
        except SQLAlchemyError as error:
            logger.warning(
                "Could not index values for column '%s', guard runs on declared values only: %s",
                column,
                error,
            )

    return values


def clear_cache() -> None:
    """Drop the cached values, e.g. after the ticket table has been reloaded."""

    _distinct_values_cache.clear()
    _failed_lookups.clear()
