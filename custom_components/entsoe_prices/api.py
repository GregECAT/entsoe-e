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

    # ── Core sensors ─────────────────────────────────────────────────────
    current_price: float | None = None
    next_hour_price: float | None = None
    today_min: float | None = None
    today_max: float | None = None
    today_avg: float | None = None
    today_min_hour: str | None = None
    today_max_hour: str | None = None

    # ── Cheapest windows ─────────────────────────────────────────────────
    cheapest_hours_start: str | None = None
    cheapest_hours_end: str | None = None
    cheapest_hours_avg: float | None = None

    cheapest_2h_start: str | None = None
    cheapest_2h_end: str | None = None
    cheapest_2h_avg: float | None = None

    cheapest_4h_start: str | None = None
    cheapest_4h_end: str | None = None
    cheapest_4h_avg: float | None = None

    # ── Most expensive windows ───────────────────────────────────────────
    most_expensive_3h_start: str | None = None
    most_expensive_3h_end: str | None = None
    most_expensive_3h_avg: float | None = None

    most_expensive_2h_start: str | None = None
    most_expensive_2h_end: str | None = None
    most_expensive_2h_avg: float | None = None

    # ── All-in cost ──────────────────────────────────────────────────────
    all_in_cost_now: float | None = None
    all_in_cost_next_hour: float | None = None
    all_in_min_today: float | None = None
    all_in_max_today: float | None = None

    # ── Rank & percentile ────────────────────────────────────────────────
    rank_current_hour: int | None = None
    total_hours_today: int | None = None
    percentile_current_hour: float | None = None

    # ── Deltas & trends ──────────────────────────────────────────────────
    delta_1h: float | None = None
    delta_3h: float | None = None
    trend_up_3h: bool | None = None
    trend_down_3h: bool | None = None

    # ── Active windows ───────────────────────────────────────────────────
    in_cheapest_window: bool = False
    in_most_expensive_window: bool = False

    # ── RCE Spread ───────────────────────────────────────────────────────
    rce_price_now: float | None = None
    spread_buy_vs_sell_now: float | None = None
    spread_buy_vs_sell_peak_today: float | None = None
    spread_battery_arb_now: float | None = None


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
        seller_margin: float = 0.0,
        excise_tax: float = 0.005,
        distribution_rate: float = 0.0,
    ) -> None:
        self._session = session
        self._api_token = api_token
        self._area = area
        self._currency = currency
        self._energy_unit = energy_unit
        self._vat = vat
        self._currency_rate = currency_rate
        self._auto_rate = auto_rate
        self._seller_margin = seller_margin
        self._excise_tax = excise_tax
        self._distribution_rate = distribution_rate
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

    # ── All-in Cost Calculation ──────────────────────────────────────────

    def _all_in_cost(self, base_price: float) -> float:
        """Calculate all-in purchase cost.

        base_price already includes VAT on energy.
        Additional costs (margin, excise, distribution) also have VAT applied.
        """
        vat_mult = 1.0 + (self._vat / 100.0)
        additional = (self._seller_margin + self._excise_tax + self._distribution_rate) * vat_mult
        return round(base_price + additional, 4)

    # ── Analytics ────────────────────────────────────────────────────────

    @staticmethod
    def _find_window(
        prices: list[ConvertedPrice], n: int, *, cheapest: bool = True
    ) -> list[ConvertedPrice] | None:
        """Find cheapest or most expensive N consecutive hours."""
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
            if best_sum is None:
                best_sum = total
                best_start = i
            elif cheapest and total < best_sum:
                best_sum = total
                best_start = i
            elif not cheapest and total > best_sum:
                best_sum = total
                best_start = i

        return sorted_prices[best_start : best_start + n] if best_sum is not None else None

    # Keep backward compat alias
    def _find_cheapest_consecutive(
        self, prices: list[ConvertedPrice], n: int
    ) -> list[ConvertedPrice] | None:
        return self._find_window(prices, n, cheapest=True)

    @staticmethod
    def _calculate_rank(
        today_prices: list[ConvertedPrice], now: datetime
    ) -> tuple[int | None, int]:
        """Calculate rank of current hour (1 = cheapest)."""
        if not today_prices:
            return None, 0

        # Sort by price ascending
        sorted_by_price = sorted(today_prices, key=lambda p: p.value)
        total = len(sorted_by_price)

        for rank, p in enumerate(sorted_by_price, start=1):
            if p.start <= now < p.end:
                return rank, total

        return None, total

    @staticmethod
    def _calculate_percentile(rank: int | None, total: int) -> float | None:
        """Calculate percentile (0 = cheapest, 100 = most expensive)."""
        if rank is None or total <= 1:
            return None
        return round(((rank - 1) / (total - 1)) * 100, 1)

    @staticmethod
    def _calculate_deltas(
        all_prices: list[ConvertedPrice], now: datetime
    ) -> tuple[float | None, float | None]:
        """Calculate price delta for +1h and +3h from now."""
        current = None
        plus_1h = None
        plus_3h = None

        current_hour = now.replace(minute=0, second=0, microsecond=0)
        target_1h = current_hour + timedelta(hours=1)
        target_3h = current_hour + timedelta(hours=3)

        for p in all_prices:
            hour = p.start.replace(minute=0, second=0, microsecond=0)
            if hour == current_hour:
                current = float(p.value)
            elif hour == target_1h:
                plus_1h = float(p.value)
            elif hour == target_3h:
                plus_3h = float(p.value)

        delta_1h = round(plus_1h - current, 4) if current is not None and plus_1h is not None else None
        delta_3h = round(plus_3h - current, 4) if current is not None and plus_3h is not None else None
        return delta_1h, delta_3h

    @staticmethod
    def _calculate_trends(
        all_prices: list[ConvertedPrice], now: datetime
    ) -> tuple[bool | None, bool | None]:
        """Calculate 3h trend (rising/falling)."""
        current_hour = now.replace(minute=0, second=0, microsecond=0)
        hours_needed = [current_hour + timedelta(hours=i) for i in range(4)]

        values: list[float] = []
        for target in hours_needed:
            found = False
            for p in all_prices:
                if p.start.replace(minute=0, second=0, microsecond=0) == target:
                    values.append(float(p.value))
                    found = True
                    break
            if not found:
                return None, None

        if len(values) < 4:
            return None, None

        # Check if prices are monotonically increasing over 4 points
        trend_up = all(values[i] < values[i + 1] for i in range(3))
        # Check if prices are monotonically decreasing
        trend_down = all(values[i] > values[i + 1] for i in range(3))

        return trend_up, trend_down

    @staticmethod
    def _is_in_window(
        window: list[ConvertedPrice] | None, now: datetime
    ) -> bool:
        """Check if current time falls within a price window."""
        if not window:
            return False
        return any(p.start <= now < p.end for p in window)

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

            # ── Cheapest windows ─────────────────────────────────────
            for n, attr_prefix in [(2, "cheapest_2h"), (3, "cheapest_hours"), (4, "cheapest_4h")]:
                window = self._find_window(today_prices, n, cheapest=True)
                if window:
                    setattr(data, f"{attr_prefix}_start", window[0].start.astimezone(CET).strftime("%H:%M"))
                    setattr(data, f"{attr_prefix}_end", window[-1].end.astimezone(CET).strftime("%H:%M"))
                    setattr(data, f"{attr_prefix}_avg", round(
                        sum(float(p.value) for p in window) / len(window), 4
                    ))

            # ── Most expensive windows ───────────────────────────────
            for n, attr_prefix in [(2, "most_expensive_2h"), (3, "most_expensive_3h")]:
                window = self._find_window(today_prices, n, cheapest=False)
                if window:
                    setattr(data, f"{attr_prefix}_start", window[0].start.astimezone(CET).strftime("%H:%M"))
                    setattr(data, f"{attr_prefix}_end", window[-1].end.astimezone(CET).strftime("%H:%M"))
                    setattr(data, f"{attr_prefix}_avg", round(
                        sum(float(p.value) for p in window) / len(window), 4
                    ))

            # ── All-in cost ──────────────────────────────────────────
            if data.current_price is not None:
                data.all_in_cost_now = self._all_in_cost(data.current_price)
            if data.next_hour_price is not None:
                data.all_in_cost_next_hour = self._all_in_cost(data.next_hour_price)
            if data.today_min is not None:
                data.all_in_min_today = self._all_in_cost(data.today_min)
            if data.today_max is not None:
                data.all_in_max_today = self._all_in_cost(data.today_max)

            # ── Rank & percentile ────────────────────────────────────
            rank, total = self._calculate_rank(today_prices, now)
            data.rank_current_hour = rank
            data.total_hours_today = total
            data.percentile_current_hour = self._calculate_percentile(rank, total)

            # ── Active windows ───────────────────────────────────────
            cheapest_3h = self._find_window(today_prices, 3, cheapest=True)
            expensive_3h = self._find_window(today_prices, 3, cheapest=False)
            data.in_cheapest_window = self._is_in_window(cheapest_3h, now)
            data.in_most_expensive_window = self._is_in_window(expensive_3h, now)

        # ── Deltas & trends (need all prices, not just today) ────────
        data.delta_1h, data.delta_3h = self._calculate_deltas(prices, now)
        data.trend_up_3h, data.trend_down_3h = self._calculate_trends(prices, now)

        return data

    def compute_spread(
        self,
        data: PriceData,
        rce_price_mwh: float | None,
        rce_max_today_mwh: float | None = None,
        battery_efficiency: float = 0.90,
    ) -> PriceData:
        """Compute RCE spread sensors.

        Args:
            data: existing PriceData
            rce_price_mwh: current RCE price in PLN/MWh (from sensor.rce_pse_cena)
            rce_max_today_mwh: max RCE price today in PLN/MWh
            battery_efficiency: round-trip battery efficiency (default 90%)
        """
        if rce_price_mwh is None:
            return data

        # Convert RCE from PLN/MWh to target unit (PLN/kWh)
        rce_per_unit = rce_price_mwh / 1000.0 if self._energy_unit == "kWh" else rce_price_mwh
        data.rce_price_now = round(rce_per_unit, 4)

        # Spread = what you can sell for - what it costs to buy
        if data.all_in_cost_now is not None:
            data.spread_buy_vs_sell_now = round(rce_per_unit - data.all_in_cost_now, 4)

            # Battery arbitrage: accounts for round-trip efficiency loss
            if battery_efficiency > 0:
                cost_after_loss = data.all_in_cost_now / battery_efficiency
                data.spread_battery_arb_now = round(rce_per_unit - cost_after_loss, 4)

        # Peak spread: max RCE today vs cheapest all-in buy
        if rce_max_today_mwh is not None and data.all_in_min_today is not None:
            rce_max_unit = rce_max_today_mwh / 1000.0 if self._energy_unit == "kWh" else rce_max_today_mwh
            data.spread_buy_vs_sell_peak_today = round(rce_max_unit - data.all_in_min_today, 4)

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
