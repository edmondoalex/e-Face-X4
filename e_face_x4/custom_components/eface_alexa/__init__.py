"""Direct Alexa schedules for e-Control, using the official Alexa Devices session."""

from __future__ import annotations

from datetime import datetime
from http import HTTPMethod
from typing import Any

import voluptuous as vol
from yarl import URL

from aioamazondevices.const.http import REFRESH_ACCESS_TOKEN, REQUEST_AGENT

from homeassistant.components.alexa_devices.const import DOMAIN as ALEXA_DOMAIN
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, service

DOMAIN = "eface_alexa"
ATTR_TIMESTAMP = "timestamp"
ATTR_DURATION = "duration"
ATTR_LABEL = "label"

DEVICE_SCHEMA = {vol.Required(ATTR_DEVICE_ID): cv.string}
TIMED_SCHEMA = vol.Schema(DEVICE_SCHEMA | {vol.Required(ATTR_TIMESTAMP): cv.datetime})
TIMER_SCHEMA = vol.Schema(
    DEVICE_SCHEMA
    | {
        vol.Required(ATTR_DURATION): vol.All(vol.Coerce(float), vol.Range(min=1)),
        vol.Optional(ATTR_LABEL, default=""): cv.string,
    }
)
REMINDER_SCHEMA = vol.Schema(
    DEVICE_SCHEMA
    | {
        vol.Required(ATTR_TIMESTAMP): cv.datetime,
        vol.Required(ATTR_LABEL): vol.All(cv.string, vol.Length(min=1, max=300)),
    }
)


def _device_context(call: ServiceCall) -> tuple[Any, Any, Any]:
    device, entry = service.async_get_device_and_config_entry(
        call.hass, ALEXA_DOMAIN, call.data[ATTR_DEVICE_ID]
    )
    coordinator = entry.runtime_data
    serial = device.serial_number
    if not serial or serial not in coordinator.data:
        raise HomeAssistantError("Dispositivo Alexa non disponibile")
    alexa_device = coordinator.data[serial]
    device_type = getattr(alexa_device, "device_type", None)
    if not device_type:
        raise HomeAssistantError("Tipo dispositivo Alexa non disponibile")
    return coordinator, serial, device_type


async def _write_notification(call: ServiceCall, kind: str) -> None:
    coordinator, serial, device_type = _device_context(call)
    payload: dict[str, Any] = {
        "type": kind,
        "status": "ON",
        "deviceSerialNumber": serial,
        "deviceType": device_type,
    }
    if kind == "Timer":
        duration_ms = round(float(call.data[ATTR_DURATION]) * 1000)
        payload.update(
            remainingTime=duration_ms,
            originalDurationInMillis=duration_ms,
            timerLabel=call.data.get(ATTR_LABEL) or None,
        )
    else:
        value: datetime = call.data[ATTR_TIMESTAMP]
        when_ms = round(value.timestamp() * 1000)
        payload.update(
            alarmTime=when_ms,
            createdDate=round(datetime.now().timestamp() * 1000),
            originalDate=value.strftime("%Y-%m-%d"),
            originalTime=value.strftime("%H:%M:%S.000"),
        )
        if kind == "Alarm":
            payload["reminderLabel"] = None
        else:
            payload["reminderLabel"] = call.data[ATTR_LABEL]

    api = coordinator.api
    handler = api._notification_handler
    wrapper = handler._http_wrapper
    state = handler._session_state_data
    if kind == "Alarm":
        refreshed, _ = await wrapper.refresh_data(REFRESH_ACCESS_TOKEN)
        if not refreshed:
            raise HomeAssistantError("Impossibile aggiornare la sessione Alexa")
        alarm_payload = {
            "trigger": {"scheduledTime": value.strftime("%Y-%m-%dT%H:%M:%S")},
            "extensions": [],
            "endpointId": f"{serial}@{device_type}",
        }
        _, response = await wrapper.session_request(
            HTTPMethod.POST,
            url=URL.joinpath(state.global_alexa_api_url, "v1/alerts/alarms"),
            input_data=alarm_payload,
            json_data=True,
            extended_headers={
                "Authorization": f"Bearer {state.login_stored_data[REFRESH_ACCESS_TOKEN]}",
                "User-Agent": REQUEST_AGENT["Amazon"],
            },
        )
    else:
        _, response = await wrapper.session_request(
            HTTPMethod.PUT,
            url=URL.joinpath(state.alexa_website_url, "api/notifications/null"),
            input_data=payload,
            json_data=True,
        )
    if response.status not in (200, 201):
        raise HomeAssistantError(f"Alexa ha rifiutato la richiesta ({response.status})")
    await coordinator.async_request_refresh()


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    async def create_alarm(call: ServiceCall) -> None:
        await _write_notification(call, "Alarm")

    async def create_timer(call: ServiceCall) -> None:
        await _write_notification(call, "Timer")

    async def create_reminder(call: ServiceCall) -> None:
        await _write_notification(call, "Reminder")

    hass.services.async_register(DOMAIN, "create_alarm", create_alarm, schema=TIMED_SCHEMA)
    hass.services.async_register(DOMAIN, "create_timer", create_timer, schema=TIMER_SCHEMA)
    hass.services.async_register(
        DOMAIN, "create_reminder", create_reminder, schema=REMINDER_SCHEMA
    )
    return True
