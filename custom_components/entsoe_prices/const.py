"""Constants for ENTSO-E Ceny Energii integration."""
from __future__ import annotations

from typing import Final

# ── Integration ──────────────────────────────────────────────────────────────
DOMAIN: Final = "entsoe_prices"
PLATFORMS: Final[list[str]] = ["sensor", "binary_sensor"]
UPDATE_INTERVAL_MINUTES: Final = 30

# ── ENTSO-E API ──────────────────────────────────────────────────────────────
ENTSOE_API_URL: Final = "https://web-api.tp.entsoe.eu/api"
REQUEST_TIMEOUT: Final = 30

# ── NBP API (kurs walut) ─────────────────────────────────────────────────────
NBP_API_URL: Final = "https://api.nbp.pl/api/exchangerates/rates/a/eur/?format=json"
NBP_REQUEST_TIMEOUT: Final = 10

# ── Config keys ──────────────────────────────────────────────────────────────
CONF_API_TOKEN: Final = "api_token"
CONF_AREA: Final = "area"
CONF_CURRENCY: Final = "currency"
CONF_ENERGY_UNIT: Final = "energy_unit"
CONF_CURRENCY_RATE: Final = "currency_rate"
CONF_VAT: Final = "vat"
CONF_AUTO_RATE: Final = "auto_rate"
CONF_SELLER_MARGIN: Final = "seller_margin"
CONF_EXCISE_TAX: Final = "excise_tax"
CONF_DISTRIBUTION_RATE: Final = "distribution_rate"
CONF_RCE_ENTITY: Final = "rce_entity"

# ── Defaults (Polska / PLN) ─────────────────────────────────────────────────
DEFAULT_AREA: Final = "10YPL-AREA-----S"
DEFAULT_CURRENCY: Final = "PLN"
DEFAULT_ENERGY_UNIT: Final = "kWh"
DEFAULT_VAT: Final = 23.0
DEFAULT_CURRENCY_RATE: Final = 4.30  # approx EUR/PLN fallback
DEFAULT_SELLER_MARGIN: Final = 0.0
DEFAULT_EXCISE_TAX: Final = 0.005
DEFAULT_DISTRIBUTION_RATE: Final = 0.0
DEFAULT_RCE_ENTITY: Final = "sensor.rce_pse_cena"

# ── Supported values ─────────────────────────────────────────────────────────
SUPPORTED_CURRENCIES: Final[set[str]] = {"EUR", "PLN"}
SUPPORTED_ENERGY_UNITS: Final[set[str]] = {"kWh", "MWh"}

