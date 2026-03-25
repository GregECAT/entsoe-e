"""ENTSO-E Transparency Platform API client."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

from aiohttp import ClientError, ClientSession, ClientTimeout

from .const import (
    ENTSOE_API_URL,
    NBP_API_URL,
    NBP_REQUEST_TIMEOUT,
    REQUEST_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

CET = ZoneInfo("Europe/Warsaw")


class EntsoeApiError(Exception):
    """Raised when communication with ENTSO-E fails."""


class NbpApiError(Exception):
    """Raised when communication with NBP API fails."""


@dataclass
class PricePoint:
    """Single raw price point from ENTSO-E."""
    timestamp: datetime
    price_eur_mwh: Decimal
    resolution_minutes: int = 60


@dataclass
class ConvertedPrice:
    """Price point after currency/unit/VAT conversion."""
    start: datetime
    end: datetime
    value: Decimal          # converted price in target currency/unit with VAT
    raw_eur_mwh: Decimal    # original EUR/MWh price


@dataclass
class PriceData:
    """Organized price data for sensors."""
    unit: str = ""
    exchange_rate: float = 1.0
    updated_at: str = ""

    # Hourly prices
    prices_today: list[dict[str, Any]] = field(default_factory=list)
    prices_tomorrow: list[dict[str, Any]] = field(default_factory=list)
    tomorrow_available: bool = False

    # Statistics
    current_price: float | None = None
    next_hour_price: float | None = None
    today_min: float | None = None
    today_max: float | None = None
    today_avg: float | None = None
    today_min_hour: str | None = None
    today_max_hour: str | None = None

    # Cheapest consecutive hours
    cheapest_hours_start: str | None = None
    cheapest_hours_end: str | None = None
    cheapest_hours_avg: float | None = None


class EntsoeApiClient:
    """Client for the ENTSO-E Transparency Platform REST API."""

    RESOLUTION_MAP = {
        "PT5M": 5,
        "PT10M": 10,
        "PT15M": 15,
        "PT20M": 20,
        "PT30M": 30,
        "PT60M": 60,
        "PT1H": 60,
    }

    def __init__(
        self,
        session: ClientSession,
        api_token: str,
        area: str,
        currency: str = "PLN",
        energy_unit: str = "kWh",
        vat: float = 23.0,
        currency_rate: float = 1.0,
        auto_rate: bool = True,
    ) -> None:
        self._session = session
        self._api_token = api_token
        self._area = area
        self._currency = currency
        self._energy_unit = energy_unit
        self._vat = vat
        self._currency_rate = currency_rate
        self._auto_rate = auto_rate
        self._cached_nbp_rate: float | None = None
        self._nbp_rate_date: datetime | None = None

    # ── Public API ───────────────────────────────────────────────────────

    async def async_get_prices(self) -> PriceData:
        """Fetch and process day-ahead prices."""
        now = datetime.now(CET)
        start, end = self._period_range(now)

        _LOGGER.info(
            "ENTSO-E: pobieranie cen day-ahead za okres %s — %s", start, end
        )
        xml_text = await self._fetch_xml(start, end)
        raw_points = self._parse_xml(xml_text)

        if not raw_points:
            raise EntsoeApiError("Brak danych cenowych z ENTSO-E")

        _LOGGER.info("ENTSO-E: pobrano %d punktów cenowych", len(raw_points))

        # Get exchange rate
        rate = await self._get_exchange_rate()

        # Convert prices
        converted = self._convert_prices(raw_points, rate)

        # Organize into PriceData
        return self._build_price_data(converted, now, rate)

    async def async_test_connection(self) -> bool:
        """Test if the API token and area are valid."""
        now = datetime.now(CET)
        start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt = start_dt + timedelta(days=1)
        start = start_dt.strftime("%Y%m%d%H%M")
        end = end_dt.strftime("%Y%m%d%H%M")

        try:
            xml_text = await self._fetch_xml(start, end)
            points = self._parse_xml(xml_text)
            return len(points) > 0
        except EntsoeApiError:
            return False

    # ── NBP Exchange Rate ────────────────────────────────────────────────

    async def _get_exchange_rate(self) -> float:
        """Get EUR/PLN exchange rate."""
        if self._currency == "EUR":
            return 1.0

        if not self._auto_rate:
            return self._currency_rate if self._currency_rate > 0 else 1.0

        # Use cached rate if fetched today
        now = datetime.now(CET)
        if (
            self._cached_nbp_rate is not None
            and self._nbp_rate_date is not None
            and self._nbp_rate_date.date() == now.date()
        ):
            return self._cached_nbp_rate

        try:
            rate = await self._fetch_nbp_rate()
            self._cached_nbp_rate = rate
            self._nbp_rate_date = now
            _LOGGER.info("NBP: kurs EUR/PLN = %.4f", rate)
            return rate
        except NbpApiError as err:
            _LOGGER.warning("NBP: nie udało się pobrać kursu: %s", err)
            if self._cached_nbp_rate is not None:
                return self._cached_nbp_rate
            return self._currency_rate if self._currency_rate > 0 else 4.30

    async def _fetch_nbp_rate(self) -> float:
        """Fetch current EUR/PLN rate from NBP API."""
        try:
            timeout = ClientTimeout(total=NBP_REQUEST_TIMEOUT)
            async with self._session.get(NBP_API_URL, timeout=timeout) as resp:
                if resp.status != 200:
                    raise NbpApiError(f"NBP API HTTP {resp.status}")
                data = await resp.json(content_type=None)
                rate = data["rates"][0]["mid"]
                return float(rate)
        except (ClientError, KeyError, IndexError, ValueError) as err:
            raise NbpApiError(f"Błąd NBP API: {err}") from err

    # ── ENTSO-E Data Fetching ────────────────────────────────────────────

    def _period_range(self, now: datetime) -> tuple[str, str]:
        """Calculate the query period: today midnight CET to tomorrow+1 midnight CET."""
        start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt = start_dt + timedelta(days=2)
        # Convert to UTC for the API
        start_utc = start_dt.astimezone(timezone.utc)
        end_utc = end_dt.astimezone(timezone.utc)
        return start_utc.strftime("%Y%m%d%H%M"), end_utc.strftime("%Y%m%d%H%M")

    async def _fetch_xml(self, start: str, end: str) -> str:
        """Fetch A44 XML from ENTSO-E."""
        params = {
            "securityToken": self._api_token,
            "documentType": "A44",
            "processType": "A01",
            "in_Domain": self._area,
            "out_Domain": self._area,
            "periodStart": start,
            "periodEnd": end,
        }

        try:
            timeout = ClientTimeout(total=REQUEST_TIMEOUT)
            async with self._session.get(
                ENTSOE_API_URL, params=params, timeout=timeout
            ) as resp:
                text = await resp.text()
                if resp.status != 200:
                    raise EntsoeApiError(
                        f"ENTSO-E HTTP {resp.status}: {text[:200]}"
                    )
                return text
        except ClientError as err:
            raise EntsoeApiError(f"Błąd połączenia z ENTSO-E: {err}") from err

    # ── XML Parsing ──────────────────────────────────────────────────────

    def _parse_xml(self, xml_text: str) -> list[PricePoint]:
        """Parse ENTSO-E A44 XML into PricePoint list."""
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as err:
            raise EntsoeApiError(f"Nieprawidłowy XML: {err}") from err

        ns_uri = self._detect_namespace(root.tag)
        ns = {"ns": ns_uri} if ns_uri else {}
        p = "ns:" if ns else ""

        points: list[PricePoint] = []

        for ts in root.findall(f".//{p}TimeSeries", ns):
            for period in ts.findall(f"{p}Period", ns):
                start_text = period.findtext(
                    f"{p}timeInterval/{p}start", namespaces=ns
                )
                res_text = period.findtext(f"{p}resolution", namespaces=ns)
                res_min = self._resolution_to_minutes(res_text)

                if not start_text or res_min is None:
                    continue

                start_time = self._parse_datetime(start_text)
                if start_time is None:
                    continue

                for point in period.findall(f"{p}Point", ns):
                    pos_text = point.findtext(f"{p}position", namespaces=ns)
                    price_text = point.findtext(
                        f"{p}price.amount", namespaces=ns
                    )
                    if pos_text is None or price_text is None:
                        continue
                    try:
                        position = int(pos_text)
                        price = Decimal(price_text)
                    except (ValueError, InvalidOperation):
                        continue

                    timestamp = start_time + timedelta(
                        minutes=res_min * (position - 1)
                    )
                    points.append(
                        PricePoint(
                            timestamp=timestamp,
                            price_eur_mwh=price,
                            resolution_minutes=res_min,
                        )
                    )

        points.sort(key=lambda p: p.timestamp)
        return points

    # ── Price Conversion ─────────────────────────────────────────────────

    def _convert_prices(
        self, points: list[PricePoint], exchange_rate: float
    ) -> list[ConvertedPrice]:
        """Convert raw EUR/MWh prices to target currency/unit with VAT."""
        rate = Decimal(str(exchange_rate))
        vat_mult = Decimal("1") + (Decimal(str(self._vat)) / Decimal("100"))
        energy_div = Decimal("1000") if self._energy_unit == "kWh" else Decimal("1")

        # Group by hour (average sub-hourly data)
        hourly: dict[datetime, list[PricePoint]] = {}
        for pt in points:
            hour_start = pt.timestamp.replace(minute=0, second=0, microsecond=0)
            hourly.setdefault(hour_start, []).append(pt)

        converted: list[ConvertedPrice] = []
        for hour_start, hour_points in sorted(hourly.items()):
            # Average the EUR/MWh prices for this hour
            avg_eur = sum(p.price_eur_mwh for p in hour_points) / len(hour_points)

            # Convert
            value = (avg_eur / energy_div) * rate * vat_mult
            value = value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

            converted.append(
                ConvertedPrice(
                    start=hour_start,
                    end=hour_start + timedelta(hours=1),
                    value=value,
                    raw_eur_mwh=avg_eur.quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    ),
                )
            )

        return converted

    # ── Price Data Organization ──────────────────────────────────────────

    def _build_price_data(
        self,
        prices: list[ConvertedPrice],
        now: datetime,
        exchange_rate: float,
    ) -> PriceData:
        """Organize converted prices into PriceData."""
        today = now.date()
        tomorrow = today + timedelta(days=1)

        today_prices = [p for p in prices if p.start.astimezone(CET).date() == today]
        tomorrow_prices = [p for p in prices if p.start.astimezone(CET).date() == tomorrow]

        unit = f"{self._currency}/{self._energy_unit}"

        data = PriceData(
            unit=unit,
            exchange_rate=exchange_rate,
            updated_at=datetime.now(timezone.utc).isoformat(),
            tomorrow_available=len(tomorrow_prices) > 0,
        )

        # Serialize today/tomorrow
        data.prices_today = self._serialize_prices(today_prices)
        data.prices_tomorrow = self._serialize_prices(tomorrow_prices)

        # Current price
        current = self._find_current_price(today_prices, now)
        if current is not None:
            data.current_price = float(current.value)

        # Next hour price
        next_hour = self._find_next_hour_price(prices, now)
        if next_hour is not None:
            data.next_hour_price = float(next_hour.value)

        # Today statistics
        if today_prices:
            values = [float(p.value) for p in today_prices]
            data.today_min = min(values)
            data.today_max = max(values)
            data.today_avg = round(sum(values) / len(values), 4)

            min_price = min(today_prices, key=lambda p: p.value)
            max_price = max(today_prices, key=lambda p: p.value)
            data.today_min_hour = min_price.start.astimezone(CET).strftime("%H:%M")
            data.today_max_hour = max_price.start.astimezone(CET).strftime("%H:%M")

            # Cheapest 3 consecutive hours
            cheapest = self._find_cheapest_consecutive(today_prices, 3)
            if cheapest:
                data.cheapest_hours_start = cheapest[0].start.astimezone(CET).strftime("%H:%M")
                data.cheapest_hours_end = cheapest[-1].end.astimezone(CET).strftime("%H:%M")
                data.cheapest_hours_avg = round(
                    sum(float(p.value) for p in cheapest) / len(cheapest), 4
                )

        return data

    @staticmethod
    def _serialize_prices(prices: list[ConvertedPrice]) -> list[dict[str, Any]]:
        """Convert prices to a list of dicts for sensor attributes."""
        return [
            {
                "start": p.start.isoformat(),
                "end": p.end.isoformat(),
                "start_local": p.start.astimezone(CET).strftime("%H:%M"),
                "value": float(p.value),
                "raw_eur_mwh": float(p.raw_eur_mwh),
            }
            for p in sorted(prices, key=lambda x: x.start)
        ]

    @staticmethod
    def _find_current_price(
        prices: list[ConvertedPrice], now: datetime
    ) -> ConvertedPrice | None:
        """Find the price for the current hour."""
        for p in prices:
            if p.start <= now < p.end:
                return p
        return None

    @staticmethod
    def _find_next_hour_price(
        prices: list[ConvertedPrice], now: datetime
    ) -> ConvertedPrice | None:
        """Find the price for the next hour."""
        next_hour_start = (now + timedelta(hours=1)).replace(
            minute=0, second=0, microsecond=0
        )
        for p in prices:
            if p.start == next_hour_start:
                return p
        return None

    @staticmethod
    def _find_cheapest_consecutive(
        prices: list[ConvertedPrice], n: int
    ) -> list[ConvertedPrice] | None:
        """Find the cheapest N consecutive hours."""
        if len(prices) < n:
            return None

        sorted_prices = sorted(prices, key=lambda p: p.start)
        best_sum = None
        best_start = 0

        for i in range(len(sorted_prices) - n + 1):
            window = sorted_prices[i : i + n]
            # Verify consecutive
            consecutive = True
            for j in range(1, len(window)):
                if window[j].start != window[j - 1].end:
                    consecutive = False
                    break
            if not consecutive:
                continue

            total = sum(p.value for p in window)
            if best_sum is None or total < best_sum:
                best_sum = total
                best_start = i

        return sorted_prices[best_start : best_start + n] if best_sum is not None else None

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _detect_namespace(tag: str) -> str | None:
        if tag.startswith("{") and "}" in tag:
            return tag[1 : tag.index("}")]
        return None

    @classmethod
    def _resolution_to_minutes(cls, value: str | None) -> int | None:
        if value is None:
            return None
        return cls.RESOLUTION_MAP.get(value.strip())

    @staticmethod
    def _parse_datetime(value: str) -> datetime | None:
        normalized = value.strip()
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
