# 🇵🇱 ENTSO-E Ceny Energii

<p align="center">
  <img src="images/logo.png" alt="ENTSO-E Ceny Energii by Smarting HOME" width="200">
</p>

<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg" alt="HACS"></a>
  <a href="https://www.home-assistant.io/"><img src="https://img.shields.io/badge/Home%20Assistant-2024.1+-blue.svg" alt="HA"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License"></a>
  <a href="https://smartinghome.pl"><img src="https://img.shields.io/badge/Smarting%20HOME-smartinghome.pl-00CCAA.svg" alt="Smarting HOME"></a>
</p>

---

Profesjonalna integracja HACS dla **Home Assistant**, pobierająca **ceny energii day-ahead** z platformy [ENTSO-E Transparency](https://transparency.entsoe.eu/).

Domyślnie skonfigurowana dla **Polski** — z przeliczeniem na **PLN/kWh**, automatycznym kursem EUR/PLN z **NBP** i polskim VAT 23%.

> 🏠 Wydawca: **[Smarting HOME](https://smartinghome.pl)** — inteligentne zarządzanie energią w domu

---

## ✨ Funkcje

| Funkcja | Opis |
|---------|------|
| ⚡ **Aktualna cena** | Cena energii w bieżącej godzinie |
| ⏭️ **Następna godzina** | Cena na kolejną godzinę |
| 📉 **Minimum dzisiaj** | Najniższa cena dnia + godzina |
| 📈 **Maksimum dzisiaj** | Najwyższa cena dnia + godzina |
| 📊 **Średnia dzisiaj** | Średnia cena dnia |
| 💰 **Najtańsze 3h** | Najtańsze 3 kolejne godziny |
| 🏦 **Auto-kurs NBP** | Automatyczny kurs EUR/PLN z Narodowego Banku Polskiego |
| 📋 **Ceny today/tomorrow** | Pełna lista cen w atrybutach sensora |
| 🇵🇱 **Polski interfejs** | Pełne tłumaczenie na język polski |
| 🌍 **60+ stref** | Wszystkie europejskie bidding zones |

## 📦 Instalacja

### HACS (zalecane)

1. Otwórz **HACS → Integracje**
2. Kliknij **⋮** → **Repozytoria niestandardowe**
3. Dodaj URL: `https://github.com/GregECAT/entsoe-e`
4. Kategoria: **Integracja**
5. Zainstaluj **ENTSO-E Ceny Energii**
6. Uruchom ponownie Home Assistant

### Ręcznie

1. Skopiuj folder `custom_components/entsoe_prices/` do katalogu `custom_components/` w Home Assistant
2. Uruchom ponownie Home Assistant

## ⚙️ Konfiguracja

<p align="center">
  <img src="images/icon.png" alt="ENTSO-E Ceny Energii icon" width="56">
</p>

1. **Settings → Devices & Services → Add Integration**
2. Wyszukaj **"ENTSO-E Ceny Energii"**
3. Wypełnij formularz:

| Pole | Opis | Domyślnie |
|------|------|-----------|
| 🔑 **Klucz API** | Token z [ENTSO-E](https://transparency.entsoe.eu/myAccount/webApiAccess) | — (wymagany) |
| 🌍 **Strefa cenowa** | Bidding zone | 🇵🇱 Polska |
| 💱 **Waluta** | EUR lub PLN | PLN |
| ⚡ **Jednostka** | kWh lub MWh | kWh |
| 🧾 **VAT (%)** | Stawka VAT | 23.0 |
| 🏦 **Auto-kurs NBP** | Automatyczny kurs walut | ✅ Tak |
| 📝 **Kurs ręczny** | Gdy auto-kurs wyłączony | 4.30 |
| 🔌 **Encja RCE** | Entity ID sensora RCE PSE (spread) | `sensor.rce_pse_cena` |

### Jak uzyskać klucz API

1. Zarejestruj konto na [transparency.entsoe.eu](https://transparency.entsoe.eu/)
2. Wyślij email na `transparency@entsoe.eu` z tematem *"Restful API access"*
3. Po aktywacji: **My Account → Web API Security Token**

> 📖 Pełna dokumentacja API: [Postman Collection](https://documenter.getpostman.com/view/7009892/2s93JtP3F6)

## 📊 Sensory (Entities)

> 📖 **Pełna dokumentacja sensorów:** [docs/SENSORS.md](docs/SENSORS.md) — wzory, instrukcje, przykłady automatyzacji

Po konfiguracji pojawią się **26 sensorów** (22 zwykłe + 4 binarne):

### Ceny hurtowe

| Sensor | Entity ID | Opis |
|--------|-----------|------|
| ⚡ Aktualna cena | `sensor.entsoe_current_price` | Cena w bieżącej godzinie (PLN/kWh) |
| ⏭️ Następna godzina | `sensor.entsoe_next_hour_price` | Cena na kolejną godzinę |
| 📉 Minimum | `sensor.entsoe_today_min` | Najniższa cena dnia |
| 📈 Maksimum | `sensor.entsoe_today_max` | Najwyższa cena dnia |
| 📊 Średnia | `sensor.entsoe_today_avg` | Średnia cena dnia |

### Koszt all-in (realny koszt zakupu z sieci)

| Sensor | Entity ID | Opis |
|--------|-----------|------|
| 💵 All-in teraz | `sensor.entsoe_all_in_cost_now` | Cena + marża + akcyza + dystrybucja + VAT |
| 💵 All-in +1h | `sensor.entsoe_all_in_cost_next_hour` | Pełny koszt na kolejną godzinę |
| ⬇️ All-in min | `sensor.entsoe_all_in_min_today` | Najniższy pełny koszt dnia |
| ⬆️ All-in max | `sensor.entsoe_all_in_max_today` | Najwyższy pełny koszt dnia |

### Okna cenowe

| Sensor | Entity ID | Opis |
|--------|-----------|------|
| 💰 Najtańsze 2h/3h/4h | `sensor.entsoe_cheapest_*_avg` | Najlepsze okna ładowania |
| 📈 Najdroższe 2h/3h | `sensor.entsoe_most_expensive_*_avg` | Najlepsze okna sprzedaży |

### Analityka

| Sensor | Entity ID | Opis |
|--------|-----------|------|
| 🔢 Ranking | `sensor.entsoe_rank_current_hour` | Pozycja cenowa (1 = najtańsza) |
| 📊 Percentyl | `sensor.entsoe_percentile_current_hour` | 0% = najtaniej, 100% = najdrożej |
| Δ Delta +1h/+3h | `sensor.entsoe_delta_1h` / `delta_3h` | Zmiana ceny w przyszłości |

### Binary sensors (ON/OFF)

| Sensor | Entity ID | ON gdy... |
|--------|-----------|-----------|
| 🔋 Okno ładowania | `binary_sensor.entsoe_in_cheapest_window` | Teraz w najtańszym 3h oknie |
| 💰 Okno sprzedaży | `binary_sensor.entsoe_in_most_expensive_window` | Teraz w najdroższym 3h oknie |
| 📈 Trend rosnący | `binary_sensor.entsoe_trend_up_3h` | Ceny rosną przez 3h |
| 📉 Trend malejący | `binary_sensor.entsoe_trend_down_3h` | Ceny maleją przez 3h |

### Sensory RCE Spread (opcjonalne — wymaga integracji RCE PSE)

| Sensor | Entity ID | Opis |
|--------|-----------|------|
| 💱 Cena RCE teraz | `sensor.entsoe_rce_price_now` | Bieżąca cena RCE (PLN/kWh) |
| 📊 Spread kupno/sprzedaż | `sensor.entsoe_spread_buy_vs_sell_now` | RCE sell − ENTSO-E all-in buy |
| 📈 Spread peak dzisiaj | `sensor.entsoe_spread_buy_vs_sell_peak_today` | Max RCE − Min all-in (potencjał) |
| 🔋 Arbitraż baterii | `sensor.entsoe_spread_battery_arb_now` | Spread z uwzgl. strat baterii (90%) |

> **Spread > 0** = opłaca się sprzedawać | **Spread < 0** = ładuj baterię  
> Instrukcja konfiguracji RCE: [docs/SENSORS.md#instrukcja-konfiguracji-rce](docs/SENSORS.md#instrukcja-konfiguracji-rce)

### Atrybuty sensora `current_price`

```yaml
prices_today:
  - start: "2025-01-15T00:00:00+01:00"
    end: "2025-01-15T01:00:00+01:00"
    start_local: "00:00"
    value: 0.4523                    # PLN/kWh
    raw_eur_mwh: 78.50               # oryginalna cena EUR/MWh
  - ...
prices_tomorrow: [...]               # Dostępne ok. 13:00 CET
tomorrow_available: true
exchange_rate: 4.3215                # kurs NBP
updated_at: "2025-01-15T12:30:00+00:00"
today_min: 0.2105
today_max: 0.8734
today_avg: 0.4521
today_min_hour: "03:00"
today_max_hour: "18:00"
cheapest_hours_start: "02:00"
cheapest_hours_end: "05:00"
cheapest_hours_avg: 0.2234
```

## 📈 Wizualizacja — przykłady kart Lovelace

### ApexCharts Card

```yaml
type: custom:apexcharts-card
header:
  title: ⚡ Ceny energii — dzisiaj
  show: true
graph_span: 24h
span:
  start: day
series:
  - entity: sensor.entsoe_current_price
    data_generator: |
      return entity.attributes.prices_today.map(p => [
        new Date(p.start).getTime(),
        p.value
      ]);
```

### Mini Graph Card

```yaml
type: custom:mini-graph-card
entities:
  - sensor.entsoe_current_price
name: Cena energii
hours_to_show: 24
points_per_hour: 1
line_color: "#00CCAA"
```

### Automatyzacja — najtańsze godziny

```yaml
automation:
  - alias: "Włącz ładowanie w najtańszych godzinach"
    trigger:
      - platform: time
        at: sensor.entsoe_cheapest_hours_avg
    condition:
      - condition: numeric_state
        entity_id: sensor.entsoe_current_price
        below: 0.30
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.charger
```

## 🔄 Aktualizacja danych

| Co | Częstotliwość |
|----|---------------|
| Ceny day-ahead | Co 30 minut |
| Kurs NBP | Raz dziennie |
| Ceny na jutro | Publikowane ok. 13:00 CET |

## 🤝 Wsparcie

- 🐛 **Błędy**: [GitHub Issues](https://github.com/GregECAT/entsoe-e/issues)
- 🏠 **Smarting HOME**: [smartinghome.pl](https://smartinghome.pl)
- 📖 **API Docs**: [Postman Collection](https://documenter.getpostman.com/view/7009892/2s93JtP3F6)
- 📧 **ENTSO-E**: [transparency@entsoe.eu](mailto:transparency@entsoe.eu)

## 📄 Licencja

MIT License — [LICENSE](LICENSE)

---

<p align="center">
  <strong>Powered by <a href="https://smartinghome.pl">Smarting HOME</a></strong><br>
  <em>Dane z <a href="https://transparency.entsoe.eu/">ENTSO-E Transparency Platform</a> · Kurs walut z <a href="https://api.nbp.pl/">API NBP</a></em>
</p>
