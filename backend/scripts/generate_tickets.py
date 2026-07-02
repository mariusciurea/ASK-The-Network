"""Generate 1000 diverse network tickets for the CSV data file."""

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)

# --- Configuration ---

TICKET_TYPES = {
    "INM": {"use_case": "Network-Incident", "prefix": "Z_INM", "weight": 50},
    "SRM": {"use_case": "Change-Request", "prefix": "Z_SRM", "weight": 20},
    "NEV": {"use_case": "Network-Event", "prefix": "Z_NEV", "weight": 10},
    "NBL": {"use_case": "Network-Build", "prefix": "Z_NBL", "weight": 10},
    "PRM": {"use_case": "Problem-Management", "prefix": "Z_PRM", "weight": 10},
}

STATUSES_INM = ["Open", "In Progress", "Closed", "Assigned", "Noticed", "Answered"]
STATUSES_CHANGE = ["Open", "In Progress", "Closed", "Assigned", "Noticed"]
STATUS_WEIGHTS_INM = [15, 20, 35, 10, 10, 10]
STATUS_WEIGHTS_CHANGE = [10, 25, 45, 10, 10]

CREATOR_AREAS = [
    "G-RAN-FO-VFRO-ZV",
    "G-RAN-BO-VFRO-ZV",
    "G-IP-OPS",
    "G-CORE-OPS",
    "G-TX-OPS",
    "G-RAN-FO-VFRO-NW",
    "G-RAN-FO-VFRO-SO",
]

ASSIGNEE_AREAS = [
    "G-RAN-FO-VFRO-ZV",
    "G-RAN-BO-VFRO-ZV",
    "G-IP-OPS",
    "G-CORE-OPS",
    "G-TX-OPS",
    "G-RAN-FO-VFRO-NW",
]

SUBJECTS_INM = [
    "Link Down",
    "Störung - RBS - Huawei 4G",
    "Störung - RBS - Ericsson 5G",
    "Störung - RBS - Nokia 3G",
    "Transport Congestion",
    "High CPU Usage",
    "VSWR Alarm",
    "Cell Unavailable",
    "S1 Setup Failure",
    "X2 Link Failure",
    "Power Failure",
    "Temperature Alarm",
    "Packet Loss High",
    "Latency Threshold Exceeded",
    "BTS Out of Service",
    "NodeB Degraded",
    "eNodeB RF Interference",
    "gNodeB Sync Loss",
    "Fiber Cut Detected",
    "Backhaul Degradation",
]

SUBJECTS_SRM = [
    "Software Upgrade - Huawei RAN",
    "Software Upgrade - Ericsson RAN",
    "Hardware Replacement - BBU",
    "Hardware Replacement - RRU",
    "Capacity Expansion - 4G",
    "Capacity Expansion - 5G",
    "Configuration Change - Transport",
    "Configuration Change - Radio",
    "Site Integration - New Build",
    "Antenna Swap",
    "Power System Upgrade",
    "Fiber Re-route",
    "Parameter Optimization",
    "Frequency Re-farming",
]

SUBJECTS_NEV = [
    "Planned Maintenance Window",
    "Network Monitoring Alert",
    "Performance Degradation Detected",
    "Threshold Breach Notification",
    "Automated Recovery Triggered",
]

SUBJECTS_NBL = [
    "New Site Build - Urban",
    "New Site Build - Rural",
    "Tower Installation",
    "Cabinet Installation",
    "Power System Installation",
    "Fiber Connectivity Setup",
]

SUBJECTS_PRM = [
    "Recurring Link Down Analysis",
    "Chronic VSWR Investigation",
    "Systematic Packet Loss Root Cause",
    "Repeated Power Failure Pattern",
    "Intermittent Cell Unavailability",
    "Capacity Planning Review",
]

RESPONSE_SUBJECTS_RESOLVED = [
    "Behoben",
    "Root cause fixed",
    "Issue resolved",
]

RESPONSE_SUBJECTS_OTHER = [
    "No impact confirmed",
    "Monitoring ongoing",
    "Kein Fehler - Ticket zurückgezogen",
    "Escalated to vendor",
    "Workaround applied",
]

