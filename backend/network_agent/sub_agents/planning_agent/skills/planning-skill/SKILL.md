---
name: planning-skill
description: Generates free loopback IP addresses from a subnet using MySQL lookup and deterministic IP computation.
---

## Overview

The planning-skill allocates free loopback IP addresses from a given subnet.

It performs the following steps:
1. Retrieves already used loopback IPs from a MySQL database
2. Computes available IP addresses inside the subnet
3. Returns the requested number of free IPs

Use this skill whenever the user requests free loopback IP addresses.

---

## Input validation rules

- `subnet` MUST be in CIDR format (example: 18.197.124.0/24)
- If subnet is NOT in CIDR format:
  - do NOT proceed
  - ask user to provide a valid CIDR subnet
- Do NOT attempt to infer or fix invalid subnets

---

## Tools

### send_sql_command(sql_query: str)
Executes a SQL query and returns a list of used loopback IP addresses from the database.

### calculate_free_ips(
    number_of_addresses: int,
    subnet: str,
    used_loopback_ips: list[str]
)
Computes available IP addresses in the given subnet and returns the requested number of free IPs.

---

## Database Schema

Primary table: `dev_radio_data`

Relevant column:
- `loop_ip` (TEXT): loopback IP address

---

## Execution Flow

### 1. Extract input
From the user request, extract:
- `subnet` (CIDR format, e.g. 158.98.202.0/24)
- `number_of_addresses`

If either value is missing, ask the user.

---

### 2. Compute subnet range

Convert the CIDR subnet into:
- `start_ip` → first IP address in the subnet
- `end_ip` → last IP address in the subnet

Example:
- subnet: 158.98.202.0/24
- start_ip: 158.98.202.0
- end_ip: 158.98.202.255

---

### 3. Build SQL query (MySQL-compatible)

Use the following query:

```sql
SELECT loop_ip
FROM dev_radio_data
WHERE loop_ip IS NOT NULL
AND INET_ATON(loop_ip)
BETWEEN INET_ATON('<start_ip>')
AND INET_ATON('<end_ip>');
```
Replace:

<start_ip> with computed start IP
<end_ip> with computed end IP

Ensure SQL is valid and safe before execution.

---

### 4. Call `send_sql_command(sql_query)`. The tool returns the list of allocated loopback IP addresses in the subnet.

---

### 5. Calculate free addresses

Call:

calculate_free_ips(
    number_of_addresses=number_of_addresses,
    subnet=subnet,
    used_loopback_ips=used_loopback_ips
)

where:

subnet is the requested subnet
used_loopback_ips is the result returned by send_sql_command, passed as a list 
number_of_addresses is the number of requested addresses

Do not attempt to calculate free IP addresses yourself.

---

### 6. Return the result

Return the free loopback IP addresses produced by calculate_free_ips.

If fewer addresses are available than requested, clearly state how many addresses are available and return those addresses.




