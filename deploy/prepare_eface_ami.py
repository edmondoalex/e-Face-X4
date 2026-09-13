"""Prepare a persistent, dedicated AMI user without changing live Asterisk.

The existing generated manager.conf is preserved byte-for-byte before the new
account is appended. This script never prints passwords or file contents.
"""

from __future__ import annotations

import argparse
import os
import secrets
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asterisk-config", required=True, type=Path)
    parser.add_argument("--eface-ip", required=True)
    parser.add_argument("--secret-file", required=True, type=Path)
    args = parser.parse_args()

    import ipaddress

    address = ipaddress.ip_address(args.eface_ip)
    if address.version != 4 or not address.is_private:
        raise SystemExit("e-Face IP must be a private IPv4 address")
    root = args.asterisk_config.resolve()
    if root.name != "asterisk" or not (root / "default" / "manager.conf").is_file() or not (root / "custom").is_dir():
        raise SystemExit("Unexpected Asterisk configuration directory")
    generated = root / "default" / "manager.conf"
    custom = root / "custom" / "manager.conf"
    if custom.exists() or args.secret_file.exists():
        raise SystemExit("Existing custom manager config or secret file: refusing to overwrite")
    original = generated.read_bytes()
    if b"[general]" not in original or b"[admin]" not in original or b"[eface]" in original:
        raise SystemExit("Unexpected generated manager.conf: refusing to install")

    secret = secrets.token_urlsafe(36)
    suffix = (
        f"\n; Dedicated e-Face provisioning account. Do not grant command/originate.\n"
        f"[eface]\n"
        f"secret = {secret}\n"
        f"deny = 0.0.0.0/0.0.0.0\n"
        f"permit = {address}/255.255.255.255\n"
        f"read = config\n"
        f"write = config\n"
        f"writetimeout = 5000\n"
    ).encode("ascii")
    args.secret_file.parent.mkdir(parents=True, exist_ok=True)
    temporary_secret = args.secret_file.with_suffix(args.secret_file.suffix + ".tmp")
    temporary_config = custom.with_suffix(".conf.tmp")
    try:
        with temporary_secret.open("xb") as stream:
            os.chmod(temporary_secret, 0o600)
            stream.write(secret.encode("ascii"))
            stream.flush()
            os.fsync(stream.fileno())
        with temporary_config.open("xb") as stream:
            stream.write(original.rstrip(b"\r\n") + b"\n" + suffix)
            stream.flush()
            os.fsync(stream.fileno())
        temporary_config.replace(custom)
        temporary_secret.replace(args.secret_file)
    finally:
        temporary_config.unlink(missing_ok=True)
        temporary_secret.unlink(missing_ok=True)
    print(f"Prepared {custom}; dedicated secret saved at {args.secret_file}; no Asterisk restart performed")


if __name__ == "__main__":
    main()
