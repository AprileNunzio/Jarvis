from datetime import datetime


def demo_payload() -> dict:
    now = datetime.now().astimezone().isoformat()
    areas = [("soggiorno", "Soggiorno", "terra"), ("cucina", "Cucina", "terra"), ("camera", "Camera da letto", "primo"),
             ("bagno", "Bagno", "primo"), ("studio", "Studio", "primo"), ("ingresso", "Ingresso", "terra")]
    devices, entities, states = [], [], []

    def add(dev_id, name, area, manuf, model, integ, ents, conns=(), via=None, ids=None):
        devices.append({"id": dev_id, "name": name, "area_id": area, "manufacturer": manuf, "model": model,
                        "identifiers": ids or [[integ, dev_id]], "connections": [list(c) for c in conns],
                        "config_entries": [integ], "primary_config_entry": integ, "via_device_id": via})
        for eid, ename, state, attrs in ents:
            entities.append({"entity_id": eid, "device_id": dev_id, "name": None, "original_name": ename,
                             "platform": integ})
            states.append({"entity_id": eid, "state": state, "last_changed": now,
                           "attributes": {"friendly_name": f"{name} {ename}".strip() if ename else name} | attrs})

    dim = {"supported_color_modes": ["color_temp", "hs"], "brightness": 180}
    add("coord", "Coordinatore Zigbee", None, "Nabu Casa", "SkyConnect", "zha", [])
    add("l1", "Luce soggiorno", "soggiorno", "Philips", "Hue White and Color", "zha",
        [("light.luce_soggiorno", None, "on", dim)], [("zigbee", "00:17:88")], "coord")
    add("l2", "Lampada lettura", "soggiorno", "IKEA", "TRADFRI bulb E27", "zha",
        [("light.lampada_lettura", None, "off", {"supported_color_modes": ["brightness"]})], [("zigbee", "00:0b:57")], "coord")
    add("l3", "Luce cucina", "cucina", "Shelly", "Shelly Dimmer 2", "shelly",
        [("light.luce_cucina", None, "off", {"supported_color_modes": ["brightness"]})], [("mac", "aa:bb:cc:00:00:01")])
    add("l4", "Faretti cucina", "cucina", "Tuya", "Smart Spot", "tuya",
        [("light.faretti_cucina", None, "off", {"supported_color_modes": ["onoff"]})], [("mac", "aa:bb:cc:00:00:02")])
    add("l5", "Luce camera", "camera", "Nanoleaf", "Essentials A19", "matter",
        [("light.luce_camera", None, "off", dim)], ids=[["matter", "node-5"]])
    add("l6", "Luce studio", "studio", "Eve", "Eve Light Switch", "matter",
        [("light.luce_studio", None, "on", {"supported_color_modes": ["onoff"]}),
         ("sensor.luce_studio_thread", "Thread status", "Child", {})], ids=[["matter", "node-6"]])
    add("c1", "Tapparella soggiorno", "soggiorno", "Shelly", "Shelly Plus 2PM", "shelly",
        [("cover.tapparella_soggiorno", None, "open", {"supported_features": 15, "current_position": 100})],
        [("mac", "aa:bb:cc:00:00:03")])
    add("c2", "Tapparella camera", "camera", "Aqara", "Roller Shade E1", "mqtt",
        [("cover.tapparella_camera", None, "closed", {"supported_features": 15, "current_position": 0})],
        ids=[["mqtt", "zigbee2mqtt_0x54ef44"]])
    add("t1", "Termostato", "soggiorno", "Netatmo", "Smart Thermostat", "netatmo",
        [("climate.termostato", None, "heat", {"supported_features": 17, "hvac_modes": ["off", "heat"],
                                                "temperature": 20.5, "current_temperature": 20.1})])
    add("m1", "Sensore movimento cucina", "cucina", "Aqara", "Motion Sensor P1", "zha",
        [("binary_sensor.movimento_cucina", "Movimento", "on", {"device_class": "motion"}),
         ("sensor.temperatura_cucina", "Temperatura", "22.4", {"device_class": "temperature", "unit_of_measurement": "°C"})],
        [("zigbee", "54:ef:44")], "coord")
    add("m2", "Presenza studio", "studio", "Aqara", "Presence Sensor FP2", "homekit_controller",
        [("binary_sensor.presenza_studio", "Presenza", "off", {"device_class": "occupancy"})])
    add("m3", "Sensore bagno", "bagno", "Shelly", "Shelly BLU Motion", "bthome",
        [("binary_sensor.movimento_bagno", "Movimento", "off", {"device_class": "motion"}),
         ("sensor.umidita_bagno", "Umidità", "64", {"device_class": "humidity", "unit_of_measurement": "%"})],
        [("bluetooth", "38:39:8f")])
    add("d1", "Porta ingresso", "ingresso", "Aqara", "Door Sensor", "zha",
        [("binary_sensor.porta_ingresso", "Apertura", "off", {"device_class": "door"})], [("zigbee", "00:15:8d")], "coord")
    add("k1", "Serratura", "ingresso", "Nuki", "Smart Lock 4.0", "matter",
        [("lock.serratura", None, "locked", {"supported_features": 1})], ids=[["matter", "node-9"]])
    add("tv", "TV Samsung", "soggiorno", "Samsung", "QE55Q80", "samsungtv",
        [("media_player.tv_samsung", None, "off", {"supported_features": 24509})], [("mac", "aa:bb:cc:00:00:09")])
    add("v1", "Robot aspirapolvere", "soggiorno", "Roborock", "S8", "roborock",
        [("vacuum.robot", None, "docked", {})])
    states.append({"entity_id": "person.nunzio", "state": "home", "last_changed": now,
                   "attributes": {"friendly_name": "Nunzio"}})
    states.append({"entity_id": "scene.cinema", "state": "unknown", "last_changed": now,
                   "attributes": {"friendly_name": "Cinema"}})
    entities += [{"entity_id": "person.nunzio", "name": None, "original_name": "Nunzio", "platform": "person"},
                 {"entity_id": "scene.cinema", "name": None, "original_name": "Cinema", "platform": "scene"}]
    return {"cfg": {"location_name": "Casa dimostrativa"},
            "floors": [{"floor_id": "terra", "name": "Piano terra", "level": 0},
                       {"floor_id": "primo", "name": "Primo piano", "level": 1}],
            "areas": [{"area_id": a, "name": n, "floor_id": f} for a, n, f in areas],
            "devices": devices, "entities": entities, "entries": [], "states": states,
            "services": {"light": {"turn_on": {}, "turn_off": {}, "toggle": {}},
                         "cover": {"open_cover": {}, "close_cover": {}, "set_cover_position": {}, "stop_cover": {}},
                         "climate": {"set_temperature": {}, "set_hvac_mode": {}, "turn_on": {}, "turn_off": {}},
                         "scene": {"turn_on": {}}, "lock": {"lock": {}, "unlock": {}, "open": {}},
                         "media_player": {"turn_on": {}, "turn_off": {}, "volume_set": {}}},
            "extended": {}}