# ── Bidding Zones ────────────────────────────────────────────────────────────
AREA_CHOICES: Final[list[tuple[str, str]]] = [
    ("🇦🇱 Albania", "10YAL-KESH-----5"),
    ("🇦🇹 Austria", "10YAT-APG------L"),
    ("🇧🇪 Belgia", "10YBE----------2"),
    ("🇧🇦 Bośnia i Hercegowina", "10YBA-JPCC-----D"),
    ("🇧🇬 Bułgaria", "10YCA-BULGARIA-R"),
    ("🇭🇷 Chorwacja", "10YHR-HEP------M"),
    ("🇨🇾 Cypr", "10YCY-1001A0003J"),
    ("🇨🇿 Czechy", "10YCZ-CEPS-----N"),
    ("🇩🇰 Dania (DK1)", "10YDK-1--------W"),
    ("🇩🇰 Dania (DK2)", "10YDK-2--------M"),
    ("🇪🇪 Estonia", "10Y1001A1001A39I"),
    ("🇫🇮 Finlandia", "10YFI-1--------U"),
    ("🇫🇷 Francja", "10YFR-RTE------C"),
    ("🇬🇪 Gruzja", "10Y1001A1001B012"),
    ("🇬🇷 Grecja", "10YGR-HTSO-----Y"),
    ("🇩🇪 Niemcy (50Hz)", "10YDE-VE-------2"),
    ("🇩🇪 Niemcy (TenneT)", "10YDE-RWENET---I"),
    ("🇩🇪 Niemcy (Amprion)", "10YDE-EON------1"),
    ("🇩🇪 Niemcy (TransnetBW)", "10YDE-ENBW-----N"),
    ("🇭🇺 Węgry", "10YHU-MAVIR----U"),
    ("🇮🇪 Irlandia (SEM)", "10Y1001A1001A59C"),
    ("🇮🇪 Irlandia", "10YIE-1001A00010"),
    ("🇮🇹 Włochy (Północ)", "10Y1001A1001A73I"),
    ("🇮🇹 Włochy (Centrum-Północ)", "10Y1001A1001A70O"),
    ("🇮🇹 Włochy (Centrum-Południe)", "10Y1001A1001A71M"),
    ("🇮🇹 Włochy (Południe)", "10Y1001A1001A788"),
    ("🇮🇹 Włochy (Sycylia)", "10Y1001A1001A75E"),
    ("🇮🇹 Włochy (Sardynia)", "10Y1001A1001A74G"),
    ("🇮🇹 Włochy (Kalabria)", "10Y1001A1001A72K"),
    ("🇽🇰 Kosowo", "10Y1001C--00100H"),
    ("🇱🇻 Łotwa", "10YLV-1001A00074"),
    ("🇱🇹 Litwa", "10YLT-1001A0008Q"),
    ("🇱🇺 Luksemburg", "10YLU-CEGEDEL-NQ"),
    ("🇲🇹 Malta", "10Y1001A1001A93C"),
    ("🇲🇩 Mołdawia", "10Y1001A1001A990"),
    ("🇲🇪 Czarnogóra", "10YCS-CG-TSO---S"),
    ("🇳🇱 Holandia", "10YNL----------L"),
    ("🇲🇰 Macedonia Płn.", "10YMK-MEPSO----8"),
    ("🇳🇴 Norwegia (NO1)", "10YNO-1--------2"),
    ("🇳🇴 Norwegia (NO2)", "10YNO-2--------T"),
    ("🇳🇴 Norwegia (NO3)", "10YNO-3--------J"),
    ("🇳🇴 Norwegia (NO4)", "10YNO-4--------9"),
    ("🇳🇴 Norwegia (NO5)", "10Y1001A1001A48H"),
    ("🇵🇱 Polska", "10YPL-AREA-----S"),
    ("🇵🇹 Portugalia", "10YPT-REN------W"),
    ("🇷🇴 Rumunia", "10YRO-TEL------P"),
    ("🇷🇸 Serbia", "10YCS-SERBIATSOV"),
    ("🇸🇰 Słowacja", "10YSK-SEPS-----K"),
    ("🇸🇮 Słowenia", "10YSI-ELES-----O"),
    ("🇪🇸 Hiszpania", "10YES-REE------0"),
    ("🇸🇪 Szwecja (SE1)", "10YSE-1--------K"),
    ("🇸🇪 Szwecja (SE2)", "10Y1001A1001A45N"),
    ("🇸🇪 Szwecja (SE3)", "10Y1001A1001A46L"),
    ("🇸🇪 Szwecja (SE4)", "10Y1001A1001A47J"),
    ("🇨🇭 Szwajcaria", "10YCH-SWISSGRIDZ"),
    ("🇹🇷 Turcja", "10YTR-TEIAS----W"),
    ("🇺🇦 Ukraina (BEI)", "10Y1001C--00003F"),
    ("🇺🇦 Ukraina (IPS)", "10YUA-WEPS-----0"),
    ("🇬🇧 Wielka Brytania", "10YGB----------A"),
]

# ── Attribute keys ───────────────────────────────────────────────────────────
ATTR_PRICES_TODAY: Final = "prices_today"
ATTR_PRICES_TOMORROW: Final = "prices_tomorrow"
ATTR_UPDATED_AT: Final = "updated_at"
ATTR_EXCHANGE_RATE: Final = "exchange_rate"
ATTR_NEXT_UPDATE: Final = "next_update"
ATTR_DATA_AVAILABLE: Final = "tomorrow_available"
