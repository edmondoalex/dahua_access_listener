from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import DahuaDataCoordinator, DahuaEntity

SENSORS = [
    ("code", "Event Code"),
    ("action", "Event Action"),
    ("index", "Index"),
    ("door_status", "Door Status"),
    ("user_id", "User ID"),
    ("card_name", "User Name"),
    ("method", "Access Method"),
    ("event_type", "Event Type"),
    ("reader_id", "Reader ID"),
    ("fingerprint_id", "Fingerprint ID"),
    ("raw", "Raw Data"),
]

def extract_value(data: dict, key: str):
    try:
        if key.startswith("relay_"):
            relay_num = int(key.split("_")[1])
            return data.get("relay_states", {}).get(relay_num)
        if key == "door_status":
            return data.get("door_status")
        if key == "user_id":
            return data.get("user_id")
        if key == "card_name":
            return data.get("card_name")
        if key == "method":
            return data.get("method")
        if key == "event_type":
            return data.get("event_type")
        if key == "reader_id":
            return data.get("reader_id")
        if key == "fingerprint_id":
            return data.get("fingerprint_id")
        if key == "raw":
            return str(data.get("data", ""))[:255]
        if key == "index":
            return data.get("index")
        return data.get(key)
    except Exception:
        return None

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: DahuaDataCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    name_prefix = entry.data.get("name", entry.entry_id)
    num_relays = entry.data.get("relays", 1)

    entities = [
        DahuaSensor(coordinator, entry.entry_id, key, f"{name_prefix} {name}")
        for key, name in SENSORS
    ]
    for relay in range(1, num_relays + 1):
        entities.append(
            DahuaSensor(coordinator, entry.entry_id, f"relay_{relay}", f"{name_prefix} Relay {relay}")
        )
    async_add_entities(entities)

class DahuaSensor(DahuaEntity, SensorEntity):
    def __init__(self, coordinator: DahuaDataCoordinator, entry_id: str, key: str, name: str):
        unique_id = f"{entry_id}_{key}"
        super().__init__(coordinator, entry_id, f"{name}", unique_id)
        self._key = key

    @property
    def native_value(self):
        return extract_value(self.coordinator.data, self._key)