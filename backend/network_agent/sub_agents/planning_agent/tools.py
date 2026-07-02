"""Tools for planning agent"""

import ipaddress


def calculate_free_ips(number_of_addresses: int, subnet: str, used_loopback_ips: list[str]) -> list[str]:
    """
    Return the requested number of free IP addresses from a subnet.

    Args:
        number_of_addresses: Number of free IPs to return.
        subnet: CIDR subnet (e.g. "158.98.202.0/24").
        used_loopback_ips: List of allocated loopback IP addresses.

    Returns:
        A list containing up to number_of_addresses available IP addresses.
    """

    network = ipaddress.ip_network(subnet)
    used_ips = {
        ipaddress.ip_address(ip) for ip in used_loopback_ips
    }

    free_ips = []

    for host in network.hosts():
        if host not in used_ips:
            free_ips.append(str(host))

            if len(free_ips) == number_of_addresses:
                break

    return free_ips