RESPONSE_DESCRIPTIONS = [
    "Temporary degradation observed, system self-recovered.",
    "Hardware module reset remotely. Traffic restored without errors.",
    "Network element unreachable briefly; connectivity restored.",
    "Capacity threshold updated to prevent future false alerts.",
    "Signal fluctuation detected; no persistent fault found.",
    "Manual intervention performed: service restarted and stability confirmed.",
    "Intermittent issue mitigated, root cause still under observation.",
    "Issue correlated with planned maintenance. No action needed.",
    "Fiber splice completed, signal restored to normal levels.",
    "Power module replaced on-site, all services operational.",
    "Software patch applied, alarm cleared after restart.",
    "Configuration rollback performed, service normalized.",
    "Antenna realignment completed, coverage restored.",
    "Vendor dispatched for hardware replacement.",
    "Remote reconfiguration applied; monitoring for 24h.",
    "Root cause identified as faulty RRU; replacement scheduled.",
    "No recurrence observed in the last monitoring window.",
    "Additional validation checks completed successfully.",
    "Ticket correlated with parent problem ticket.",
    "Redundancy failover confirmed working; primary link under repair.",
]

DESCRIPTION_TEMPLATES_INM = [
    "RoboNOC ticket for {ne}; detected event: {event}",
    "Automated alarm for {ne}: {event} - immediate action required",
    "NMS alert triggered for {ne}; event: {event}",
    "Monitoring system detected {event} on network element {ne}",
]

DESCRIPTION_TEMPLATES_SRM = [
    "Change request for {ne}: {event}",
    "Planned activity on {ne} - {event}",
    "Scheduled maintenance: {event} on element {ne}",
]

DESCRIPTION_TEMPLATES_PRM = [
    "Problem investigation for recurring {event} on {ne}",
    "Analysis of chronic issue: {event} affecting {ne}",
    "Root cause investigation: {event} - multiple occurrences on {ne}",
]

# Generate realistic network element identifiers
def gen_ne_id():
    prefix = "OXV"
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    suffix = "".join(random.choices(chars, k=4))
    return prefix + suffix


def gen_loc_id():
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(random.choices(chars, k=5))


# Pre-generate a pool of NE IDs (simulate ~150 unique network elements)
NE_POOL = [gen_ne_id() for _ in range(150)]
LOC_POOL = [gen_loc_id() for _ in range(80)]

# Date range: Jan 2026 - June 2026
START_DATE = datetime(2026, 1, 1)
END_DATE = datetime(2026, 6, 30)


def random_date(start, end):
    delta = end - start
    random_seconds = random.randint(0, int(delta.total_seconds()))
    return start + timedelta(seconds=random_seconds)


def format_date(dt):
    return dt.strftime("%-m/%-d/%Y %-H:%M") if hasattr(dt, 'strftime') else ""


def format_date_win(dt):
    """Windows-compatible date formatting."""
    return f"{dt.month}/{dt.day}/{dt.year} {dt.hour}:{dt.minute:02d}"


def generate_sla(start_dt, priority):
    """Generate SLA deadline based on priority."""
    sla_hours = {1: 4, 2: 8, 3: 24, 4: 48, 5: 72}
    hours = sla_hours.get(priority, 24)
    sla_dt = start_dt + timedelta(hours=hours)
    return format_date_win(sla_dt)


