"""Semantic validation of the SQL produced by the ticketing_master agent.

`backend.core.sql_safety` answers "is this query safe?". This module answers
"does this query mean what the user asked?", using the semantic layer:

* only the ticket table may be queried;
* only columns that exist may be referenced (no `solution_date`, no `region`);
* a value that belongs to a structured column may not be searched in free text
  - that is the "Berlin appears in the description too" failure mode;
* columns declared as exact matches may not be filtered with LIKE;
* every query comes back with a bounded LIMIT.

The checks run in a `before_tool_callback`, so a rejected query never reaches
the database and the model gets a message it can act on.
"""

from logging import getLogger
from typing import Iterable, Mapping

from sqlglot import expressions as exp

from backend.core.settings import settings
from backend.core.sql_safety import UnsafeSQLError, enforce_limit, parse_read_only
from backend.network_agent.sub_agents.ticketing_master.semantic_layer import (
    SemanticLayer,
    load_semantic_layer,
)


logger = getLogger(__name__)

# Predicates where a column is compared against a literal value.
_COMPARISONS = (exp.EQ, exp.NEQ, exp.Like, exp.ILike, exp.In)


def _collect_aliases(statement: exp.Expression) -> set[str]:
    """Collect every name a query defines itself (column aliases, CTEs, tables)."""

    aliases: set[str] = set()

    for node in statement.walk():
        if isinstance(node, exp.Alias):
            aliases.add(node.alias.lower())
        elif isinstance(node, exp.TableAlias):
            aliases.add(node.name.lower())
        elif isinstance(node, exp.CTE):
            aliases.add(node.alias_or_name.lower())

    return aliases


def _check_tables(statement: exp.Expression, layer: SemanticLayer) -> None:
    """Reject queries that touch a table outside this agent's scope."""

    allowed = {layer.dataset.table.lower()}
    cte_names = {node.alias_or_name.lower() for node in statement.find_all(exp.CTE)}

    for table in statement.find_all(exp.Table):
        name = table.name.lower()
        if name and name not in allowed and name not in cte_names:
            raise UnsafeSQLError(
                f"Table '{table.name}' is out of scope. This agent queries only "
                f"'{layer.dataset.table}'."
            )


def _check_columns(statement: exp.Expression, layer: SemanticLayer) -> None:
    """Reject references to columns that do not exist in the ticket table."""

    known = {name.lower() for name in layer.queryable_columns}
    aliases = _collect_aliases(statement)

    for column in statement.find_all(exp.Column):
        name = column.name.lower()
        if not name or name == "*":
            continue
        if name in known or name in aliases:
            continue
        raise UnsafeSQLError(
            f"Column '{column.name}' does not exist in {layer.dataset.table}. "
            f"Available columns: {', '.join(sorted(known))}."
        )


def _literals(predicate: exp.Expression) -> list[str]:
    """Return the string literals a predicate compares a column against."""

    if isinstance(predicate, exp.In):
        candidates: Iterable[exp.Expression] = predicate.expressions
    else:
        candidates = [predicate.expression] if predicate.expression else []

    return [node.name for node in candidates if isinstance(node, exp.Literal) and node.is_string]


def _canonical(value: str) -> str:
    """Normalise a literal for comparison: drop LIKE wildcards and case."""

    return value.strip().strip("%").strip().casefold()


def _check_predicates(
    statement: exp.Expression,
    layer: SemanticLayer,
    known_values: Mapping[str, set[str]],
) -> None:
    """Apply the filtering rules of the semantic layer to every predicate."""

    # normalised literal -> (owning column, value as stored in the database)
    value_owners: dict[str, tuple[str, str]] = {
        _canonical(value): (column, value)
        for column, values in known_values.items()
        for value in values
        if _canonical(value)
    }

    for predicate in statement.find_all(*_COMPARISONS):
        column_node = predicate.this
        if not isinstance(column_node, exp.Column):
            continue

        spec = layer.columns.get(column_node.name.lower())
        if spec is None:
            continue

        if isinstance(predicate, (exp.Like, exp.ILike)) and not spec.accepts_like:
            raise UnsafeSQLError(
                f"Column '{column_node.name}' must be filtered with '=' or IN, not LIKE. "
                f"Use lookup_column_values to resolve the exact value first."
            )

        if not spec.is_free_text:
            continue

        for literal in _literals(predicate):
            owner = value_owners.get(_canonical(literal))
            if owner:
                owner_column, canonical_value = owner
                raise UnsafeSQLError(
                    f"'{literal}' is a value of the '{owner_column}' column, so searching it in "
                    f"the free-text column '{column_node.name}' also matches unrelated tickets. "
                    f"Filter on {owner_column} = '{canonical_value}' instead."
                )


def guard_sql(
    sql_query: str,
    layer: SemanticLayer | None = None,
    known_values: Mapping[str, set[str]] | None = None,
) -> str:
    """Validate a model-generated query and return the version that may run.

    Args:
        sql_query: The SQL written by the agent.
        layer: Semantic layer override, only used in tests.
        known_values: Column values used for the free-text check. Defaults to the
            live value index; pass an explicit mapping in tests.

    Returns:
        The query with a bounded LIMIT applied.

    Raises:
        UnsafeSQLError: If the query is unsafe or contradicts the semantic layer.
    """

    layer = layer or load_semantic_layer()

    if known_values is None:
        # Imported lazily: the value index talks to the database, the parsing
        # rules above do not, and tests exercise them without a database.
        from backend.network_agent.sub_agents.ticketing_master.value_index import structured_values

        known_values = structured_values(layer)

    statement = parse_read_only(sql_query, dialect=layer.dataset.dialect)

    _check_tables(statement, layer)
    _check_columns(statement, layer)
    _check_predicates(statement, layer, known_values)

    return enforce_limit(statement, settings.MAX_SQL_LIMIT, dialect=layer.dataset.dialect)
