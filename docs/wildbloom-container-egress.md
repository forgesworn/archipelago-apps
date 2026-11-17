# Rootless Wildbloom egress guard

The hardened package retains mirror refusal and validates public fetch destinations. A second layer can restrict the container network namespace. Do not filter the host UID: all rootless Archy apps share it.

Install `scripts/guard-wildbloom-container.py` as `/usr/local/libexec/guard-wildbloom-container.py`. As the Podman owner, create a private JSON config, for example `/home/archipelago/.config/wildbloom-egress.json`:

```json
{"dns_servers":["10.89.0.1"],"blocked_hosts":["203.0.113.1"]}
```

Use the container's actual resolver IPs and every public IP belonging to the node; the example host is a documentation address. Keep these updated if host addresses change. No private payment endpoint is allowed by this policy; review exact address/port exceptions before using a private issuer or Lightning service.

Add a persistent Quadlet drop-in `~/.config/containers/systemd/wildbloom-node.container.d/egress.conf`:

```ini
[Service]
ExecStartPost=/usr/bin/python3 /usr/local/libexec/guard-wildbloom-container.py --config /home/archipelago/.config/wildbloom-egress.json
```

Reload the user manager and restart the service during a backed-up upgrade. Verify the table after restart with `podman unshare nsenter -t <container-host-pid> -n /usr/sbin/nft list table inet wildbloom_egress`. Confirm existing reads, uploads, checkout discovery, issuer access, DNS and health before considering the upgrade complete. A failing ExecStartPost fails service startup. This post-start layer is applied after the process starts; application destination validation remains necessary during that interval. The container retains dropped capabilities, read-only root and no-new-privileges.

Only responses to incoming connections, localhost TCP 3742 health checks, configured DNS port 53 and public destinations are allowed. Private, loopback, link-local, metadata, reserved and node-owned public addresses are blocked for new outbound connections. The atomic batch only replaces its own table inside this container. Other applications and the host firewall are untouched. Reapplying the hook is safe.

Before installing, rehearse in a disposable container with the same rootless network. Prove blocked destinations with listening synthetic fixtures and check public TCP, DNS over UDP/TCP and replies to incoming connections. Preserve the container volume and payment ledger using the offline backup procedure in `wildbloom-upgrade.md`.
