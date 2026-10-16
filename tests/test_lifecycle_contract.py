"""Regression tests for lifecycle and public identity."""
from __future__ import annotations

import ast
import asyncio
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).parents[1]
INTEGRATION = ROOT / "custom_components" / "dahua_access_listener"


def source() -> str:
    return (INTEGRATION / "__init__.py").read_text(encoding="utf-8")


def unload_function():
    tree = ast.parse(source())
    node = next(item for item in tree.body if isinstance(item, ast.AsyncFunctionDef) and item.name == "async_unload_entry")
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {"DOMAIN": "dahua_access_listener", "_PLATFORMS": ["sensor", "lock"], "HomeAssistant": object, "ConfigEntry": object}
    exec(compile(module, "<unload>", "exec"), namespace)
    return namespace["async_unload_entry"]


def test_manifest_identity_and_real_documentation_are_stable():
    manifest = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["domain"] == "dahua_access_listener"
    assert manifest["name"] == "Dahua Access Reader"
    assert manifest["version"] == "2.0.0"
    assert manifest["documentation"] == "https://github.com/edmondoalex/dahua_access_listener"
    assert manifest["iot_class"] == "local_push"


def test_hacs_metadata_matches_runtime_domain():
    for path in (ROOT / "hacs.json", INTEGRATION / "hacs.json"):
        metadata = json.loads(path.read_text(encoding="utf-8"))
        assert metadata["name"] == "Dahua Access Reader"
        assert "domain" not in metadata


def test_setup_forwards_both_platforms_and_registers_service_once():
    tree = ast.parse(source())
    text = ast.unparse(tree)
    assert '_PLATFORMS = [\'sensor\', \'lock\']' in text
    assert "async_forward_entry_setups(entry, _PLATFORMS)" in text
    assert 'has_service(DOMAIN, "open_relay")' in source()
    assert 'async_register(DOMAIN, "open_relay"' in source()
    assert 'current["open_relay"]' in source()


def test_unload_is_idempotent_and_cleans_listener_coordinator_and_service():
    text = source()
    assert "if entry_data is None:" in text and "return True" in text
    assert "async_unload_platforms(entry, _PLATFORMS)" in text
    assert 'entry_data["stop_event"].set()' in text
    assert "response.close()" in text
    assert 'async_remove(DOMAIN, "open_relay")' in text
    assert "hass.data.pop(DOMAIN, None)" in text


def test_unload_runtime_behavior_and_double_unload():
    class Stop:
        called = False
        def set(self): self.called = True
    class Response:
        closed = False
        def close(self): self.closed = True
    class Services:
        present = True
        removed = []
        def has_service(self, domain, service): return self.present
        def async_remove(self, domain, service): self.removed.append((domain, service)); self.present = False
    class Entries:
        calls = []
        async def async_unload_platforms(self, entry, platforms): self.calls.append(tuple(platforms)); return True
    class Hass: pass
    class Entry: entry_id = "entry-1"
    stop, response, hass = Stop(), Response(), Hass()
    hass.services, hass.config_entries = Services(), Entries()
    hass.data = {"dahua_access_listener": {"entry-1": {"stop_event": stop, "runtime": {"response": response}}}}
    unload = unload_function()
    assert asyncio.run(unload(hass, Entry())) is True
    assert stop.called and response.closed
    assert hass.config_entries.calls == [("sensor", "lock")]
    assert hass.services.removed == [("dahua_access_listener", "open_relay")]
    assert "dahua_access_listener" not in hass.data
    assert asyncio.run(unload(hass, Entry())) is True


def test_entity_unique_ids_and_service_name_are_unchanged():
    sensor = (INTEGRATION / "sensor.py").read_text(encoding="utf-8")
    lock = (INTEGRATION / "lock.py").read_text(encoding="utf-8")
    assert 'unique_id = f"{entry_id}_{key}"' in sensor
    assert 'unique_id = f"{entry_id}_lock_{relay}"' in lock
    assert '"open_relay"' in source()


def test_bytecode_is_excluded_and_absent_from_tracked_files():
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "__pycache__/" in ignore and "*.py[cod]" in ignore
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.splitlines()
    assert not any("__pycache__" in path or path.endswith((".pyc", ".pyo")) for path in tracked)
