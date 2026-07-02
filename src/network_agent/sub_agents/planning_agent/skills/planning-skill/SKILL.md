---
name: planning-skill
description: Generates free loopback IP addresses from a subnet using mandatory MySQL lookup and deterministic IP computation.
---

# Overview

This skill allocates free loopback IP addresses from a given subnet.

It is fully automated and MUST use tools for all data retrieval.

The model MUST NOT ask the user for database information under any circumstance.

---

# Core Rules (CRITICAL)

- You MUST use tools to retrieve all used loopback IPs.
- You MUST NOT ask the user for IP addresses.
- You MUST NOT assume, infer, or hallucinate any IP data.
- You MUST execute tools in the correct order.
- If a tool is required, it MUST be called before proceeding.

---

# Input validation rules

- `subnet` MUST be a valid CIDR (example: 18.197.124.0/24)
- If subnet is invalid:
  - STOP
  - ask user for a valid CIDR
- Do NOT attempt to fix or guess invalid subnets

---

# Tools

## send_sql_command(sql_query: str)

MANDATORY TOOL.

Executes a MySQL query and returns all used loopback IPs.

If results exceed limits, it stores the full dataset in an artifact.

YOU MUST call this tool before calculating IP availability.

Never ask the user for database values.

---

## calculate_free_ips(
    number_of_addresses,
    subnet,
    used_loopback_ips
)

Computes free IP addresses in the given subnet.

- Automatically uses artifact data if available
- Otherwise uses `used_loopback_ips` from `send_sql_command`

DO NOT manually compute IP availability outside this tool.

---

# Database Schema

Table: `dev_radio_data`

Column:
- `loop_ip` (TEXT)

---

# Execution Flow (STRICT ORDER)

## 1. Extract inputs

From the user request extract:

- subnet
- number_of_addresses

If missing → ask user.

---

## 2. Retrieve used IPs (MANDATORY STEP)

You MUST generate and execute this SQL query:

```sql
SELECT loop_ip
FROM dev_radio_data
WHERE loop_ip IS NOT NULL;
```

Then call:

send_sql_command(sql_query)

DO NOT skip this step.
DO NOT ask user for IP data.

---

## 3. Compute free IPs

Call:

calculate_free_ips(
    number_of_addresses=number_of_addresses,
    subnet=subnet,
    used_loopback_ips=result_from_sql
)

---

## 4. Return result

Return the list of free IPs.

If fewer IPs are available than requested:
- return all available IPs
- explicitly mention the shortage

---

# Important Behavior Constraints

- Never ask the user for IPs
- Never assume DB contents
- Always call send_sql_command first
- Always use tool outputs or artifacts
- Never compute availability manually in the model