"""Semantic layer loader for the ticketing_master agent.

The YAML file next to this module describes the ticket database in business
terms. This module validates it with pydantic and renders two very different
views of it:

* :meth:`SemanticLayer.render_core_instruction` - small and static, injected in
  the agent instruction on every request (concept map, hard rules, one line per
  column). Keeping it static lets the model provider cache the prompt prefix.
* :meth:`SemanticLayer.render_topic` - the verbose parts (enum values, metric
  parameters, few-shot examples), served only when the agent asks for them
  through the ``describe_schema`` tool.
"""

from functools import lru_cache
from logging import getLogger
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator


logger = getLogger(__name__)

SEMANTIC_LAYER_PATH = Path(__file__).with_name("semantic_layer.yaml")

MatchKind = Literal["internal", "exact", "pattern", "enum", "numeric", "timestamp", "free_text"]
FilterKind = Literal["equals", "group", "prefix", "date_from", "date_to"]

DETAIL_TOPICS = ("columns", "values", "groups", "metrics", "examples", "rules", "limitations")


class DatasetSpec(BaseModel):
    """Physical and temporal characteristics of the dataset."""

    table: str
    dialect: str = "mysql"
    description: str = ""
    coverage_start: str = ""
    coverage_end: str = ""
    timestamp_format: str = "%m/%d/%Y %H:%i"
    reference_date_sql: str = ""


class ColumnSpec(BaseModel):
    """One physical column and the rules for filtering it."""

    type: str
    match: MatchKind
    description: str = ""
    hint: str = ""
    synonyms: list[str] = Field(default_factory=list)
    values: list[Any] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    pattern: str = ""
    notes: str = ""
    allow_like: bool = False
    lookup: bool = False
    cardinality: int | None = None

    @property
    def is_queryable(self) -> bool:
        """Whether the agent may reference the column at all."""

        return self.match != "internal"

    @property
    def is_free_text(self) -> bool:
        return self.match == "free_text"

    @property
    def accepts_like(self) -> bool:
        """Whether a LIKE predicate on this column is acceptable."""

        return self.match in ("pattern", "free_text") or self.allow_like

    @property
    def summary(self) -> str:
        """The one-liner used in the always-on part of the instruction."""

        return self.hint or self.description


class GroupSpec(BaseModel):
    """A named set of values for a column, e.g. active vs resolved statuses."""

    column: str
    description: str = ""
    members: dict[str, list[str]]
    labels: dict[str, str] = Field(default_factory=dict)


class RuleSpec(BaseModel):
    """A hard rule the agent must follow, optionally checked in code."""

    id: str
    text: str
    enforced_by: str = ""


class FilterSpec(BaseModel):
    """A filter that `run_metric` knows how to bind as a SQL parameter."""

    kind: FilterKind
    description: str = ""
    column: str = ""
    group: str = ""


class MetricSpec(BaseModel):
    """A named, deterministic query with a `{filters}` placeholder."""

    description: str
    sql: str
    default_limit: int = 20
    filter_alias: str = ""

    @model_validator(mode="after")
    def validate_sql(self) -> "MetricSpec":
        if "{filters}" not in self.sql:
            raise ValueError("metric SQL must contain the {filters} placeholder")
        return self


class ExampleSpec(BaseModel):
    """A worked example, with the tempting-but-wrong alternative."""

    question: str
    sql: str = ""
    call: str = ""
    avoid: str = ""
    note: str = ""


class UnsupportedSpec(BaseModel):
    """Something the dataset cannot answer, and why."""

    concept: str
    reason: str


