from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN
from .coordinator import DahuaDataCoordinator, DahuaEntity

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: DahuaDataCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    name_prefix = entry.data.get("name", entry.entry_id)
    num_relays = entry.data.get("relays", 1)

    entities = [
        DahuaLock(hass, coordinator, entry.entry_id, relay, f"{name_prefix} Door {relay}")
        for relay in range(1, num_relays + 1)
    ]
    async_add_entities(entities)

class DahuaLock(DahuaEntity, LockEntity):
    def __init__(self, hass, coordinator, entry_id, relay, name):
        unique_id = f"{entry_id}_lock_{relay}"
        super().__init__(coordinator, entry_id, name, unique_id)
        self._hass = hass
        self._relay = relay

    async def async_added_to_hass(self):
        await super().async_added_to_hass()

        @callback
        def _handle_update():
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self._hass,
                f"{DOMAIN}_{self._entry_id}_update",
                _handle_update,
            )
        )

    @property
    def is_locked(self):
        data = self.coordinator.data
        status = None
        if data:
            status = data.get("door_status")
        if status == "Open":
            self._attr_is_locked = False
            return False
        if status == "Close":
            self._attr_is_locked = True
            return True
        # Keep previous state if not Open/Close
        return getattr(self, "_attr_is_locked", True)

    async def async_unlock(self, **kwargs):
        await self._hass.services.async_call(
            DOMAIN, "open_relay", {"relay": self._relay}, blocking=True
        )

    async def async_lock(self, **kwargs):
        pass