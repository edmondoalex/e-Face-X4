from __future__ import annotations

from typing import Any


LABEL_NAMES = {"e-face", "eface", "e_face"}


def _labels(item: dict[str, Any]) -> set[str]:
    value = item.get("labels")
    return {str(label) for label in value} if isinstance(value, list) else set()


def normalize_labeled_entities(
    states: list[dict[str, Any]], entities: list[dict[str, Any]], devices: list[dict[str, Any]],
    areas: list[dict[str, Any]], labels: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return only entities explicitly labelled e-Face, directly or through their HA device."""
    label_ids = {str(item.get("label_id")) for item in labels if isinstance(item, dict)
                 and str(item.get("name") or "").strip().casefold() in LABEL_NAMES}
    if not label_ids:
        return []
    device_map = {str(item.get("id")): item for item in devices if isinstance(item, dict)}
    area_names = {str(item.get("area_id")): str(item.get("name") or "") for item in areas if isinstance(item, dict)}
    selected: dict[str, dict[str, Any]] = {}
    for entity in entities:
        if not isinstance(entity, dict) or entity.get("disabled_by"):
            continue
        device = device_map.get(str(entity.get("device_id") or ""), {})
        if not (label_ids & (_labels(entity) | _labels(device))):
            continue
        entity_id = str(entity.get("entity_id") or "")
        if "." in entity_id:
            selected[entity_id] = {"registry": entity, "device": device}

    result = []
    for state in states:
        entity_id = str(state.get("entity_id") or "") if isinstance(state, dict) else ""
        source = selected.get(entity_id)
        if not source:
            continue
        registry, device = source["registry"], source["device"]
        attributes = state.get("attributes") if isinstance(state.get("attributes"), dict) else {}
        domain = entity_id.split(".", 1)[0]
        kind = {"input_boolean": "switch", "button": "button"}.get(domain, domain)
        area_id = str(registry.get("area_id") or device.get("area_id") or "")
        features = int(attributes.get("supported_features") or 0)
        capabilities: dict[str, bool] = {}
        if kind in {"light", "switch"}:
            capabilities = {"on": True, "off": True}
        elif kind == "cover":
            capabilities = {"open": True, "close": True, "stop": bool(features & 8), "set_position": bool(features & 4)}
        elif kind == "lock":
            capabilities = {"lock": True, "unlock": True}
        elif kind == "button":
            capabilities = {"press": True}
        item = {
            "id": f"ha:{entity_id}", "registry_id": entity_id, "entity_id": entity_id,
            "state_key": entity_id,
            "provider": "home_assistant", "kind": kind, "entity_domain": domain,
            "name": str(registry.get("name_by_user") or attributes.get("friendly_name") or registry.get("original_name") or entity_id),
            "room": area_names.get(area_id) or "Home Assistant", "icon": str(registry.get("icon") or attributes.get("icon") or "mdi:access-point"),
            "state": state.get("state"), "device_class": attributes.get("device_class"),
            "unit": attributes.get("unit_of_measurement"), "capabilities": capabilities,
            "availability": "unavailable" if state.get("state") == "unavailable" else "available",
        }
        if kind == "light":
            item["dimmable"] = bool(features & 1)
            item["brightness"] = attributes.get("brightness")
        if kind == "cover":
            item["position"] = attributes.get("current_position")
            item["position_supported"] = bool(features & 4)
        result.append(item)
    return sorted(result, key=lambda item: (str(item["room"]).casefold(), str(item["name"]).casefold()))
