import logging
from typing import Any, Optional

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    CoordinatorEntity,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class DahuaDataCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_{entry_id}",
        )
        self.entry_id = entry_id

    async def _async_update_data(self) -> dict:
        return self.data if hasattr(self, "data") else {}

class DahuaEntity(CoordinatorEntity):
    def __init__(self, coordinator: DahuaDataCoordinator, entry_id: str, name: str, unique_id: str) -> None:
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_should_poll = False
        self._entry_id = entry_id

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        @callback
        def _handle_update():
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._entry_id}_update",
                _handle_update,
            )
        )

    @property
    def extra_state_attributes(self) -> Optional[dict[str, Any]]:
        return self.coordinator.data or {}