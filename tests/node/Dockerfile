# Disposable Linux host fixture; its Docker daemon never uses the runner socket.
FROM debian:trixie-slim
ENV container=docker
RUN apt-get update && apt-get install -y --no-install-recommends systemd systemd-sysv dbus openssh-server ca-certificates && rm -rf /var/lib/apt/lists/*
STOPSIGNAL SIGRTMIN+3
CMD ["/sbin/init"]