def generate_ticket(idx, ticket_type_key):
    """Generate a single ticket row."""
    cfg = TICKET_TYPES[ticket_type_key]
    ticket_num = f"{cfg['prefix']}{200000 + idx:06d}A001"

    ne_id = random.choice(NE_POOL)
    loc_id = random.choice(LOC_POOL)
    creator = random.choice(CREATOR_AREAS)
    assignee = random.choice(ASSIGNEE_AREAS)

    # Subject based on type
    if ticket_type_key == "INM":
        subject = random.choice(SUBJECTS_INM)
        statuses = STATUSES_INM
        weights = STATUS_WEIGHTS_INM
        priority = random.choices([1, 2, 3, 4, 5], weights=[5, 15, 30, 30, 20])[0]
        templates = DESCRIPTION_TEMPLATES_INM
    elif ticket_type_key == "SRM":
        subject = random.choice(SUBJECTS_SRM)
        statuses = STATUSES_CHANGE
        weights = STATUS_WEIGHTS_CHANGE
        priority = random.choices([1, 2, 3, 4, 5], weights=[2, 10, 40, 35, 13])[0]
        templates = DESCRIPTION_TEMPLATES_SRM
    elif ticket_type_key == "NEV":
        subject = random.choice(SUBJECTS_NEV)
        statuses = STATUSES_CHANGE
        weights = STATUS_WEIGHTS_CHANGE
        priority = random.choices([3, 4, 5], weights=[40, 40, 20])[0]
        templates = DESCRIPTION_TEMPLATES_INM
    elif ticket_type_key == "NBL":
        subject = random.choice(SUBJECTS_NBL)
        statuses = STATUSES_CHANGE
        weights = STATUS_WEIGHTS_CHANGE
        priority = random.choices([3, 4, 5], weights=[30, 50, 20])[0]
        templates = DESCRIPTION_TEMPLATES_SRM
    else:  # PRM
        subject = random.choice(SUBJECTS_PRM)
        statuses = STATUSES_INM
        weights = STATUS_WEIGHTS_INM
        priority = random.choices([1, 2, 3, 4], weights=[10, 30, 40, 20])[0]
        templates = DESCRIPTION_TEMPLATES_PRM

    status = random.choices(statuses, weights=weights)[0]

    # Dates
    start_dt = random_date(START_DATE, END_DATE)
    start_str = format_date_win(start_dt)

    # SLA
    sla_str = generate_sla(start_dt, priority)

    # Description
    template = random.choice(templates)
    description = template.format(ne=ne_id, event=subject.lower())

    # Response (only for closed/answered/in progress)
    response_subject = ""
    response_description = ""
    if status in ("Closed", "Answered"):
        response_subject = random.choice(RESPONSE_SUBJECTS_RESOLVED)
        response_description = random.choice(RESPONSE_DESCRIPTIONS)
        if random.random() > 0.5:
            response_description += " " + random.choice(RESPONSE_DESCRIPTIONS)
    elif status == "In Progress":
        if random.random() > 0.3:
            response_subject = random.choice(RESPONSE_SUBJECTS_OTHER)
            response_description = random.choice(RESPONSE_DESCRIPTIONS)

    return {
        "Ticket Number": ticket_num,
        "Status": status,
        "Creator Area": creator,
        "Use Case": cfg["use_case"],
        "Subject": subject,
        "Priority": str(priority),
        "Description": description,
        "Start": start_str,
        "SLA Ticket": sla_str,
        "Network Element Identifier": ne_id,
        "Loc Identifier": loc_id,
        "Assignee Area": assignee,
        "Response Subject": response_subject,
        "Response Description": response_description,
    }


def main():
    total = 1000
    tickets = []

    # Distribute by type weights
    type_keys = list(TICKET_TYPES.keys())
    type_weights = [TICKET_TYPES[k]["weight"] for k in type_keys]

    for i in range(total):
        ticket_type = random.choices(type_keys, weights=type_weights)[0]
        tickets.append(generate_ticket(i, ticket_type))

    # Sort by start date
    tickets.sort(key=lambda t: t["Start"])

    # Write CSV
    output_path = Path(__file__).parent.parent / "data" / "network_tickets_diverse_resolution.csv"
    fieldnames = [
        "Ticket Number", "Status", "Creator Area", "Use Case", "Subject",
        "Priority", "Description", "Start", "SLA Ticket",
        "Network Element Identifier", "Loc Identifier", "Assignee Area",
        "Response Subject", "Response Description",
    ]

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(tickets)

    print(f"Generated {len(tickets)} tickets -> {output_path}")

    # Print stats
    from collections import Counter
    type_counts = Counter(t["Use Case"] for t in tickets)
    status_counts = Counter(t["Status"] for t in tickets)
    print("\nBy Use Case:")
    for k, v in type_counts.most_common():
        print(f"  {k}: {v}")
    print("\nBy Status:")
    for k, v in status_counts.most_common():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
