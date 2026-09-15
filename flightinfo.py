import os
import time
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("SWEDAVIA_API_KEY")
BASE_URL = "https://api.swedavia.se/flightinfo/v2"

HEADERS = {
    "Ocp-Apim-Subscription-Key": API_KEY,
    "Accept": "application/json"
}

# Swedavia airports (IATA codes)
AIRPORTS = {
    "ARN": "Stockholm Arlanda",
    "BMA": "Stockholm Bromma",
    "GOT": "Göteborg Landvetter",
    "MMX": "Malmö",
    "LLA": "Luleå",
    "UME": "Umeå",
    "OSD": "Åre Östersund",
    "VBY": "Visby",
    "RNB": "Ronneby",
    "KRN": "Kiruna",
}

STOCKHOLM_TZ = ZoneInfo("Europe/Stockholm")
PAGE_SIZE = 50


def parse_date_input(raw: str) -> str:
    """Convert user-friendly date words into YYYY-MM-DD format."""
    raw = raw.strip().lower()
    today = datetime.now(timezone.utc).date()
    if raw in ("nu", "idag", "today", "now"):
        return today.strftime("%Y-%m-%d")
    if raw in ("imorgon", "tomorrow"):
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")
    if raw in ("igår", "igar", "yesterday"):
        return (today - timedelta(days=1)).strftime("%Y-%m-%d")
    return raw  # assume already in YYYY-MM-DD format


def resolve_airport(raw: str) -> str | None:
    """Accept either an IATA code or a partial city name."""
    raw = raw.strip().upper()
    if raw in AIRPORTS:
        return raw
    for code, name in AIRPORTS.items():
        if raw.lower() in name.lower():
            return code
    return None


def to_local(utc_str: str | None) -> str:
    if not utc_str:
        return "-"
    dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
    local = dt.astimezone(STOCKHOLM_TZ)
    return local.strftime("%H:%M CET")


def to_utc_display(utc_str: str | None) -> str:
    if not utc_str:
        return "-"
    dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
    return dt.strftime("%H:%M UTC")


def _print_flight(flight: dict, index: int, home_airport: str, flight_type: str):
    flight_id = flight.get("flightId", "N/A")
    airline = flight.get("airlineOperator", {}) or {}
    airline_name = airline.get("name", "Unknown")
    airline_iata = airline.get("iata", "")

    leg_id = flight.get("flightLegIdentifier", {}) or {}

    if flight_type == "A":
        other_airport = flight.get("departureAirportEnglish", "Unknown")
        other_iata = leg_id.get("departureAirportIata", "")
        time_block = flight.get("arrivalTime", {}) or {}
        from_label = f"{other_airport} {other_iata}"
        to_label = f"({home_airport})"
    else:
        other_airport = flight.get("arrivalAirportEnglish", "Unknown")
        other_iata = leg_id.get("arrivalAirportIata", "")
        time_block = flight.get("departureTime", {}) or {}
        from_label = f"({home_airport})"
        to_label = f"{other_airport} {other_iata}"

    loc_status = flight.get("locationAndStatus", {}) or {}
    baggage = flight.get("baggage", {}) or {}
    d_i = flight.get("diIndicator", "-")

    sched = time_block.get("scheduledUtc")
    est = time_block.get("estimatedUtc")
    actual = time_block.get("actualUtc")

    print(f"[{index}] -> {flight_id} | {airline_name} ({airline_iata})")
    print(f"  From : {from_label}")
    print(f"  To   : {to_label}")
    print(f"  Status : {loc_status.get('flightLegStatusEnglish', '-')}")
    print(f"  Terminal : {loc_status.get('terminal', 'N/A')}   Gate: {loc_status.get('gate', 'N/A')}")
    print(f"  Baggage belt : {baggage.get('baggageClaimUnit', 'N/A')}")
    print(f"  Sched : {to_utc_display(sched)} -> {to_local(sched)}")
    print(f"  Est   : {to_utc_display(est) if est else '-'}")
    print(f"  Actual: {to_utc_display(actual) if actual else '-'}")
    print(f"  D/I   : {d_i}")
    print()


def _print_flights_paged(flights: list, home_airport: str, flight_type: str):
    """Print flights PAGE_SIZE at a time, waiting for user input between pages."""
    total = len(flights)
    start = 0
    while start < total:
        page = flights[start:start + PAGE_SIZE]
        for i, f in enumerate(page, start + 1):
            _print_flight(f, i, home_airport, flight_type)

        shown = min(start + PAGE_SIZE, total)
        remaining = total - shown
        print(f"— Showing {shown}/{total} — ({remaining} left)")

        if remaining <= 0:
            break

        choice = input("[Enter] next page | [a] show all | [q] back to menu: ").strip().lower()
        if choice == "q":
            print("Stopped early.")
            return
        elif choice == "a":
            for i, f in enumerate(flights[shown:], shown + 1):
                _print_flight(f, i, home_airport, flight_type)
            break
        start += PAGE_SIZE


def get_arrivals():
    raw_airport = input("Enter IATA code or city name (e.g. ARN or Visby): ")
    airport = resolve_airport(raw_airport)
    if not airport:
        print("Unknown airport.")
        return
    raw_date = input("Enter date (YYYY-MM-DD / now / today / tomorrow / yesterday): ")
    date = parse_date_input(raw_date)

    url = f"{BASE_URL}/{airport}/arrivals/{date}"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        print(f"Error {resp.status_code}: {resp.text}")
        return
    data = resp.json()
    flights = data.get("flights", [])
    if not flights:
        print("No arrivals found for that airport/date.")
        return
    _print_flights_paged(flights, airport, "A")


