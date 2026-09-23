# Guide: how the `ticketing_master` agent works

For anyone working on this agent for the first time. It explains **what** we
built, **why** it looks like this, and **which concept** sits behind each piece.

Read it in order - every chapter builds on the previous one.

---

## 1. The problem we are solving

The agent receives a question in natural language and has to answer with data
from the `ticket_data` table. The naive version is simple: give the model the
table schema and ask it to write SQL.

It works well for simple questions. It breaks on complex ones, and it breaks
**inconsistently** - the same question, asked twice, gives two different
answers. The classic example:

> "What is the most common resolution for tickets in region X?"

The model does not know what "region" means in our schema. It can choose
between:

```sql
-- the correct version
WHERE loc_identifier = 'DZR1Y'

-- the one it sometimes picks
WHERE description LIKE '%DZR1Y%'
```

The second one looks reasonable, because the description really does contain the
site code. But it also contains it in tickets that belong to other locations
(the text mentions the network element, not the ticket's location). The result:
wrong numbers that look credible. That is the most dangerous kind of bug -
nothing crashes, you simply report something other than reality.

### The central idea

> A prompt is a **soft** constraint. Code is a **hard** constraint.

You can write "never filter on description" in the prompt. The model will
respect it 95% of the time. If you want real consistency, the remaining 5% has
to be stopped in code, before the query reaches the database.

Hence the four layers:

| Layer | What it does | Where it lives |
|---|---|---|
| 1. Described schema | Tells the model what each column means | `semantic_layer.yaml` → instruction |
| 2. Resolved values | Turns the user's words into real values | `lookup_column_values` |
| 3. Deterministic metrics | Answers with SQL written once, by us | `run_metric` |
| 4. Validation | Rejects anything contradicting the layers above | `sql_guard` + callback |

Layers 1-3 **reduce** mistakes. Layer 4 **eliminates** the ones that can be
detected automatically.

---

## 2. What a "semantic layer" is

A **semantic layer** is the dictionary between human language and the structure
of the database.

The database tells you:
```
loc_identifier VARCHAR(100)
```

The semantic layer tells you:
```yaml
loc_identifier:
  description: Site / location code of the ticket. The only geographic column.
  synonyms: [location, site, region, area, geography, where]
  match: exact          # '=' or IN only, never LIKE
  lookup: true          # values are resolved with lookup_column_values
```

The difference: the second version carries **intent** and **rules**, not just
data types. That is exactly the information the model needs in order not to
guess.

### Why YAML and not the prompt directly

Because the same information is used in four different places:

1. the agent instruction (so the model knows),
2. the `describe_schema` tool (details on demand),
3. `sql_guard` (to validate),
4. `run_metric` (to build the SQL).

If the information lives in the prompt, you copy it into the other three. Two
months later you change one and forget the rest - this is called **drift**, and
it is the main source of bugs in agent systems. One file versioned in git means
one source of truth.

> Team rule: if you write a fact about the database in two places, one of them
> will become false. Decide where the truth lives and generate the rest from it.

---

## 3. The files, one by one

### 3.1 `semantic_layer.yaml` - the source of truth

Its sections and what each represents:

**`dataset`** - the physical characteristics of the table.
```yaml
coverage_start: "2026-01-01"
coverage_end: "2026-06-30"
reference_date_sql: "(SELECT MAX(STR_TO_DATE(start, '%m/%d/%Y %H:%i')) FROM ticket_data)"
```
Why it matters: the data is historical, January to June 2026. If the model
writes `WHERE start >= NOW() - INTERVAL 30 DAY` it gets **zero rows** and
reports "there are no recent tickets" - which is false. That is why we define a
"reference date" = the most recent ticket in the data, and the rule says
relative ranges must be anchored on it.

**`columns`** - every column with description, synonyms and `match`.

`match` is the key. It says *how* a column may be filtered:

| `match` | Meaning | Example |
|---|---|---|
| `exact` | `=` or `IN` only | `loc_identifier = 'DZR1Y'` |
| `enum` | `=` / `IN`, restricted to the listed values | `status IN ('Open', 'Closed')` |
| `pattern` | `LIKE` with a documented prefix | `ticket_number LIKE 'Z_INM%'` |
| `numeric` | comparisons | `priority <= 2` |
| `timestamp` | always through `STR_TO_DATE()` | `STR_TO_DATE(start, ...) >= '2026-03-01'` |
| `free_text` | human prose, searched only on explicit request | `description LIKE '%fiber splice%'` |
| `internal` | never exposed | `id` |

The guard reads exactly these values when validating. So when you change `match`
in the YAML, you automatically change what validation accepts. That is the idea
of **executable configuration** - the file is not dead documentation, it is code.

**`hint` vs `description`** - two lengths for two contexts:
```yaml
subject:
  hint: normalised alarm / problem name - THE column for "what kind of problem"
  description: >-
    Short, normalised title of the issue or activity. This is the structured
    "alarm name" / "problem type" of a ticket.
```
`hint` (one line) goes into the instruction, on every request. `description`
(long) is sent only when the model explicitly asks for details. See chapter 5 on
tokens.

**`groups`** - named sets of values:
```yaml
status_group:
  members:
    active: [Open, In Progress, Assigned, Noticed]
    resolved: [Closed, Answered]
```
The user says "active tickets". Without the group, the model has to remember all
four statuses - it usually gets them right, but not always. With the group it
writes `status_group='active'` and the code expands the list. Deterministic.

**`concepts`** - the vocabulary → column map. This is the direct answer to "the
model guesses where Berlin is".

**`rules`** - the hard rules, in natural language, with one special field:
```yaml
- id: geo_filters_use_loc_identifier
  text: >-
    Any geographic filter uses loc_identifier with '=' or IN...
  enforced_by: sql_guard.misplaced_literal
```
`enforced_by` documents *which rule is also checked in code*. Reading the YAML
you immediately know what is a recommendation and what is law.

**`metrics`** - the SQL of the recurring questions, written by us:
```yaml
top_resolutions:
  description: Most frequent resolution categories...
  default_limit: 10
  sql: |
    SELECT response_subject AS resolution, COUNT(*) AS ticket_count
    FROM ticket_data
    WHERE 1=1
      AND response_subject <> ''
      {filters}
    GROUP BY response_subject
    ORDER BY ticket_count DESC
```
`{filters}` is where the code injects the filters. `WHERE 1=1` is a classic
trick: it lets every filter be appended uniformly with `AND ...`, without
special-casing the first one.

**`examples`** - few-shot examples, with an `avoid` field showing the **tempting
mistake**:
```yaml
- question: What is the most common resolution for tickets on site DZR1Y?
  call: "run_metric(metric_name='top_resolutions', loc_identifier='DZR1Y')"
  avoid: >-
    WHERE description LIKE '%DZR1Y%' - the site code also appears in the free
    text of tickets that belong to other sites.
```
Negative examples work better than abstract prohibitions: the model sees
concretely what not to do, and why.

**`unsupported`** - questions the data **cannot** answer. The most important one:
MTTR (mean time to resolution). Our table has `start` and `sla_ticket`, but
**no** resolution timestamp. The old code computed "MTTR" as the difference
`start → sla_ticket`, which is the contractual SLA window, not the repair time.
It was a false number with a correct-sounding name.

> A good agent says "I don't know". An agent that silently approximates is more
> dangerous than one that crashes.

### 3.2 `semantic_layer.py` - loading and validation

Turns the YAML into pydantic objects. Two things to understand:

**Validation at startup (fail fast).**
```python
@model_validator(mode="after")
def validate_references(self) -> "SemanticLayer":
    for name, group in self.groups.items():
        if group.column not in self.columns:
            raise ValueError(f"group '{name}' references unknown column '{group.column}'")
```
If someone misspells a column name in the YAML, the application **does not
start**. The alternative is finding out three days later, from a wrong report.
The principle is called *fail fast*: fail as early and as loudly as possible.

**Two rendering functions.**
- `render_core_instruction()` - short text that goes into the prompt on every request.
- `render_topic(topic)` - long text, delivered on demand through `describe_schema`.

**`@lru_cache`** on the loader: the file is read once, not on every request. The
YAML does not change at runtime.

### 3.3 `prompt.py` - the generated instruction

```python
_SEMANTIC_CONTEXT = load_semantic_layer().render_core_instruction()

TICKETING_MASTER_INSTRUCTIONS = f"""You are a senior network operations analyst...
...
{_SEMANTIC_CONTEXT}
"""
```

The behavioural part (how it answers, what tone, what tool order) is written by
hand. The schema part is **generated**. We never edit the schema in the prompt
again.

Note that this runs at **import time**, not per request: the cost is paid once,
when the application starts.

### 3.4 `data_tools.py` - typed tools

Four tools. What each represents:

**`describe_schema(topic)`** - documentation on demand. The model calls
`describe_schema('values')` and gets the list of enum values. Without it, we
would have to send everything in every prompt.

**`lookup_column_values(column, search_term)`** - translates the user's
vocabulary into real values:

```
user: "link down"  →  lookup  →  exact_match: "Link Down", 43 tickets
user: "Berlin"     →  lookup  →  matches: [], "tell the user, do not guess"
```

The implementation searches in three steps: exact match → substring → fuzzy
(`difflib.get_close_matches`, which compares how similar two strings are).

Why this matters: the alternative was putting all values in the prompt. We have
51 subjects, 80 locations, 150 network elements. In a real database you have
tens of thousands. They do not fit, and they would go stale anyway.

**`get_ticket(ticket_number)`** - one ticket, one fixed query.

**`run_metric(metric_name, ...filters)`** - the heart of determinism.

```python
query, params, applied = build_metric_query(metric_name, supplied, limit)
connection.execute(text(query), params)
```

Note that the values never enter the SQL text. We build **bound parameters**:

```python
clauses.append(f"AND {prefix}{spec.column} = :{name}")   # the SQL gets :loc_identifier
params[name] = value                                      # the value travels separately
```

The database driver receives the query and the values separately. A value cannot
"escape" its position and become SQL code. This is the standard defence against
**SQL injection** - and we have a test for it:

```python
def test_metric_filters_are_bound_not_interpolated():
    sql_query, params, _ = build_metric_query(
        "top_resolutions", {"loc_identifier": "DZR1Y'; DROP TABLE ticket_data --"}
    )
    assert "DROP" not in sql_query
```

Watch out for a subtlety: **column names cannot be bound parameters** (SQL does
not allow it). That is why a column name always comes from the YAML, never from
what the model wrote - see `_assert_known_column` in `value_index.py`. The
general rule: *bind the values, allowlist the identifiers*.

Why `run_metric` instead of free SQL: same question → same SQL → same answer.
It does not depend on what the model feels like generating today. Free SQL
remains for ad-hoc questions you cannot anticipate.

### 3.5 `value_index.py` - the real values, cached

Keeps track of which values actually exist in the database. Three mechanisms:

**TTL cache** (time to live):
```python
cached = _distinct_values_cache.get(column)
if cached and cached[0] > time.monotonic():
    return cached[1]
```
Values are re-read every 10 minutes (`VALUE_CACHE_TTL_SECONDS`). The ticket table
changes far more slowly than the agent is queried.

**Failure cooldown**: if the database does not respond, we remember the failure
for 30 seconds instead of retrying for every column of every query. Without it,
with the database down, each question waited through three connection timeouts.

**Graceful degradation** (*fail-soft*):
```python
except SQLAlchemyError as error:
    logger.warning("Could not index values for column '%s', guard runs on declared values only")
```
If the value index is unavailable, the guard continues with the values declared
in the YAML instead of blocking the conversation. The principle: an auxiliary
component that fails should degrade functionality, not stop it.

### 3.6 `backend/core/sql_safety.py` - real read-only

Here is a security lesson worth learning properly, once.

The old validation:
```python
BLACKLIST_SQL_COMMANDS = ["DROP", "DELETE", "TRUNCATE"]
if value.split()[0] in BLACKLIST_SQL_COMMANDS:
    raise ValueError("Query is not permitted")
```

What gets through it:
- `SELECT 1; DROP TABLE ticket_data` - the first word is `SELECT`
- `UPDATE ticket_data SET ...` - `UPDATE` is not even on the list
- `SELECT * FROM ticket_data INTO OUTFILE '/tmp/leak.csv'` - writes to disk
- `SELECT SLEEP(300)` - holds a connection hostage

> General security rule: **a blacklist is always incomplete**. You enumerate what
> you know is dangerous; the attacker uses what you did not enumerate. The
> correct approach is an allowlist: define what is permitted and reject the rest.

The new version parses the query with `sqlglot` and gets an **AST** (Abstract
Syntax Tree - the syntactic tree of the statement). On a tree you can ask
questions the text cannot answer:

```python
statements = sqlglot.parse(sql_query, dialect="mysql")
if len(statements) > 1:                          # stacked statements
    raise UnsafeSQLError(...)
if not isinstance(expression, READ_ONLY_ROOTS):  # the root must be a SELECT
    raise UnsafeSQLError(...)
for node in statement.walk():                    # anywhere in the tree
    if isinstance(node, FORBIDDEN_NODES):        # INSERT/UPDATE/DROP/INTO OUTFILE...
        raise UnsafeSQLError(...)
```

`walk()` traverses the whole tree, so it also catches a `DROP` hidden inside a
subquery, not just at the start.

`enforce_limit()` adds or caps `LIMIT`, again on the tree. An unbounded query can
return a million rows and fill the process memory.

The file lives in `backend/core/` because **every** agent that runs SQL uses it,
not just ticketing.

### 3.7 `sql_guard.py` - semantic validation

`sql_safety` answers "is this safe?". `sql_guard` answers "does this mean what
the user asked?". Four checks:

**1. Allowed tables** - only `ticket_data`. Radio inventory questions belong to
`radio_agent`.

**2. Existing columns** - catches exactly the bugs we had (`solution_date`,
`end`, `region`). Implementation subtlety: you also have to accept the aliases
the query defines itself:
```sql
SELECT COUNT(*) AS ticket_count FROM ticket_data ORDER BY ticket_count DESC
                   -- ^ defined here       -- ^ used here, not a real column
```
That is what `_collect_aliases()` is for. Without it, the guard would reject
perfectly valid queries - a **false positive**, which is just as bad as a leak,
because the agent would become unusable.

**3. LIKE on exact columns** - `loc_identifier LIKE '%DZR%'` is rejected, with a
suggestion to use `lookup_column_values`.

**4. A structured value inside free text** - the check that solves the "Berlin"
problem. The logic:

```python
for predicate in statement.find_all(exp.EQ, exp.NEQ, exp.Like, exp.ILike, exp.In):
    # ...only for free_text columns
    for literal in _literals(predicate):
        owner = value_owners.get(_canonical(literal))   # '%DZR1Y%' → 'dzr1y'
        if owner:
            raise UnsafeSQLError(f"... Filter on {owner_column} = '{canonical_value}' instead.")
```

In short: if the text being searched in `description` is a real value of a
structured column, it is almost certainly a mapping mistake. If it is **not**
("fiber splice"), it is a legitimate text search and it passes.

Note that we never ask the model what it meant - we infer it from the data. That
is why the check works even when the model is convinced it is right.

The rejection message is phrased to be **actionable**: not "invalid query", but
"filter on `loc_identifier = 'DZR1Y'`". The model reads the message and corrects
itself.

### 3.8 `callbacks.py` - where it all plugs into ADK

ADK offers `before_tool_callback`: a function called **before** every tool.

```python
def validate_sql_before_execution(tool, args, tool_context) -> Optional[dict]:
    if tool.name != "send_sql_command":
        return None                      # other tools, not our business
    try:
        guarded_query = guard_sql(args.get("sql_query", ""))
    except UnsafeSQLError as error:
        return SQLCommandResult.failure(...).model_dump()   # <- replaces the call
    if guarded_query != sql_query:
        args["sql_query"] = guarded_query                   # <- rewrites the arguments
    return None                                             # <- let the call proceed
```

The contract, which is easy to miss:

| What you return | What happens |
|---|---|
| `None` | the tool executes normally |
| a `dict` | the tool does **not** execute; the dict becomes its result |
| mutate `args` instead | the tool executes with the modified arguments |

We use all three: reject (dict), rewrite the `LIMIT` (mutate `args`), or let it
through (`None`).

Why we return an error result instead of raising: the agent receives the error as
a tool response, reads it and retries **in the same turn**. An exception would
break the conversation.

### 3.9 `tools.py` - report, chart, Excel

Here we did not change the architecture, we hardened the details that break in
production:

- **Markdown escaping**: a value containing `|` broke the report table.
- **Sanitised filename**: the model picks the Excel export name. If it picks
  `../../something`, we reduce it to `something.xlsx`. Never let a
  model-generated name reach a path directly - that is *path traversal*.
- **Valid sheet name**: Excel rejects `[]:*?/\` and anything over 31 characters.
- **Non-numeric values**: MySQL returns `COUNT(*)` as `Decimal`, sometimes as
  `str`. `pd.to_numeric(..., errors="coerce")` converts them before plotting.
- **`plt.close(fig)` in `finally`**: matplotlib keeps figures in memory until you
  close them explicitly. In a server running for weeks, that is a memory leak.

### 3.10 `backend/tests/test_ticketing_master.py`

15 tests that run **without a database and without an API key**. That is
deliberate: everything deterministic must be testable offline, otherwise nobody
runs the tests.

The two categories that matter:

```python
def test_valid_queries_are_not_blocked():              # false positives
def test_structured_value_in_free_text_is_blocked():   # the detection itself
```

A guard that rejects everything is "safe" and useless. Always test both
directions.

Two ways to run it:
```bash
python -m pytest backend/tests/test_ticketing_master.py
python backend/tests/test_ticketing_master.py        # without pytest installed
```

### 3.11 `eval/ticketing_master.evalset.json`

Tests verify the **code**. Evals verify the **model's behaviour**: given a
prompt, does it call the right tools and answer correctly?

```json
{
  "eval_id": "location_uses_loc_identifier",
  "conversation": [{
    "user_content": { "parts": [{ "text": "What is the most common resolution for the tickets on site DZR1Y?" }] },
    "intermediate_data": {
      "tool_uses": [{ "name": "run_metric", "args": { "metric_name": "top_resolutions", "loc_identifier": "DZR1Y" } }]
    },
    "final_response": { "parts": [{ "text": "The most frequent resolution category..." }] }
  }]
}
```

`tool_uses` is the **expected trajectory** - which tools should be called, in
what order, with what arguments. ADK compares the real trajectory against it.

Running it:
```bash
adk eval backend/network_agent/sub_agents/ticketing_master \
         backend/network_agent/sub_agents/ticketing_master/eval/ticketing_master.evalset.json
```

It needs a model and a running database. Run it after every change to the YAML.

> Without evals you cannot say "I improved the agent", only "it feels better to
> me". That is the difference between engineering and impression.

So it can be evaluated in isolation, `__init__.py` also exposes the agent as
`root_agent` - the name ADK looks for when loading an agent module.

---

## 4. The full flow of a question

Let us follow "What is the most common resolution for link down problems in
region DZR1Y?":

```
1. root_agent receives the question
   -> root-skill says: tickets = ticketing_master
   -> delegates (AgentTool)

2. ticketing_master reads the instruction (already in context)
   -> concept map: "region" -> loc_identifier ✓
   -> concept map: "link down" -> subject ✓

3. lookup_column_values(column="subject", search_term="link down")
   -> exact_match: "Link Down"

4. run_metric(metric_name="top_resolutions",
              subject="Link Down",
              loc_identifier="DZR1Y")
   -> build_metric_query() composes SQL from the YAML + bound parameters
   -> execution
   -> rows

5. generate_report(...)  +  generate_chart(chart_type="pie", ...)
   -> artifacts: ticket_report.md, ticket_chart.png

6. Final answer, which also states the filters that were applied
```

And if at step 4 the model had chosen wrong free SQL instead:

```
4'. send_sql_command("SELECT ... WHERE description LIKE '%DZR1Y%'")
    -> before_tool_callback -> guard_sql() -> UnsafeSQLError
    -> the tool does NOT execute
    -> the model receives: "'DZR1Y' is a value of the 'loc_identifier' column...
       Filter on loc_identifier = 'DZR1Y' instead."
    -> retries correctly, in the same turn
```

That is the difference between "we hope the model follows the prompt" and "we
know it cannot not follow it".

---

## 5. The token budget

Everything in the instruction is sent on **every** request. So the instruction is
the most expensive part of an agent. Our strategy:

**Always in the prompt (~1,400 tokens):**
- one line per column (`hint`, not `description`)
- the concept map
- the 11 rules
- only the **names** of the metrics

**Loaded on demand:**
- `describe_schema('values')` - the enum values
- `describe_schema('examples')` - the few-shot examples
- `describe_schema('metrics')` - the metric parameters
- SKILL.md - the analysis playbooks, loaded by `SkillToolset` only when the model
  considers the skill relevant (this is called **progressive disclosure**)

**Never in the prompt:**
- the metric SQL (it lives in the YAML and runs in code)
- the distinct column values (fetched with `lookup_column_values`)
- large result sets (capped at `MAX_ROWS = 20`; the rest is saved as an artifact)

### Prompt caching

Model providers (Gemini included) can reuse a prompt prefix if it is
**identical** between requests. That is why the instruction is generated once, at
import time, and contains nothing dynamic - no current date, no ticket count,
nothing that changes.

> If you put `datetime.now()` in the instruction, the prefix differs on every
> request and you lose the entire caching benefit. It is an easy mistake to make
> and a hard one to notice.

### Why the skill does not hold the critical rules

ADK loads a skill only when the model decides it is relevant. That is excellent
for optional methodology ("how do I do a recurrence analysis"), but **dangerous**
for rules - if the model does not load the skill, the rule simply does not exist
in its context.

The split we use:
- **instruction** = what it must never get wrong (schema, rules),
- **skill** = what is occasionally useful (playbooks, report style).

---

## 6. Other small decisions, with their reasons

**`temperature = 0`** - temperature controls how "creative" the model is. For
text-to-SQL you want zero creativity: same question, same SQL.
```python
generate_content_config=types.GenerateContentConfig(temperature=settings.MODEL_TEMPERATURE)
```

**`MAX_ROWS = 20` vs `MAX_SQL_LIMIT = 500`** - two different limits:
- `MAX_SQL_LIMIT`: how much the database may return (protects the server)
- `MAX_ROWS`: how much the model sees (protects the context and the cost)

The remaining rows are saved as a JSON artifact, and the result explicitly says
`truncated: true` plus how many rows exist. Before, the truncation was
**silent** - the model reported 20 rows as if they were all of them.

**`SQLCommandResult` with new fields** (`row_count`, `truncated`, `artifact`,
`sql_query`) - a tool result should say not only *what* it found, but also *how*.
Returning `sql_query` means the model can quote in the report exactly what ran.

**`send_sql_command` catches validation errors** - before, a rejected query
raised `ValidationError` and broke the conversation. Now it becomes an error
result the agent can correct.

---

## 7. How to change something (recipes)

**I want to add a new column to the table:**
1. `db_models.py` - the column in the SQLAlchemy model
2. `semantic_layer.yaml` - the entry under `columns`, with `hint`, `match`, synonyms
3. `concepts` - if users call it something other than the column name
4. run the tests → the guard accepts it automatically, no code change needed
5. run the evals

**I want to add a metric:**
1. `semantic_layer.yaml`, `metrics` section, with `{filters}` after `WHERE 1=1`
2. that is all. The name appears in the instruction automatically, and
   `run_metric` can run it.
3. `test_every_metric_builds_valid_sql` checks it automatically across all filter
   combinations
4. add a case to the eval set

**I want a new rule:**
1. `rules` in the YAML. If it is only a recommendation, you are done.
2. If it must be guaranteed, write the check in `sql_guard.py` and set
   `enforced_by` in the YAML.
3. Test both directions: what must be blocked **and** what must not be.

---

## 8. Common mistakes to avoid

1. **Writing the schema in the prompt "just this once".** It becomes a second
   source of truth and diverges. Put it in the YAML.
2. **Believing the prompt is enough.** If a rule really matters, check it in code.
3. **Putting all distinct values in the prompt.** Fine with 80 locations, not
   with 80,000. Use the lookup.
4. **An over-aggressive guard.** A false positive blocks a real user. Always test
   the correct queries too.
5. **Interpolating values into SQL** (`f"WHERE x = '{value}'"`). Use bound
   parameters. Always.
6. **A column name coming from the model, dropped straight into SQL.**
   Identifiers cannot be parameters, so they must be allowlisted.
7. **Approximating an unanswerable question.** If the data has no MTTR, the
   answer is "I do not have that data", not a number that looks like it.
8. **Dynamic data in the instruction.** It kills prompt caching.

---

## 9. Exercises

For anyone who wants to really get into the code:

1. Add a `tickets_by_creator_area` metric to the YAML and verify, without writing
   a single line of Python, that `run_metric` can run it.
2. Write a query that tries to list all tables in the database. See which layer
   stops it, and why.
3. Change `match` on `subject` from `exact` (with `allow_like: true`) to `exact`
   without `allow_like`. Run the tests. Which test fails, and why?
4. Find, in `sql_guard.py`, why a query with `SELECT ... AS x ... ORDER BY x` is
   not rejected even though `x` is not a real column.
5. Stop the database and ask the agent a question. Watch in the logs how the
   guard degrades and what message the user receives.

---

## 10. One-sentence recap

The database schema lives in a single YAML file; from it we generate the
instruction (small and stable), serve the details on demand, build the
deterministic metrics and validate the model's SQL before execution - so that
consistency comes from code, not from hope.
