"""Dahua Access Reader integration."""
from __future__ import annotations
import json
import logging
import threading
import requests
from requests.auth import HTTPDigestAuth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from .const import DOMAIN
from .coordinator import DahuaDataCoordinator

_LOGGER = logging.getLogger(__name__)
_PLATFORMS = ["sensor", "lock"]


def start_dahua_stream(hass, coordinator, url, username, password, stop_event, runtime):
    """Run the blocking event listener until unload requests a stop."""
    try:
        with requests.get(url, auth=HTTPDigestAuth(username, password), stream=True, timeout=(5, 30)) as response:
            runtime["response"] = response
            buffer = []
            for line_bytes in response.iter_lines():
                if stop_event.is_set():
                    break
                if not line_bytes:
                    continue
                line = line_bytes.decode("utf-8", errors="ignore").strip()
                if not line.startswith("--"):
                    buffer.append(line)
                    continue
                if not buffer:
                    continue
                block = "\n".join(buffer)
                buffer.clear()
                if "Heartbeat" in block or "data=" not in block:
                    continue
                try:
                    headers, body = block.split("data=", 1)
                    data = json.loads(body.strip())
                    code, action, index = "", "", None
                    for header_line in headers.strip().split("\n"):
                        for part in header_line.replace("\r", "").split(";"):
                            if part.startswith("Code="):
                                code = part.split("=", 1)[1]
                            elif part.startswith("action="):
                                action = part.split("=", 1)[1]
                            elif part.startswith("index="):
                                try:
                                    index = int(part.split("=", 1)[1])
                                except ValueError:
                                    index = None
                    code = code or data.get("Event", "")
                    update = {
                        "code": code, "action": action, "index": index, "data": data,
                        "door_status": data.get("Status") if code == "DoorStatus" else None,
                        "user_id": data.get("UserID") if code == "AccessControl" else None,
                        "card_name": data.get("CardName") if code == "AccessControl" else None,
                        "method": data.get("Method") if code == "AccessControl" else None,
                        "event_type": data.get("Type"), "reader_id": data.get("ReaderID"),
                        "fingerprint_id": data.get("FingerPrintID") if code == "_FingerPrintCheck_" else None,
                        "relay_states": {},
                    }
                    hass.loop.call_soon_threadsafe(coordinator.async_set_updated_data, update)
                except (ValueError, TypeError, json.JSONDecodeError):
                    _LOGGER.exception("Unable to parse Dahua event")
    except requests.RequestException:
        if not stop_event.is_set():
            _LOGGER.exception("Dahua event stream failed")
    finally:
        runtime.pop("response", None)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up without changing config-entry or entity identity."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    host, user, password, name = entry.data["host"], entry.data["username"], entry.data["password"], entry.data["name"]
    url = f"http://{host}/cgi-bin/eventManager.cgi?action=attach&codes=[All]&heartbeat=5"
    coordinator = DahuaDataCoordinator(hass, entry.entry_id)
    stop_event, runtime = threading.Event(), {}
    domain_data[entry.entry_id] = {"coordinator": coordinator, "name": name, "stop_event": stop_event, "runtime": runtime}
    runtime["future"] = hass.async_add_executor_job(start_dahua_stream, hass, coordinator, url, user, password, stop_event, runtime)

    def open_relay(relay):
        relay_url = f"http://{host}/cgi-bin/accessControl.cgi?action=openDoor&channel={relay}"
        try:
            response = requests.get(relay_url, auth=HTTPDigestAuth(user, password), timeout=5)
            if response.status_code != 200:
                _LOGGER.error("Relay %s returned HTTP %s", relay, response.status_code)
        except requests.RequestException:
            _LOGGER.exception("Unable to open relay %s", relay)

    domain_data[entry.entry_id]["open_relay"] = open_relay

    async def handle_open_relay(call):
        current = next(iter(hass.data.get(DOMAIN, {}).values()), None)
        if current is None:
            _LOGGER.warning("Ignoring open_relay without an active Dahua entry")
            return
        await hass.async_add_executor_job(current["open_relay"], call.data.get("relay", 1))

    if not hass.services.has_service(DOMAIN, "open_relay"):
        hass.services.async_register(DOMAIN, "open_relay", handle_open_relay)
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload platforms, listener/coordinator state and the shared service."""
    domain_data = hass.data.get(DOMAIN, {})
    entry_data = domain_data.get(entry.entry_id)
    if entry_data is None:
        return True
    if not await hass.config_entries.async_unload_platforms(entry, _PLATFORMS):
        return False
    entry_data = domain_data.pop(entry.entry_id, None)
    if entry_data:
        entry_data["stop_event"].set()
        response = entry_data["runtime"].get("response")
        if response is not None:
            response.close()
    if not domain_data:
        if hass.services.has_service(DOMAIN, "open_relay"):
            hass.services.async_remove(DOMAIN, "open_relay")
        hass.data.pop(DOMAIN, None)
    return True
