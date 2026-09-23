from app.ha_labeled import normalize_labeled_entities


def test_labeled_entity_is_normalized_with_area_and_sensor_metadata():
    items = normalize_labeled_entities(
        [{"entity_id": "binary_sensor.water", "state": "off", "attributes": {"friendly_name": "Allagamento", "device_class": "moisture", "icon": "mdi:water-alert"}}],
        [{"entity_id": "binary_sensor.water", "device_id": "device-1", "area_id": None, "labels": [], "disabled_by": None}],
        [{"id": "device-1", "area_id": "boiler", "labels": ["eface"]}],
        [{"area_id": "boiler", "name": "Locale caldaia"}],
        [{"label_id": "eface", "name": "e-Face"}],
    )
    assert items == [{
        "id": "ha:binary_sensor.water", "registry_id": "binary_sensor.water", "entity_id": "binary_sensor.water",
        "state_key": "binary_sensor.water", "provider": "home_assistant", "kind": "binary_sensor",
        "entity_domain": "binary_sensor", "name": "Allagamento", "room": "Locale caldaia",
        "icon": "mdi:water-alert", "state": "off", "device_class": "moisture", "unit": None,
        "capabilities": {}, "availability": "available",
    }]


def test_only_explicit_eface_label_is_imported():
    states = [{"entity_id": "sensor.keep", "state": "12", "attributes": {}}, {"entity_id": "sensor.skip", "state": "9", "attributes": {}}]
    entities = [{"entity_id": "sensor.keep", "labels": ["wanted"]}, {"entity_id": "sensor.skip", "labels": ["other"]}]
    items = normalize_labeled_entities(states, entities, [], [], [{"label_id": "wanted", "name": "E_FACE"}, {"label_id": "other", "name": "Altro"}])
    assert [item["entity_id"] for item in items] == ["sensor.keep"]


def test_disabled_labeled_entity_is_not_imported():
    assert normalize_labeled_entities(
        [{"entity_id": "sensor.disabled", "state": "1", "attributes": {}}],
        [{"entity_id": "sensor.disabled", "labels": ["wanted"], "disabled_by": "user"}], [], [],
        [{"label_id": "wanted", "name": "e-Face"}],
    ) == []


def test_labeled_select_exposes_options_for_ui_and_routines():
    items = normalize_labeled_entities(
        [{"entity_id": "select.feeder", "state": "2", "attributes": {"friendly_name": "Distributore", "options": ["1", "2", "3"]}}],
        [{"entity_id": "select.feeder", "labels": ["wanted"], "disabled_by": None}], [], [],
        [{"label_id": "wanted", "name": "e-Face"}],
    )
    assert items[0]["kind"] == "select"
    assert items[0]["options"] == ["1", "2", "3"]
    assert items[0]["source_list"] == ["1", "2", "3"]
    assert items[0]["capabilities"] == {"select_option": True, "select_source": True}
