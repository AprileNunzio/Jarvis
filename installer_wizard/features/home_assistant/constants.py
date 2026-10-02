import logging
import re

from config import STATE_DIR

log = logging.getLogger("jarvis.home")

HOME_DIR = STATE_DIR / "home"
DB_FILE = HOME_DIR / "home.db"
FLUSH_EVERY = 2.0
RESYNC_EVERY = 6 * 3600
HISTORY_DAYS = 30
CONFIRM_WINDOW = 45

MOTION = {"motion", "moving", "vibration"}
PRESENCE = {"occupancy", "presence"}
OPENING = {"door", "window", "opening", "garage_door"}
TRACKED = {"person", "device_tracker", "lock", "alarm_control_panel"}

PROTO_LABEL = {"zigbee": "Zigbee", "thread": "Thread", "wifi": "Wi-Fi", "ethernet": "Ethernet", "zwave": "Z-Wave",
               "bluetooth": "Bluetooth", "matter": "Matter", "mqtt": "MQTT", "lan": "Rete locale", "cloud": "Cloud",
               "app": "App sul telefono", "virtual": "Virtuale / servizio", "unknown": "Non determinato"}
ZIGBEE_INT = {"zha", "deconz", "zigbee2mqtt", "tradfri", "xiaomi_aqara", "zigate", "hue"}
ZIGBEE_HUBS = {"hue", "tradfri", "deconz", "xiaomi_aqara"}
ZWAVE_INT = {"zwave_js", "zwave_me", "zwave"}
BT_INT = {"bthome", "xiaomi_ble", "switchbot", "govee_ble", "inkbird", "sensorpush", "ibeacon", "oralb",
          "yalexs_ble", "led_ble", "bluemaestro", "qingping", "thermobeacon", "moat", "kegtron", "airthings_ble",
          "ld2410_ble", "private_ble_device", "eq3btsmart", "improv_ble", "ruuvitag_ble", "sensirion_ble",
          "thermopro", "tilt_ble", "mopeka", "rapt_ble", "snooz", "bluetooth", "medcom_ble", "gardena_bluetooth"}
WIFI_INT = {"esphome", "shelly", "tasmota", "wled", "tuya", "tplink", "tplink_tapo", "yeelight", "wiz", "sonoff",
            "broadlink", "meross_lan", "govee_light_local", "lifx", "nanoleaf", "elgato", "twinkly", "flux_led",
            "switcher_kis", "xiaomi_miio", "roborock", "dreame_vacuum", "daikin", "midea_ac", "gree", "localtuya",
            "tuya_local", "sonoff_lan", "wemo", "tapo", "athom", "magichome", "motion_blinds", "somfy_mylink",
            "blebox", "nuki", "fully_kiosk", "wmspro", "linkplay", "airgradient", "bosch_shc", "led_ble_wifi"}
LAN_INT = {"cast", "sonos", "samsungtv", "webostv", "androidtv", "androidtv_remote", "apple_tv", "denonavr",
           "yamaha_musiccast", "synology_dsm", "unifi", "unifiprotect", "fritz", "fritzbox", "plex", "kodi",
           "braviatv", "philips_js", "onkyo", "heos", "bluesound", "reolink", "onvif", "dlna_dmr", "dlna_dms",
           "homekit", "squeezebox", "openhome", "panasonic_viera", "vizio", "roku", "frigate", "octoprint", "nut",
           "upnp", "ipp", "brother", "hikvision", "axis", "doorbird", "modbus", "knx", "velux", "hunterdouglas_powerview"}
CLOUD_INT = {"met", "sun", "google", "alexa", "spotify", "openweathermap", "accuweather", "ring", "nest", "ecobee",
             "netatmo", "tado", "smartthings", "tesla_fleet", "cloud", "google_assistant", "lg_thinq", "ezviz",
             "switchbot_cloud", "tuya_cloud", "husqvarna_automower", "miele", "home_connect", "blink", "august",
             "yale", "somfy", "overkiz", "xiaomi_cloud", "withings", "fitbit", "icloud", "life360"}
