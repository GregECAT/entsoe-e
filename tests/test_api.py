"""Unit tests for ENTSO-E API client."""
from __future__ import annotations

import sys
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add the custom_components path so we can import without HA installed
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "custom_components"))

# Mock homeassistant modules before importing our code
sys.modules["homeassistant"] = MagicMock()
sys.modules["homeassistant.config_entries"] = MagicMock()
sys.modules["homeassistant.core"] = MagicMock()
sys.modules["homeassistant.helpers"] = MagicMock()
sys.modules["homeassistant.helpers.aiohttp_client"] = MagicMock()
sys.modules["homeassistant.helpers.update_coordinator"] = MagicMock()
sys.modules["homeassistant.helpers.entity"] = MagicMock()
sys.modules["homeassistant.helpers.entity_platform"] = MagicMock()
sys.modules["homeassistant.helpers.selector"] = MagicMock()
sys.modules["homeassistant.components"] = MagicMock()
sys.modules["homeassistant.components.sensor"] = MagicMock()
sys.modules["voluptuous"] = MagicMock()

from entsoe_prices.api import EntsoeApiClient, PricePoint, ConvertedPrice, PriceData


# ── Sample ENTSO-E XML ──────────────────────────────────────────────────────

SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Publication_MarketDocument xmlns="urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3">
  <mRID>some-id</mRID>
  <type>A44</type>
  <TimeSeries>
    <mRID>1</mRID>
    <currency_Unit.name>EUR</currency_Unit.name>
    <price_Measure_Unit.name>MWH</price_Measure_Unit.name>
    <Period>
      <timeInterval>
        <start>2025-01-15T23:00Z</start>
        <end>2025-01-16T23:00Z</end>
      </timeInterval>
      <resolution>PT60M</resolution>
      <Point>
        <position>1</position>
        <price.amount>45.50</price.amount>
      </Point>
      <Point>
        <position>2</position>
        <price.amount>42.30</price.amount>
      </Point>
      <Point>
        <position>3</position>
        <price.amount>38.10</price.amount>
      </Point>
      <Point>
        <position>4</position>
        <price.amount>35.00</price.amount>
      </Point>
      <Point>
        <position>5</position>
        <price.amount>33.20</price.amount>
      </Point>
      <Point>
        <position>6</position>
        <price.amount>36.80</price.amount>
      </Point>
      <Point>
        <position>7</position>
        <price.amount>52.40</price.amount>
      </Point>
      <Point>
        <position>8</position>
        <price.amount>68.90</price.amount>
      </Point>
      <Point>
        <position>9</position>
        <price.amount>75.20</price.amount>
      </Point>
      <Point>
        <position>10</position>
        <price.amount>72.50</price.amount>
      </Point>
      <Point>
        <position>11</position>
        <price.amount>65.30</price.amount>
      </Point>
      <Point>
        <position>12</position>
        <price.amount>60.10</price.amount>
      </Point>
      <Point>
        <position>13</position>
        <price.amount>58.40</price.amount>
      </Point>
      <Point>
        <position>14</position>
        <price.amount>55.70</price.amount>
      </Point>
      <Point>
        <position>15</position>
        <price.amount>53.20</price.amount>
      </Point>
      <Point>
        <position>16</position>
        <price.amount>56.80</price.amount>
      </Point>
      <Point>
        <position>17</position>
        <price.amount>72.40</price.amount>
      </Point>
      <Point>
        <position>18</position>
        <price.amount>89.30</price.amount>
      </Point>
      <Point>
        <position>19</position>
        <price.amount>95.10</price.amount>
      </Point>
      <Point>
        <position>20</position>
        <price.amount>85.60</price.amount>
      </Point>
      <Point>
        <position>21</position>
        <price.amount>70.20</price.amount>
      </Point>
      <Point>
        <position>22</position>
        <price.amount>58.90</price.amount>
      </Point>
      <Point>
        <position>23</position>
        <price.amount>48.30</price.amount>
      </Point>
      <Point>
        <position>24</position>
        <price.amount>42.10</price.amount>
      </Point>
    </Period>
  </TimeSeries>
