---
name: radio-skill
description: Converts natural language requests related to radio network elements into SQL queries for database interactions.
---

## Overview
The **radio-skill** skill enables an agent to transform user-provided natural language questions or instructions related to radio network elements into executable SQL queries.  
It is responsible for understanding intent, mapping it to the database schema, generating safe and valid SQL, and optionally executing the query via the provided tool.

This skill is especially useful for:
- Network Elements data exploration
- Ad-hoc queries on radio network elements

---

## Tools
* `send_sql_command(sql_query: str)`  
  Sends the SQL query to the database and returns the result.
---

## Database Schema
The current schema exposed to this skill includes the table below.

### Table: `dev_radio_data`
| Column | Type | Description |
|---|---|---|
| `id` | `int` | Unique row identifier. |
| `ne_name` | `text` | Network element name (for example `ne1`, `ne2`). |
| `lte_ip` | `text` | LTE interface IP address for the network element. |
| `gsm_ip` | `text` | GSM interface IP address for the network element. |
| `5g_ip` | `text` | 5G interface IP address for the network element. |
| `loop_ip` | `text` | Loopback IP address for the network element. |
| `ike_peer` | `text` | IKE peer identifier (for example `sgw1`, `sgw2`). |
| `enodeb_id` | `int` | eNodeB identifier associated with the network element. |
| `gnodeb_id` | `int` | gNodeB identifier associated with the network element. |


### Notes for SQL generation
- Primary source table for this skill is ``dev_radio_data``.
- IP-related user requests may target one or more of: `lte_ip`, `gsm_ip`, `5g_ip`, `loop_ip`.
- Node-ID requests should map to `enodeb_id` (4G/LTE) and `gnodeb_id` (5G).
- Peer-related (IKE - Internet Key Exchange) filters should use `ike_peer`.

### Example query patterns
```sql
SELECT ne_name, lte_ip, gsm_ip, "5g_ip", loop_ip
FROM ne_data
WHERE ne_name = 'ne1'
LIMIT 1;
```

```sql
SELECT ne_name, enodeb_id, gnodeb_id
FROM ne_data
WHERE ike_peer = 'sgw2'
LIMIT 100;
```

---

## Responsibilities
The `radio_agent` agent using this skill must:

1. **Understand user intent**
   - Parse the natural language input
   - Identify entities (tables, columns, filters, aggregations) based on attached dB schema
   - Infer relationships if needed

2. **Generate valid SQL**
   - Construct syntactically correct SQL queries
   - Ensure compatibility with the target database dialect (if known)

3. **Ensure safety**
   - Avoid destructive operations (e.g., `DROP`, `DELETE`, `TRUNCATE`, `UPDATE`) unless explicitly required and allowed
   - Prefer read-only queries (`SELECT`)
   - Prevent SQL injection risks by not blindly trusting input

4. **Optimize queries**
   - Use appropriate filters (`WHERE`)
   - Limit results when necessary (`LIMIT`)
   - Avoid unnecessary joins or subqueries

5. **Execute queries when appropriate**
   - Use `send_sql_command` to run the query
   - Return results in a clear and structured format
   - By default, after generating the SQL, execute it and return the data (unless the user explicitly asks for SQL-only output)

---

## End-to-End Execution Flow
1. Parse the user request in natural language.
2. Map intent to the ``dev_radio_data`` schema and generate SQL.
3. Validate the SQL for safety and correctness.
4. Call `send_sql_command(sql_query)`.
5. Return the tool output to the user as the final answer (rows, empty result, or execution error).

---

## Output Format

### When generating SQL only:
```sql
SELECT column1, column2
FROM table_name
WHERE condition
LIMIT 100;
```

### When executing and returning data (default):
1. Generated SQL query
2. Tool call: `send_sql_command(sql_query)`
3. Final response with returned data in a concise, readable table or list