VIRTUAL_INT = {"template", "group", "hassio", "input_boolean", "input_number", "input_select", "input_text",
               "input_datetime", "input_button", "counter", "timer", "schedule", "backup", "sun", "shopping_list",
               "derivative", "integration", "utility_meter", "min_max", "threshold", "statistics", "switch_as_x",
               "workday", "times_of_the_day", "tod", "season", "moon", "uptime", "systemmonitor", "local_calendar",
               "local_todo", "zone", "person"}

STATE_IT = {"on": "acceso", "off": "spento", "open": "aperto", "closed": "chiuso", "opening": "in apertura",
            "closing": "in chiusura", "playing": "in riproduzione", "paused": "in pausa", "idle": "inattivo",
            "standby": "in standby", "locked": "bloccato", "unlocked": "sbloccato", "locking": "in blocco",
            "unlocking": "in sblocco", "jammed": "inceppato", "unavailable": "non raggiungibile", "unknown": "sconosciuto",
            "home": "a casa", "not_home": "fuori casa", "heat": "riscaldamento", "cool": "raffrescamento",
            "heat_cool": "automatico", "auto": "automatico", "dry": "deumidificazione", "fan_only": "ventilazione",
            "cleaning": "in pulizia", "docked": "alla base", "returning": "in rientro", "error": "in errore",
            "armed_away": "inserito (fuori casa)", "armed_home": "inserito (in casa)", "armed_night": "inserito (notte)",
            "disarmed": "disinserito", "triggered": "in allarme", "pending": "in attesa", "arming": "in inserimento"}
PAST = {"turn_on": "acceso", "turn_off": "spento", "toggle": "commutato", "open_cover": "aperto",
        "close_cover": "chiuso", "stop_cover": "fermato", "set_cover_position": "regolato",
        "set_temperature": "impostato", "set_hvac_mode": "impostato", "set_percentage": "regolato",
        "increase_speed": "aumentato", "decrease_speed": "ridotto", "volume_set": "regolato il volume di",
        "volume_up": "alzato il volume di", "volume_down": "abbassato il volume di", "volume_mute": "silenziato",
        "media_play": "fatto ripartire", "media_pause": "messo in pausa", "media_stop": "fermato",
        "media_next_track": "passato al brano successivo su", "media_previous_track": "tornato al brano precedente su",
        "lock": "bloccato", "unlock": "sbloccato", "open": "aperto", "start": "avviato", "pause": "messo in pausa",
        "stop": "fermato", "return_to_base": "rimandato alla base", "start_mowing": "avviato", "dock": "rimandato alla base",
        "press": "premuto", "open_valve": "aperto", "close_valve": "chiuso", "alarm_disarm": "disinserito",
        "alarm_arm_away": "inserito", "set_value": "impostato"}
INFINITIVE = {"unlock": "sbloccare", "open": "aprire", "lock": "bloccare", "alarm_disarm": "disinserire",
              "alarm_arm_away": "inserire", "open_cover": "aprire", "set_cover_position": "aprire",
              "open_valve": "aprire", "close_cover": "chiudere", "turn_on": "accendere", "turn_off": "spegnere"}
FEMININE = {"light", "cover", "lock", "siren", "valve"}
DOMAIN_PLURAL = {"light": "luci", "cover": "tapparelle", "switch": "prese e interruttori", "media_player": "lettori",
                 "fan": "ventilatori", "climate": "climatizzatori", "scene": "scene", "lock": "serrature"}
LLM_DATA_KEYS = {"brightness_pct", "brightness_step_pct", "rgb_color", "color_temp_kelvin", "position", "temperature",
                 "hvac_mode", "percentage", "volume_level", "is_volume_muted", "value", "option", "preset_mode",
                 "fan_mode", "effect", "source", "tilt_position"}
CONFIRM_RE = re.compile(r"^\s*(si|sì|conferma|confermo|procedi|vai|ok|certo|esatto|fallo)\b", re.I)
CANCEL_RE = re.compile(r"^\s*(no|annulla|lascia stare|non farlo|niente|stop)\b", re.I)