</Publication_MarketDocument>"""


SAMPLE_XML_15MIN = """<?xml version="1.0" encoding="UTF-8"?>
<Publication_MarketDocument xmlns="urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3">
  <TimeSeries>
    <Period>
      <timeInterval>
        <start>2025-01-15T23:00Z</start>
        <end>2025-01-16T00:00Z</end>
      </timeInterval>
      <resolution>PT15M</resolution>
      <Point>
        <position>1</position>
        <price.amount>45.00</price.amount>
      </Point>
      <Point>
        <position>2</position>
        <price.amount>46.00</price.amount>
      </Point>
      <Point>
        <position>3</position>
        <price.amount>44.00</price.amount>
      </Point>
      <Point>
        <position>4</position>
        <price.amount>45.00</price.amount>
      </Point>
    </Period>
  </TimeSeries>
</Publication_MarketDocument>"""


EMPTY_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Acknowledgement_MarketDocument xmlns="urn:iec62325.351:tc57wg16:451-1:acknowledgementdocument:7:0">
  <Reason>
    <code>999</code>
    <text>No matching data found</text>
  </Reason>
</Acknowledgement_MarketDocument>"""


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    """Create a test API client."""
    session = MagicMock()
    return EntsoeApiClient(
        session=session,
        api_token="test-token",
        area="10YPL-AREA-----S",
        currency="PLN",
        energy_unit="kWh",
        vat=23.0,
        currency_rate=4.30,
        auto_rate=False,
    )


@pytest.fixture
def client_eur():
    """Create a test API client with EUR."""
    session = MagicMock()
    return EntsoeApiClient(
        session=session,
        api_token="test-token",
        area="10YPL-AREA-----S",
        currency="EUR",
        energy_unit="kWh",
        vat=0.0,
        currency_rate=1.0,
        auto_rate=False,
    )


# ── XML Parsing Tests ────────────────────────────────────────────────────────

class TestXmlParsing:
    """Tests for XML parsing."""

    def test_parse_hourly_prices(self, client):
        """Test parsing of hourly price data."""
        points = client._parse_xml(SAMPLE_XML)
        assert len(points) == 24
        assert all(isinstance(p, PricePoint) for p in points)

    def test_parse_first_point(self, client):
        """Test first point has correct values."""
        points = client._parse_xml(SAMPLE_XML)
        first = points[0]
        assert first.price_eur_mwh == Decimal("45.50")
        assert first.resolution_minutes == 60
        assert first.timestamp == datetime(2025, 1, 15, 23, 0, tzinfo=timezone.utc)

    def test_parse_last_point(self, client):
        """Test last point has correct values."""
        points = client._parse_xml(SAMPLE_XML)
        last = points[-1]
        assert last.price_eur_mwh == Decimal("42.10")
        assert last.timestamp == datetime(2025, 1, 16, 22, 0, tzinfo=timezone.utc)

    def test_parse_15min_prices(self, client):
        """Test parsing of 15-minute prices."""
        points = client._parse_xml(SAMPLE_XML_15MIN)
        assert len(points) == 4
        assert all(p.resolution_minutes == 15 for p in points)

    def test_parse_empty_response(self, client):
        """Test parsing of empty/acknowledgement response."""
        points = client._parse_xml(EMPTY_XML)
        assert len(points) == 0

    def test_parse_invalid_xml(self, client):
        """Test parsing of invalid XML raises error."""
        from entsoe_prices.api import EntsoeApiError
        with pytest.raises(EntsoeApiError, match="Nieprawidłowy XML"):
            client._parse_xml("this is not xml")

    def test_points_sorted_by_timestamp(self, client):
        """Test that parsed points are sorted by timestamp."""
        points = client._parse_xml(SAMPLE_XML)
        timestamps = [p.timestamp for p in points]
        assert timestamps == sorted(timestamps)


# ── Price Conversion Tests ───────────────────────────────────────────────────

