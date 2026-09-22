"""Direct Alexa schedules for e-Control, using the official Alexa Devices session."""

from __future__ import annotations

from datetime import datetime
from http import HTTPMethod
from typing import Any

import voluptuous as vol
from yarl import URL

from aioamazondevices.const.http import REFRESH_ACCESS_TOKEN, REQUEST_AGENT
from aioamazondevices.exceptions import CannotRetrieveData

from homeassistant.components.alexa_devices.const import DOMAIN as ALEXA_DOMAIN
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
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
DELETE_SCHEMA = vol.Schema(
    DEVICE_SCHEMA
    | {vol.Required("notification_id"): vol.All(cv.string, vol.Length(min=1, max=200))}
)
DELETE_NEXT_SCHEMA = vol.Schema(
    DEVICE_SCHEMA
    | {vol.Required("kind"): vol.In({"alarm", "timer", "reminder"})}
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
        _, endpoints_response = await wrapper.session_request(
            HTTPMethod.GET,
            url=URL.joinpath(state.alexa_website_url, "api/endpoints"),
        )
        endpoints = await wrapper.response_to_json(endpoints_response, "Alexa endpoints")
        alexa_api_url = str(endpoints.get("alexaApiUrl") or "").strip()
        if not alexa_api_url.startswith("https://"):
            raise HomeAssistantError("Endpoint regionale Alexa non disponibile")
        alarm_payload = {
            "trigger": {"scheduledTime": value.strftime("%Y-%m-%dT%H:%M:%S")},
            "extensions": [],
            "endpointId": f"{serial}@{device_type}",
        }
        try:
            _, response = await wrapper.session_request(
                HTTPMethod.POST,
                url=URL.joinpath(URL(alexa_api_url), "v1/alerts/alarms"),
                input_data=alarm_payload,
                json_data=True,
                extended_headers={
                    "Authorization": f"Bearer {state.login_stored_data[REFRESH_ACCESS_TOKEN]}",
                    "User-Agent": REQUEST_AGENT["Amazon"],
                },
            )
            status = response.status
        except CannotRetrieveData as exc:
            # aioamazondevices currently accepts only HTTP 200, while Alexa
            # Alerts correctly returns HTTP 201 after creating an alarm.
            if "Created" not in str(exc):
                raise
            status = 201
    else:
        _, response = await wrapper.session_request(
            HTTPMethod.PUT,
            url=URL.joinpath(state.alexa_website_url, "api/notifications/null"),
            input_data=payload,
            json_data=True,
        )
        status = response.status
    if status not in (200, 201):
        raise HomeAssistantError(f"Alexa ha rifiutato la richiesta ({status})")
    await coordinator.async_request_refresh()


async def _raw_notifications(call: ServiceCall) -> tuple[Any, list[dict[str, Any]]]:
    coordinator, serial, _ = _device_context(call)
    handler = coordinator.api._notification_handler
    _, response = await handler._http_wrapper.session_request(
        HTTPMethod.GET,
        url=URL.joinpath(handler._session_state_data.alexa_website_url, "api/notifications"),
    )
    data = await handler._http_wrapper.response_to_json(response, "notifications")
    records = [
        item for item in data.get("notifications", [])
        if isinstance(item, dict) and item.get("deviceSerialNumber") == serial
    ]
    return coordinator, records


async def _list_notifications(call: ServiceCall) -> dict[str, Any]:
    _, records = await _raw_notifications(call)
    items = []
    for record in records:
        identifier = str(record.get("notificationIndex") or record.get("id") or "")
        if not identifier:
            continue
        items.append(
            {
                "id": identifier,
                "kind": str(record.get("type") or "").lower(),
                "status": record.get("status"),
                "label": record.get("reminderLabel") or record.get("timerLabel") or record.get("originalLabel"),
                "alarm_time": record.get("alarmTime"),
                "remaining_ms": record.get("remainingTime"),
            }
        )
    return {"items": items}


async def _delete_notification(call: ServiceCall) -> None:
    _, records = await _raw_notifications(call)
    identifier = call.data["notification_id"]
    record = next(
        (item for item in records if identifier in {str(item.get("notificationIndex") or ""), str(item.get("id") or "")}),
        None,
    )
    if record is None:
        raise HomeAssistantError("Evento Alexa non trovato")
    await _delete_record(call, record)


async def _delete_record(call: ServiceCall, record: dict[str, Any]) -> None:
    handler = _device_context(call)[0].api._notification_handler
    try:
        await handler._http_wrapper.session_request(
            HTTPMethod.DELETE,
            url=URL.joinpath(handler._session_state_data.alexa_website_url, f"api/notifications/{record.get('id') or record.get('notificationIndex')}"),
            input_data=record,
            json_data=True,
        )
    except CannotRetrieveData as exc:
        if "No Content" not in str(exc):
            raise


async def _delete_next_notification(call: ServiceCall) -> None:
    _, records = await _raw_notifications(call)
    kind = call.data["kind"].casefold()
    candidates = [
        item for item in records
        if str(item.get("type") or "").casefold() == kind and item.get("status") == "ON"
    ]
    if not candidates:
        raise HomeAssistantError("Nessun evento Alexa da cancellare")
    def event_order(item: dict[str, Any]) -> int:
        return int(item.get("alarmTime") or 0) or int(item.get("createdDate") or 0)
    await _delete_record(call, min(candidates, key=event_order))


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    async def create_alarm(call: ServiceCall) -> None:
        await _write_notification(call, "Alarm")

    async def create_timer(call: ServiceCall) -> None:
        await _write_notification(call, "Timer")

    async def create_reminder(call: ServiceCall) -> None:
        await _write_notification(call, "Reminder")

    async def list_notifications(call: ServiceCall) -> dict[str, Any]:
        return await _list_notifications(call)

    async def delete_notification(call: ServiceCall) -> None:
        await _delete_notification(call)

    async def delete_next_notification(call: ServiceCall) -> None:
        await _delete_next_notification(call)

    hass.services.async_register(DOMAIN, "create_alarm", create_alarm, schema=TIMED_SCHEMA)
    hass.services.async_register(DOMAIN, "create_timer", create_timer, schema=TIMER_SCHEMA)
    hass.services.async_register(
        DOMAIN, "create_reminder", create_reminder, schema=REMINDER_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "list_notifications", list_notifications, schema=vol.Schema(DEVICE_SCHEMA),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, "delete_notification", delete_notification, schema=DELETE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "delete_next_notification", delete_next_notification,
        schema=DELETE_NEXT_SCHEMA,
    )
    return True
