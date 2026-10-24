#!/usr/bin/env python3
"""Do not release an install catalogue until its exact image pulls anonymously."""
import json
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

# This is an anonymous registry token; no account credential is read.
coordinates = subprocess.check_output(["bash", "-c", '. ./PINS; . scripts/lib/app-image.bash; app_image spry; echo "$APP_TAG"'], text=True).strip()
repository, tag = coordinates.removeprefix("ghcr.io/").split(":", 1)
query = urllib.parse.urlencode({"service": "ghcr.io", "scope": f"repository:{repository}:pull"})
for attempt in range(40):
    try:
        with urllib.request.urlopen(f"https://ghcr.io/token?{query}", timeout=10) as response:
            token = json.load(response)["token"]
        request = urllib.request.Request(f"https://ghcr.io/v2/{repository}/manifests/{tag}", headers={
            "Authorization": f"Bearer {token}", "Accept": "application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json"})
        with urllib.request.urlopen(request, timeout=10) as response:
            index = json.load(response)
        platforms = {entry.get("platform", {}).get("architecture") for entry in index.get("manifests", [])}
        if {"amd64", "arm64"} <= platforms:
            print("Spry image is public for AMD64 and ARM64.")
            break
    except (urllib.error.URLError, KeyError, ValueError):
        pass
    if attempt == 39:
        raise SystemExit("The exact public Spry image is unavailable; catalogue release withheld.")
    time.sleep(15)