class TestPriceConversion:
    """Tests for price conversion logic."""

    def test_eur_to_pln_kwh_with_vat(self, client):
        """Test EUR/MWh → PLN/kWh + 23% VAT."""
        points = [
            PricePoint(
                timestamp=datetime(2025, 1, 16, 0, 0, tzinfo=timezone.utc),
                price_eur_mwh=Decimal("100.00"),
                resolution_minutes=60,
            )
        ]
        converted = client._convert_prices(points, 4.30)
        assert len(converted) == 1
        price = converted[0]
        # 100 EUR/MWh = 0.1 EUR/kWh * 4.30 = 0.43 PLN/kWh * 1.23 = 0.5289
        assert float(price.value) == pytest.approx(0.5289, abs=0.001)

    def test_eur_no_vat(self, client_eur):
        """Test EUR/MWh → EUR/kWh without VAT."""
        points = [
            PricePoint(
                timestamp=datetime(2025, 1, 16, 0, 0, tzinfo=timezone.utc),
                price_eur_mwh=Decimal("100.00"),
                resolution_minutes=60,
            )
        ]
        converted = client_eur._convert_prices(points, 1.0)
        assert len(converted) == 1
        assert float(converted[0].value) == pytest.approx(0.1, abs=0.001)

    def test_15min_averaged_to_hourly(self, client_eur):
        """Test that 15-minute data is averaged to hourly."""
        points = [
            PricePoint(
                timestamp=datetime(2025, 1, 16, 0, 0, tzinfo=timezone.utc),
                price_eur_mwh=Decimal("40.00"),
                resolution_minutes=15,
            ),
            PricePoint(
                timestamp=datetime(2025, 1, 16, 0, 15, tzinfo=timezone.utc),
                price_eur_mwh=Decimal("44.00"),
                resolution_minutes=15,
            ),
            PricePoint(
                timestamp=datetime(2025, 1, 16, 0, 30, tzinfo=timezone.utc),
                price_eur_mwh=Decimal("48.00"),
                resolution_minutes=15,
            ),
            PricePoint(
                timestamp=datetime(2025, 1, 16, 0, 45, tzinfo=timezone.utc),
                price_eur_mwh=Decimal("48.00"),
                resolution_minutes=15,
            ),
        ]
        converted = client_eur._convert_prices(points, 1.0)
        assert len(converted) == 1  # one hour
        # Average: (40+44+48+48)/4 = 45 EUR/MWh = 0.045 EUR/kWh
        assert float(converted[0].value) == pytest.approx(0.045, abs=0.001)


# ── Statistics Tests ─────────────────────────────────────────────────────────

class TestStatistics:
    """Tests for price statistics and cheapest hours."""

    def test_find_current_price(self, client):
        """Test finding the current price."""
        now = datetime(2025, 1, 16, 10, 30, tzinfo=timezone.utc)
        prices = [
            ConvertedPrice(
                start=datetime(2025, 1, 16, 10, 0, tzinfo=timezone.utc),
                end=datetime(2025, 1, 16, 11, 0, tzinfo=timezone.utc),
                value=Decimal("0.45"),
                raw_eur_mwh=Decimal("78.00"),
            ),
            ConvertedPrice(
                start=datetime(2025, 1, 16, 11, 0, tzinfo=timezone.utc),
                end=datetime(2025, 1, 16, 12, 0, tzinfo=timezone.utc),
                value=Decimal("0.52"),
                raw_eur_mwh=Decimal("90.00"),
            ),
        ]
        current = client._find_current_price(prices, now)
        assert current is not None
        assert current.value == Decimal("0.45")

    def test_find_next_hour_price(self, client):
        """Test finding the next hour price."""
        now = datetime(2025, 1, 16, 10, 30, tzinfo=timezone.utc)
        prices = [
            ConvertedPrice(
                start=datetime(2025, 1, 16, 10, 0, tzinfo=timezone.utc),
                end=datetime(2025, 1, 16, 11, 0, tzinfo=timezone.utc),
                value=Decimal("0.45"),
                raw_eur_mwh=Decimal("78.00"),
            ),
            ConvertedPrice(
                start=datetime(2025, 1, 16, 11, 0, tzinfo=timezone.utc),
                end=datetime(2025, 1, 16, 12, 0, tzinfo=timezone.utc),
                value=Decimal("0.52"),
                raw_eur_mwh=Decimal("90.00"),
            ),
        ]
        next_price = client._find_next_hour_price(prices, now)
        assert next_price is not None
        assert next_price.value == Decimal("0.52")

    def test_cheapest_consecutive_hours(self, client):
        """Test finding cheapest N consecutive hours."""
        prices = [
            ConvertedPrice(
                start=datetime(2025, 1, 16, h, 0, tzinfo=timezone.utc),
                end=datetime(2025, 1, 16, h + 1, 0, tzinfo=timezone.utc),
                value=Decimal(str(v)),
                raw_eur_mwh=Decimal("0"),
            )
            for h, v in [
                (0, 0.50), (1, 0.45), (2, 0.30), (3, 0.25), (4, 0.28),
                (5, 0.35), (6, 0.60), (7, 0.80),
            ]
        ]
        cheapest = client._find_cheapest_consecutive(prices, 3)
        assert cheapest is not None
        assert len(cheapest) == 3
        # Hours 2, 3, 4 = 0.30 + 0.25 + 0.28 = 0.83
        assert cheapest[0].start.hour == 2
        assert cheapest[2].start.hour == 4


