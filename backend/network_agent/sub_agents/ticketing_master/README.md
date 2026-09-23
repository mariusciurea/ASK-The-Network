# ticketing_master

Answers questions about network tickets: text-to-SQL, named metrics, reports,
charts and Excel exports.

New to this agent? Start with the walkthrough in
[`docs/ticketing-master-guide.md`](../../../../docs/ticketing-master-guide.md),
which explains every file and the reasoning behind it. This page is the short
reference.

The problem this design solves: an LLM that only sees column names guesses what
"region" means. It filters `loc_identifier` in one turn and `description LIKE
'%Berlin%'` in the next, and both answers look plausible. Consistency cannot
come from a longer prompt alone - it comes from a described schema, typed tools
and validation in code.

## Layout

| File | Role |
|------|------|
| `semantic_layer.yaml` | Single source of truth: columns, synonyms, rules, value groups, metric SQL, examples, known limitations |
| `semantic_layer.py` | Loads and validates the YAML, renders the instruction and the on-demand topics |
| `prompt.py` | Agent instruction; the schema section is generated, not written by hand |
| `data_tools.py` | `describe_schema`, `lookup_column_values`, `get_ticket`, `run_metric` |
| `sql_guard.py` | Validates model-written SQL against the semantic layer |
| `callbacks.py` | `before_tool_callback` that runs the guard before `send_sql_command` |
| `value_index.py` | Cached distinct values per column, used by the lookup tool and the guard |
| `tools.py` | Report, chart and Excel artifacts |
| `eval/` | ADK eval set - the regression check after each YAML change |

Read-only SQL parsing lives in `backend/core/sql_safety.py`, because every agent
that runs SQL needs it.

## The four layers

1. **Described schema.** Each column carries a description, synonyms and a match
   mode (`exact`, `enum`, `free_text`, ...). A concept map translates user
   vocabulary into columns.
2. **Resolved values.** `lookup_column_values` maps the user's wording onto the
   values that actually exist, so a filter is never built on a guess. The
   distinct values are cached, not pasted into the prompt.
3. **Deterministic metrics.** The recurring questions are named queries in the
   YAML, executed with bound parameters. The same question produces the same
   SQL, every time. Free SQL stays available as the fallback for ad-hoc work.
4. **Validation before execution.** The guard rejects, before the database is
   touched: writes and stacked statements, unknown tables and columns, `LIKE` on
   exact-match columns, and a structured value searched in a free-text column.
   The rejection is returned to the model with the fix, so it can correct itself
   in the same turn.

## Token budget

The instruction is small (~1.4k tokens) and byte-for-byte identical between
requests, which is what makes prefix caching effective:

- metric SQL never enters the prompt - only the metric names;
- enum values, few-shot examples and detailed column docs are pulled with
  `describe_schema(topic)` only when the model needs them;
- the skill (`skills/ticketing-master-skill/SKILL.md`) holds the analysis
  playbooks and is loaded on demand by the `SkillToolset`, never eagerly;
- tool results are capped at `settings.MAX_ROWS`; the full result set is written
  to an artifact instead of into the context.

Rule of thumb: what the agent must never get wrong goes into the instruction,
what it occasionally needs goes behind a tool.

## Changing the schema

1. Edit `semantic_layer.yaml`.
2. `python backend/tests/test_ticketing_master.py` - structure, guard and metric
   SQL, offline.
3. `adk eval backend/network_agent/sub_agents/ticketing_master backend/network_agent/sub_agents/ticketing_master/eval/ticketing_master.evalset.json`
   - agent behaviour, needs a model and the database.
4. Commit the YAML and the eval set together: they describe the same contract.

Never re-document the schema in the prompt or the skill. A second copy is a
second truth.