class SemanticLayer(BaseModel):
    """The validated contents of semantic_layer.yaml."""

    version: int
    dataset: DatasetSpec
    columns: dict[str, ColumnSpec]
    groups: dict[str, GroupSpec] = Field(default_factory=dict)
    concepts: dict[str, str] = Field(default_factory=dict)
    rules: list[RuleSpec] = Field(default_factory=list)
    filters: dict[str, FilterSpec] = Field(default_factory=dict)
    metrics: dict[str, MetricSpec] = Field(default_factory=dict)
    examples: list[ExampleSpec] = Field(default_factory=list)
    unsupported: list[UnsupportedSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> "SemanticLayer":
        """Fail fast on a YAML that points at columns or groups that do not exist."""

        for name, group in self.groups.items():
            if group.column not in self.columns:
                raise ValueError(f"group '{name}' references unknown column '{group.column}'")

        for name, spec in self.filters.items():
            if spec.column and spec.column not in self.columns:
                raise ValueError(f"filter '{name}' references unknown column '{spec.column}'")
            if spec.group and spec.group not in self.groups:
                raise ValueError(f"filter '{name}' references unknown group '{spec.group}'")
            if spec.kind in ("group", "prefix") and not spec.group:
                raise ValueError(f"filter '{name}' of kind '{spec.kind}' requires a group")

        return self

    # -- column helpers ----------------------------------------------------

    @property
    def queryable_columns(self) -> dict[str, ColumnSpec]:
        return {name: spec for name, spec in self.columns.items() if spec.is_queryable}

    @property
    def free_text_columns(self) -> set[str]:
        return {name for name, spec in self.columns.items() if spec.is_free_text}

    @property
    def lookup_columns(self) -> dict[str, ColumnSpec]:
        return {name: spec for name, spec in self.columns.items() if spec.lookup}

    @property
    def structured_columns(self) -> dict[str, ColumnSpec]:
        """Columns that carry a canonical value a user term could refer to."""

        return {
            name: spec
            for name, spec in self.queryable_columns.items()
            if spec.match in ("exact", "enum")
        }

    def known_values(self) -> dict[str, list[str]]:
        """Declared enum values per column, as strings."""

        return {
            name: [str(value) for value in spec.values]
            for name, spec in self.columns.items()
            if spec.values
        }

    def group_members(self, group_name: str, member: str) -> list[str]:
        """Return the values of one member of a group (e.g. status_group/active)."""

        group = self.groups[group_name]
        if member not in group.members:
            valid = ", ".join(sorted(group.members))
            raise ValueError(f"unknown {group_name} '{member}'. Valid values: {valid}")
        return group.members[member]

    # -- rendering ---------------------------------------------------------

    def render_core_instruction(self) -> str:
        """Render the compact, always-on schema context.

        Deliberately terse: verbose material lives behind `describe_schema`, so
        the per-request prompt stays small and byte-for-byte stable.
        """

        lines: list[str] = []

        lines.append("## Dataset")
        lines.append(
            f"Table `{self.dataset.table}` ({self.dataset.dialect}). {self.dataset.description}"
        )
        lines.append(
            f"Coverage: {self.dataset.coverage_start} .. {self.dataset.coverage_end}. "
            f"Timestamps are strings: STR_TO_DATE(col, '{self.dataset.timestamp_format}')."
        )
        if self.dataset.reference_date_sql:
            lines.append(f"Reference date for relative ranges: {self.dataset.reference_date_sql}")

        lines.append("\n## Columns")
        for name, spec in self.queryable_columns.items():
            lines.append(f"- `{name}` ({spec.type}): {spec.summary}")

        lines.append("\n## Concept map (user wording -> column)")
        for concept, column in self.concepts.items():
            lines.append(f"- {concept} -> `{column}`")

        lines.append("\n## Rules")
        for index, rule in enumerate(self.rules, start=1):
            suffix = " [checked before execution]" if rule.enforced_by else ""
            lines.append(f"{index}. {rule.text.strip()}{suffix}")

        lines.append("\n## Metric catalogue (use with `run_metric`)")
        lines.append(", ".join(f"`{name}`" for name in self.metrics))

        lines.append(
            "\nCall `describe_schema(topic)` for details, one topic at a time: "
            + ", ".join(DETAIL_TOPICS)
            + "."
        )

        return "\n".join(lines)

    def render_topic(self, topic: str) -> str:
        """Render one detail topic for the `describe_schema` tool."""

        renderers = {
            "columns": self._render_columns_detail,
            "values": self._render_values,
            "groups": self._render_groups,
            "metrics": self._render_metrics,
            "examples": self._render_examples,
            "rules": self._render_rules,
            "limitations": self._render_limitations,
        }

        renderer = renderers.get(topic.strip().lower())
        if renderer is None:
            raise ValueError(f"unknown topic '{topic}'. Valid topics: {', '.join(DETAIL_TOPICS)}")
        return renderer()

    def _render_columns_detail(self) -> str:
        lines = ["## Columns in detail"]
        for name, spec in self.queryable_columns.items():
            lines.append(f"\n### `{name}` ({spec.type}, match: {spec.match})")
            lines.append(spec.description.strip())
            if spec.synonyms:
                lines.append(f"Synonyms: {', '.join(spec.synonyms)}")
            if spec.examples:
                lines.append(f"Examples: {', '.join(spec.examples)}")
            if spec.lookup:
                lines.append("Resolve user wording with `lookup_column_values` before filtering.")
            if spec.notes:
                lines.append(spec.notes.strip())
        return "\n".join(lines)

    def _render_values(self) -> str:
        lines = ["## Allowed values"]
        for name, values in self.known_values().items():
            lines.append(f"- `{name}`: " + ", ".join(f"'{value}'" for value in values))
        high_cardinality = [
            f"`{name}`" + (f" ({spec.cardinality} values)" if spec.cardinality else "")
            for name, spec in self.lookup_columns.items()
            if not spec.values
        ]
        if high_cardinality:
            lines.append(
                "\nToo many values to list, use `lookup_column_values`: "
                + ", ".join(high_cardinality)
            )
        return "\n".join(lines)

    def _render_groups(self) -> str:
        lines = ["## Value groups"]
        for name, group in self.groups.items():
            lines.append(f"\n### {name} (column `{group.column}`)")
            if group.description:
                lines.append(group.description.strip())
            for member, values in group.members.items():
                label = group.labels.get(member, "")
                label_suffix = f" - {label}" if label else ""
                lines.append(f"- {member}{label_suffix}: " + ", ".join(f"'{v}'" for v in values))
        return "\n".join(lines)

    def _render_metrics(self) -> str:
        lines = ["## Metric catalogue", "Call `run_metric(metric_name=..., <filters>)`.", ""]
        lines.append("Available filters:")
        for name, spec in self.filters.items():
            lines.append(f"- `{name}`: {spec.description.strip()}")
        for name, metric in self.metrics.items():
            lines.append(f"\n### `{name}`")
            lines.append(metric.description.strip())
            lines.append(f"Default limit: {metric.default_limit}")
        return "\n".join(lines)

    def _render_examples(self) -> str:
        lines = ["## Worked examples"]
        for example in self.examples:
            lines.append(f"\n**Q:** {example.question}")
            if example.call:
                lines.append(f"Call: `{example.call}`")
            if example.sql:
                lines.append("```sql\n" + example.sql.strip() + "\n```")
            if example.note:
                lines.append(f"Note: {example.note.strip()}")
            if example.avoid:
                lines.append(f"Do NOT write: {example.avoid.strip()}")
        return "\n".join(lines)

    def _render_rules(self) -> str:
        lines = ["## Rules"]
        for rule in self.rules:
            enforcement = f" (enforced by {rule.enforced_by})" if rule.enforced_by else ""
            lines.append(f"\n### {rule.id}{enforcement}")
            lines.append(rule.text.strip())
        return "\n".join(lines)

    def _render_limitations(self) -> str:
        lines = ["## Questions this dataset cannot answer"]
        for item in self.unsupported:
            lines.append(f"\n### {item.concept}")
            lines.append(item.reason.strip())
        return "\n".join(lines)


@lru_cache(maxsize=1)
def load_semantic_layer(path: Path = SEMANTIC_LAYER_PATH) -> SemanticLayer:
    """Load and validate the semantic layer.

    Args:
        path: Location of the YAML file. Only overridden in tests.

    Returns:
        The validated SemanticLayer. Cached, since the file is read-only at runtime.
    """

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    layer = SemanticLayer.model_validate(raw)
    logger.info(
        "Loaded semantic layer v%s: %s columns, %s metrics",
        layer.version,
        len(layer.columns),
        len(layer.metrics),
    )
    return layer