def get_departures():
    raw_airport = input("Enter IATA code or city name (e.g. ARN or Visby): ")
    airport = resolve_airport(raw_airport)
    if not airport:
        print("Unknown airport.")
        return
    raw_date = input("Enter date (YYYY-MM-DD / now / today / tomorrow / yesterday): ")
    date = parse_date_input(raw_date)

    url = f"{BASE_URL}/{airport}/departures/{date}"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        print(f"Error {resp.status_code}: {resp.text}")
        return
    data = resp.json()
    flights = data.get("flights", [])
    if not flights:
        print("No departures found for that airport/date.")
        return
    _print_flights_paged(flights, airport, "D")


def search_flight():
    raw_airport = input("Enter IATA code (e.g. ARN): ")
    airport = resolve_airport(raw_airport)
    if not airport:
        print("Unknown airport.")
        return
    raw_date = input("Enter date (YYYY-MM-DD / now / today): ")
    date = parse_date_input(raw_date).replace("-", "")[2:]  # convert YYYYMMDD to YYMMDD
    flight_id = input("Enter flight number (e.g. SK532): ").strip().upper()
    flight_type = input("Arrival or Departure? [a/d]: ").strip().lower()
    ftype = "A" if flight_type == "a" else "D"

    filter_expr = f"airport eq '{airport}' and scheduled eq '{date}' and flightType eq '{ftype}' and flightId eq '{flight_id}'"
    url = f"{BASE_URL}/query"
    resp = requests.get(url, headers=HEADERS, params={"filter": filter_expr})
    if resp.status_code != 200:
        print(f"Error {resp.status_code}: {resp.text}")
        return
    data = resp.json()
    raw_flights = data.get("flights", [])
    if not raw_flights:
        print("No matching flight found.")
        return
    # The query endpoint wraps each flight inside "arrival" or "departure"
    flights = [f.get("arrival") or f.get("departure") for f in raw_flights]
    for i, f in enumerate(flights, 1):
        _print_flight(f, i, airport, ftype)


def custom_query():
    print("Build an OData filter. Example fields: Airport, FlightType, Scheduled, FlightId")
    print("Example: airport eq 'ARN' and flightType eq 'D' and scheduled eq '20260915'")
    filter_expr = input("Enter your filter expression: ").strip()
    url = f"{BASE_URL}/query"
    resp = requests.get(url, headers=HEADERS, params={"filter": filter_expr})
    if resp.status_code != 200:
        print(f"Error {resp.status_code}: {resp.text}")
        return
    data = resp.json()
    raw_flights = data.get("flights", [])
    print(f"Found {len(raw_flights)} flight(s).")
    if raw_flights:
        flights = [f.get("arrival") or f.get("departure") for f in raw_flights]
        first = flights[0]
        leg_id = first.get("flightLegIdentifier", {}) or {}
        is_arrival = "arrival" in raw_flights[0]
        home = leg_id.get("arrivalAirportIata") if is_arrival else leg_id.get("departureAirportIata")
        _print_flights_paged(flights, home or "?", "A" if is_arrival else "D")


def health_check():
    url = f"{BASE_URL}/ARN/arrivals/{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
    start = time.time()
    resp = requests.get(url, headers=HEADERS)
    elapsed = round((time.time() - start) * 1000)
    if resp.status_code == 200:
        print(f"API is UP. Responded in {elapsed}ms.")
        last_mod = resp.headers.get("Last-Modified", "N/A")
        print(f"Last-Modified: {last_mod}")
    else:
        print(f"API returned an error: {resp.status_code}")


def full_demo():
    print("\n--- DEMO: Arrivals at ARN today ---")
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    url = f"{BASE_URL}/ARN/arrivals/{date}"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code == 200:
        flights = resp.json().get("flights", [])[:3]
        for i, f in enumerate(flights, 1):
            _print_flight(f, i, "ARN", "A")
    else:
        print(f"Error: {resp.status_code}")

    print("\n--- DEMO: Departures at ARN today ---")
    url = f"{BASE_URL}/ARN/departures/{date}"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code == 200:
        flights = resp.json().get("flights", [])[:3]
        for i, f in enumerate(flights, 1):
            _print_flight(f, i, "ARN", "D")
    else:
        print(f"Error: {resp.status_code}")

    print("\n--- DEMO: Health check ---")
    health_check()


def main():
    while True:
        print("=" * 55)
        print("  Swedavia FlightInfo API v2 — Python client")
        print("=" * 55)
        print("  1. Arrivals for an airport & date")
        print("  2. Departures for an airport & date")
        print("  3. Search a specific flight number")
        print("  4. Custom OData query")
        print("  5. HeartBeat - API health check")
        print("  6. Demonstrate all endpoints automatically")
        print("  q. Quit")
        print("=" * 55)
        choice = input("Choose [1-6] or q: ").strip().lower()

        if choice == "q":
            break
        elif choice == "1":
            get_arrivals()
        elif choice == "2":
            get_departures()
        elif choice == "3":
            search_flight()
        elif choice == "4":
            custom_query()
        elif choice == "5":
            health_check()
        elif choice == "6":
            full_demo()
        else:
            print("Invalid choice, try again.")


if __name__ == "__main__":
    main()