# ── Helper Tests ─────────────────────────────────────────────────────────────

class TestHelpers:
    """Tests for helper methods."""

    def test_detect_namespace(self, client):
        """Test namespace detection from XML tag."""
        ns = client._detect_namespace(
            "{urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3}Publication_MarketDocument"
        )
        assert ns == "urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3"

    def test_detect_no_namespace(self, client):
        """Test no namespace detection."""
        ns = client._detect_namespace("Publication_MarketDocument")
        assert ns is None

    def test_resolution_mapping(self, client):
        """Test resolution string to minutes mapping."""
        assert client._resolution_to_minutes("PT60M") == 60
        assert client._resolution_to_minutes("PT1H") == 60
        assert client._resolution_to_minutes("PT15M") == 15
        assert client._resolution_to_minutes("PT30M") == 30
        assert client._resolution_to_minutes(None) is None
        assert client._resolution_to_minutes("INVALID") is None

    def test_parse_datetime_utc(self, client):
        """Test datetime parsing."""
        dt = client._parse_datetime("2025-01-15T23:00Z")
        assert dt == datetime(2025, 1, 15, 23, 0, tzinfo=timezone.utc)

    def test_parse_datetime_with_offset(self, client):
        """Test datetime parsing with offset."""
        dt = client._parse_datetime("2025-01-15T23:00:00+01:00")
        assert dt is not None
        assert dt.tzinfo == timezone.utc
        assert dt == datetime(2025, 1, 15, 22, 0, tzinfo=timezone.utc)

    def test_parse_datetime_invalid(self, client):
        """Test invalid datetime returns None."""
        assert client._parse_datetime("not-a-date") is None

    def test_period_range(self, client):
        """Test period range calculation."""
        from zoneinfo import ZoneInfo
        now = datetime(2025, 1, 16, 14, 30, tzinfo=ZoneInfo("Europe/Warsaw"))
        start, end = client._period_range(now)
        # Should start at midnight CET today, end at midnight CET in 2 days
        assert len(start) == 12
        assert len(end) == 12


# ── Serialization Tests ──────────────────────────────────────────────────────

class TestSerialization:
    """Tests for price serialization."""

    def test_serialize_prices(self, client):
        """Test price serialization to dict list."""
        prices = [
            ConvertedPrice(
                start=datetime(2025, 1, 16, 0, 0, tzinfo=timezone.utc),
                end=datetime(2025, 1, 16, 1, 0, tzinfo=timezone.utc),
                value=Decimal("0.4523"),
                raw_eur_mwh=Decimal("78.50"),
            ),
        ]
        result = client._serialize_prices(prices)
        assert len(result) == 1
        assert result[0]["value"] == 0.4523
        assert result[0]["raw_eur_mwh"] == 78.50
        assert "start" in result[0]
        assert "end" in result[0]
        assert "start_local" in result[0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
