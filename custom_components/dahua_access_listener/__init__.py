import logging
import json
import requests
from requests.auth import HTTPDigestAuth

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN
from .coordinator import DahuaDataCoordinator

_LOGGER = logging.getLogger(__name__)


def start_dahua_stream(hass: HomeAssistant, coordinator: DahuaDataCoordinator, url: str, username: str, password: str):
    """Avvia il listener eventi Dahua."""
    try:
        with requests.get(url, auth=HTTPDigestAuth(username, password), stream=True, timeout=None) as response:
            buffer = []

            for line_bytes in response.iter_lines():
                if line_bytes:
                    line = line_bytes.decode("utf-8", errors="ignore").strip()

                    if line.startswith("--"):
                        if buffer:
                            block = "\n".join(buffer)
                            buffer.clear()

                            if "Heartbeat" in block:
                                continue

                            try:
                                if "data=" not in block:
                                    _LOGGER.warning("⚠️ Nessun campo 'data=' nel blocco ricevuto:\n%s", block)
                                    continue

                                headers, body = block.split("data=", 1)
                                data = json.loads(body.strip())

                                code = ""
                                action = ""
                                index = None

                                header_lines = headers.strip().split("\n")[1:] if "Content-Length" in headers else headers.strip().split("\n")

                                for line in header_lines:
                                    for part in line.replace("\r", "").split(";"):
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

                                coordinator_data = {
                                    "code": code,
                                    "action": action,
                                    "index": index,
                                    "data": data,
                                    "door_status": data.get("Status") if code == "DoorStatus" else None,
                                    "user_id": data.get("UserID") if code == "AccessControl" else None,
                                    "card_name": data.get("CardName") if code == "AccessControl" else None,
                                    "method": data.get("Method") if code == "AccessControl" else None,
                                    "event_type": data.get("Type"),
                                    "reader_id": data.get("ReaderID"),
                                    "fingerprint_id": data.get("FingerPrintID") if code == "_FingerPrintCheck_" else None,
                                    "relay_states": {},
                                }

                                hass.loop.call_soon_threadsafe(
                                    coordinator.async_set_updated_data,
                                    coordinator_data
                                )

                            except Exception as e:
                                _LOGGER.exception("❌ Errore parsing evento Dahua: %s", e)
                    else:
                        buffer.append(line)
    except Exception as e:
        _LOGGER.exception("❌ Errore stream Dahua: %s", e)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Setup dell'integrazione da UI."""
    hass.data.setdefault(DOMAIN, {})

    host = entry.data["host"]
    user = entry.data["username"]
    pwd = entry.data["password"]
    name = entry.data["name"]

    url = f"http://{host}/cgi-bin/eventManager.cgi?action=attach&codes=[All]&heartbeat=5"

    _LOGGER.info("📡 Avvio listener eventi Dahua per '%s' su %s", name, host)

    coordinator = DahuaDataCoordinator(hass, entry.entry_id)
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "name": name,
    }

    hass.async_add_executor_job(start_dahua_stream, hass, coordinator, url, user, pwd)

    def open_relay(relay):
        url_relay = f"http://{host}/cgi-bin/accessControl.cgi?action=openDoor&channel={relay}"
        try:
            resp = requests.get(url_relay, auth=HTTPDigestAuth(user, pwd), timeout=5)
            if resp.status_code != 200:
                _LOGGER.error("Errore apertura relè %s: HTTP %s", relay, resp.status_code)
        except Exception as e:
            _LOGGER.error("Errore apertura relè %s: %s", relay, e)

    async def handle_open_relay(call):
        relay = call.data.get("relay", 1)
        await hass.async_add_executor_job(open_relay, relay)

    hass.services.async_register(DOMAIN, "open_relay", handle_open_relay)

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "lock"])
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
