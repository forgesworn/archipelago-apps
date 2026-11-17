#!/usr/bin/env python3
"""Apply an atomic egress guard inside the rootless Wildbloom container only.

Run as the Podman owner, including from the Quadlet service's ExecStartPost.
Requires host nftables, nsenter and Podman. Never edits the host firewall.
"""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import subprocess


def run(*args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, text=True, **kwargs).stdout


def render(config):
    if not isinstance(config, dict) or set(config) != {'dns_servers', 'blocked_hosts'}:
        raise ValueError('expected dns_servers and blocked_hosts')
    addresses = {}
    for key in config:
        if not isinstance(config[key], list) or not config[key]:
            raise ValueError(f'{key} must be a nonempty list of bare IP addresses')
        addresses[key] = []
        for value in config[key]:
            if not isinstance(value, str) or '%' in value:
                raise ValueError('expected bare IP addresses')
            addresses[key].append(ipaddress.ip_address(value))
    rules = [
        'add table inet wildbloom_egress',
        'flush table inet wildbloom_egress',
        'table inet wildbloom_egress {',
        ' chain output {',
        '  type filter hook output priority 10; policy accept;',
        '  ct direction reply ct state { established, related } counter accept',
        # Health checks use loopback. Rootless port forwarding also opens a
        # connection to this namespace's own bridge address on the app port.
        '  fib daddr type local tcp dport 3742 counter accept',
    ]
    for ip in addresses['dns_servers']:
        family = 'ip' if ip.version == 4 else 'ip6'
        for protocol in ('tcp', 'udp'):
            rules.append(f'  {family} daddr {ip} {protocol} dport 53 counter accept')
    for ip in addresses['blocked_hosts']:
        family = 'ip' if ip.version == 4 else 'ip6'
        rules.append(f'  {family} daddr {ip} counter reject with icmpx type admin-prohibited')
    rules.extend([
        '  fib daddr type local counter reject with icmpx type admin-prohibited',
        '  ip daddr { 0.0.0.0/8, 10.0.0.0/8, 100.64.0.0/10, 127.0.0.0/8, 169.254.0.0/16, 172.16.0.0/12, 192.0.0.0/24, 192.0.2.0/24, 192.88.99.0/24, 192.168.0.0/16, 198.18.0.0/15, 198.51.100.0/24, 203.0.113.0/24, 224.0.0.0/3 } counter reject with icmpx type admin-prohibited',
        '  meta nfproto ipv6 ip6 daddr != 2000::/3 counter reject with icmpx type admin-prohibited',
        '  ip6 daddr { 2001::/32, 2001:db8::/32, 2002::/16 } counter reject with icmpx type admin-prohibited',
        '  counter accept',
        ' }',
        '}',
        '',
    ])
    return '\n'.join(rules)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--container', default='wildbloom-node')
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error('run as the rootless Podman owner')
    policy = render(json.loads(args.config.read_text()))
    state = json.loads(run('/usr/bin/podman', 'inspect', args.container))[0]
    pid = state['State']['Pid']
    if not state['State']['Running'] or type(pid) is not int or pid <= 1:
        raise RuntimeError('container is not running')
    namespace = Path(f'/proc/{pid}/ns/net')
    if namespace.readlink() == Path('/proc/self/ns/net').readlink():
        raise RuntimeError('refusing a host-network container')
    # Podman's user namespace owns the container network namespace. No extra
    # capabilities or tools are granted to the workload itself.
    command = ['/usr/bin/podman', 'unshare', '/usr/bin/nsenter', '-t', str(pid), '-n', '/usr/sbin/nft']
    run(*command, '--check', '-f', '-', input=policy)
    run(*command, '-f', '-', input=policy)
    run(*command, 'list', 'table', 'inet', 'wildbloom_egress')
    print('Wildbloom container egress guard applied')


if __name__ == '__main__':
    main()
