from __future__ import annotations

import pytest

from asterisk_provisioner.include_migration import PjsipIncludeMigration
from asterisk_provisioner.managed_config import ManagedConfig


def prepared(tmp_path, content=b"[8301]\r\ntype=endpoint\r\n") -> PjsipIncludeMigration:
    root = tmp_path / "asterisk"
    (root / "custom").mkdir(parents=True)
    custom = root / "custom" / "pjsip_custom.conf"
    custom.write_bytes(content)
    ManagedConfig(root / "eface").reconcile_file()
    return PjsipIncludeMigration(root)


def test_install_is_persistent_idempotent_and_exactly_reversible(tmp_path) -> None:
    original = b"[8301]\r\ntype=endpoint\r\n"
    migration = prepared(tmp_path, original)
    calls = []
    assert migration.install(lambda: calls.append("reload")) is True
    assert migration.custom.read_bytes() == original + migration.line + b"\n"
    assert migration.backup.read_bytes() == original
    assert migration.install(lambda: calls.append("unexpected")) is False
    assert calls == ["reload"]
    assert migration.rollback(lambda: calls.append("rollback")) is True
    assert migration.custom.read_bytes() == original
    assert migration.rollback(lambda: calls.append("unexpected")) is False
    assert calls == ["reload", "rollback"]


def test_failed_reload_restores_original_and_keeps_backup(tmp_path) -> None:
    migration = prepared(tmp_path, b"existing without newline")
    calls = []

    def fails() -> None:
        calls.append(True)
        if len(calls) == 1:
            raise RuntimeError("reload failed")

    with pytest.raises(RuntimeError, match="reload failed"):
        migration.install(fails)
    assert migration.custom.read_bytes() == b"existing without newline"
    assert migration.backup.read_bytes() == b"existing without newline"
    assert len(calls) == 2


def test_migration_refuses_drift_and_unowned_include(tmp_path) -> None:
    migration = prepared(tmp_path)
    migration.install(lambda: None)
    migration.custom.write_bytes(migration.custom.read_bytes() + b"; local user change\n")
    with pytest.raises(RuntimeError, match="modificato"):
        migration.rollback(lambda: pytest.fail("reload called"))

    another = prepared(tmp_path / "other")
    another.custom.write_bytes(another.custom.read_bytes() + another.line + b"\n")
    with pytest.raises(RuntimeError, match="non gestito"):
        another.install(lambda: pytest.fail("reload called"))


def test_migration_requires_generated_persistent_file(tmp_path) -> None:
    migration = prepared(tmp_path)
    migration.managed.unlink()
    with pytest.raises(RuntimeError, match="e-Face non disponibile"):
        migration.install(lambda: pytest.fail("reload called"))
