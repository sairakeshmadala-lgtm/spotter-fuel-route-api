
import heapq
import math
from pathlib import Path

import pandas as pd
import requests
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response


BASE_DIR = Path(__file__).resolve().parent.parent
CSV_FILE = BASE_DIR / "data" / "fuel-prices-for-be-assessment.csv"
COORDINATE_FILE = BASE_DIR / "data" / "validated-station-coordinates.csv"

METERS_PER_MILE = 1609.344
VEHICLE_RANGE_MILES = 500
MILES_PER_GALLON = 10
MAX_STATION_DETOUR_MILES = 5
MAX_STATIONS_FOR_OPTIMIZATION = 120


def geocode_us_location(location):
    """Geocode a US location using Nominatim."""
    response = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={
            "q": f"{location}, USA",
            "format": "jsonv2",
            "limit": 1,
            "countrycodes": "us",
        },
        headers={"User-Agent": "SpotterFuelRouteAssessment/1.0"},
        timeout=20,
    )
    response.raise_for_status()
    results = response.json()

    if not results:
        return None

    return {
        "latitude": float(results[0]["lat"]),
        "longitude": float(results[0]["lon"]),
        "display_name": results[0]["display_name"],
    }


def haversine_miles(lat1, lon1, lat2, lon2):
    """Calculate great-circle distance between two coordinates."""
    radius = 3958.8

    lat1, lon1, lat2, lon2 = map(
        math.radians, [lat1, lon1, lat2, lon2]
    )

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    return 2 * radius * math.asin(math.sqrt(a))


def get_station_route_position(station_lat, station_lon, coordinates):
    """
    Approximate a station's position along the route using the nearest
    sampled route vertex. Returns off-route distance and route position.
    """
    if not coordinates:
        return float("inf"), 0.0

    step = max(1, len(coordinates) // 400)
    sampled = coordinates[::step]

    if sampled[-1] != coordinates[-1]:
        sampled.append(coordinates[-1])

    cumulative = [0.0]

    for index in range(1, len(sampled)):
        lon1, lat1 = sampled[index - 1]
        lon2, lat2 = sampled[index]

        cumulative.append(
            cumulative[-1] + haversine_miles(
                lat1, lon1, lat2, lon2
            )
        )

    nearest_distance = float("inf")
    route_position = 0.0

    for index, (lon, lat) in enumerate(sampled):
        distance = haversine_miles(
            station_lat, station_lon, lat, lon
        )

        if distance < nearest_distance:
            nearest_distance = distance
            route_position = cumulative[index]

    return nearest_distance, route_position


def load_route_station_candidates(coordinates, route_distance_miles):
    """
    Load fuel-price candidates with approximate coordinates.
    These station matches are not independently verified.
    """
    if not COORDINATE_FILE.exists():
        raise FileNotFoundError(
            "data/validated-station-coordinates.csv was not found."
        )

    stations = pd.read_csv(COORDINATE_FILE)

    required = {
        "Latitude",
        "Longitude",
        "Retail Price",
        "Match Score",
        "Match Status",
        "Truckstop Name",
        "City",
        "State",
    }

    missing = required.difference(stations.columns)

    if missing:
        raise ValueError(
            "Station coordinate CSV is missing columns: "
            + ", ".join(sorted(missing))
        )

    stations = stations.dropna(
        subset=[
            "Latitude",
            "Longitude",
            "Retail Price",
            "Match Score",
        ]
    )

    stations = stations[
        (stations["Match Score"] >= 80)
        & (
            stations["Match Status"].astype(str).str.upper()
            == "REVIEW_REQUIRED"
        )
        & (stations["Retail Price"] > 0)
    ].copy()

    candidates = []

    sampled_route_length = max(
        get_station_route_position(
            coordinates[-1][1],
            coordinates[-1][0],
            coordinates,
        )[1],
        1.0,
    )

    for _, station in stations.iterrows():
        lat = float(station["Latitude"])
        lon = float(station["Longitude"])

        off_route, raw_position = get_station_route_position(
            lat, lon, coordinates
        )

        if off_route > MAX_STATION_DETOUR_MILES:
            continue

        position = (
            raw_position * route_distance_miles / sampled_route_length
        )

        position = min(
            max(position, 0.0),
            route_distance_miles,
        )

        candidates.append({
            "name": str(station["Truckstop Name"]),
            "city": str(station["City"]),
            "state": str(station["State"]),
            "latitude": lat,
            "longitude": lon,
            "price_per_gallon": float(station["Retail Price"]),
            "match_score": float(station["Match Score"]),
            "distance_from_route_miles": round(off_route, 2),
            "route_position_miles": position,
        })

    bins = {}

    bin_width = max(
        route_distance_miles / MAX_STATIONS_FOR_OPTIMIZATION,
        1.0,
    )

    for item in candidates:
        bin_id = int(item["route_position_miles"] // bin_width)
        bins.setdefault(bin_id, []).append(item)

    selected = []

    for bin_id in sorted(bins):
        segment = sorted(
            bins[bin_id],
            key=lambda item: (
                item["distance_from_route_miles"],
                -item["match_score"],
                item["price_per_gallon"],
            ),
        )

        selected.extend(segment[:2])

    return sorted(
        selected,
        key=lambda item: item["route_position_miles"],
    )[:MAX_STATIONS_FOR_OPTIMIZATION]


def optimize_fuel_stops(candidates, route_distance_miles):
    """
    Minimum-cost path search with fuel remaining discretized to 1-mile units.
    The vehicle starts with a full 50-gallon tank.
    The cost of the initial tank is excluded.
    """
    stations = sorted(
        candidates,
        key=lambda item: item["route_position_miles"],
    )

    nodes = [
        {
            "type": "start",
            "position": 0.0,
            "detour": 0.0,
            "station": None,
        }
    ]

    for station in stations:
        nodes.append({
            "type": "station",
            "position": station["route_position_miles"],
            "detour": station["distance_from_route_miles"],
            "station": station,
        })

    nodes.append({
        "type": "finish",
        "position": route_distance_miles,
        "detour": 0.0,
        "station": None,
    })

    start_state = (0, VEHICLE_RANGE_MILES)

    distances = {start_state: 0.0}
    previous = {}

    heap = [(0.0, 0, VEHICLE_RANGE_MILES)]
    goal_state = None

    while heap:
        cost, node_index, fuel_left = heapq.heappop(heap)

        state = (node_index, fuel_left)

        if cost > distances.get(state, float("inf")) + 1e-9:
            continue

        if nodes[node_index]["type"] == "finish":
            goal_state = state
            break

        current = nodes[node_index]
        station = current["station"]

        # Purchase one mile of driving range at this station.
        if station is not None and fuel_left < VEHICLE_RANGE_MILES:
            next_state = (node_index, fuel_left + 1)

            next_cost = cost + (
                station["price_per_gallon"] / MILES_PER_GALLON
            )

            if next_cost < distances.get(next_state, float("inf")):
                distances[next_state] = next_cost
                previous[next_state] = (state, "buy")

                heapq.heappush(
                    heap,
                    (next_cost, next_state[0], next_state[1]),
                )

        # Drive to any later station or the destination.
        for next_index in range(node_index + 1, len(nodes)):
            target = nodes[next_index]

            route_gap = target["position"] - current["position"]

            travel_miles = math.ceil(
                max(0.0, route_gap)
                + current["detour"]
                + target["detour"]
            )

            if travel_miles > fuel_left:
                continue

            next_state = (
                next_index,
                fuel_left - travel_miles,
            )

            if cost < distances.get(next_state, float("inf")):
                distances[next_state] = cost
                previous[next_state] = (state, "drive")

                heapq.heappush(
                    heap,
                    (cost, next_state[0], next_state[1]),
                )

    if goal_state is None:
        return None, None

    # Reconstruct the selected route and fuel purchases.
    actions = []
    state = goal_state

    while state != start_state:
        prior_state, action = previous[state]
        actions.append((prior_state, state, action))
        state = prior_state

    actions.reverse()

    purchases = {}

    for prior_state, next_state, action in actions:
        if action == "buy":
            station_index = prior_state[0]

            purchases[station_index] = (
                purchases.get(station_index, 0) + 1
            )

    stops = []

    for station_index, range_miles in purchases.items():
        station = nodes[station_index]["station"]

        gallons = range_miles / MILES_PER_GALLON
        price = station["price_per_gallon"]

        stops.append({
            "name": station["name"],
            "city": station["city"],
            "state": station["state"],
            "latitude": station["latitude"],
            "longitude": station["longitude"],
            "price_per_gallon": round(price, 3),
            "gallons_to_purchase": round(gallons, 2),
            "estimated_cost": round(gallons * price, 2),
            "distance_from_route_miles":
                station["distance_from_route_miles"],
            "route_position_miles":
                round(station["route_position_miles"], 2),
            "match_score": station["match_score"],
            "station_identity_status": "UNVERIFIED_CANDIDATE",
        })

    stops.sort(
        key=lambda item: item["route_position_miles"]
    )

    total_cost = sum(
        stop["estimated_cost"] for stop in stops
    )

    return stops, round(total_cost, 2)


@api_view(["GET"])
def fuel_prices(request):
    try:
        if not CSV_FILE.exists():
            return Response(
                {"error": "Fuel price CSV file not found."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        df = pd.read_csv(CSV_FILE)

        state = request.query_params.get("state")

        if state:
            df = df[
                df["State"].astype(str).str.upper()
                == state.strip().upper()
            ]

        df = df.sort_values("Retail Price").head(100)

        results = df.rename(columns={
            "OPIS Truckstop ID": "truckstop_id",
            "Truckstop Name": "name",
            "Address": "address",
            "City": "city",
            "State": "state",
            "Retail Price": "price_per_gallon",
        })

        columns = [
            "truckstop_id",
            "name",
            "address",
            "city",
            "state",
            "price_per_gallon",
        ]

        return Response({
            "total_records": len(df),
            "returned_records": len(results),
            "fuel_stations": results[columns].to_dict(
                orient="records"
            ),
        })

    except Exception as exc:
        return Response(
            {"error": str(exc)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
def route_preview(request):
    start = request.query_params.get("start")
    finish = request.query_params.get("finish")

    if not start or not finish:
        return Response(
            {"error": "Both start and finish locations are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        start_location = geocode_us_location(start)
        finish_location = geocode_us_location(finish)

        if not start_location or not finish_location:
            return Response(
                {"error": "Could not find one or both US locations."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        route_response = requests.get(
            "https://router.project-osrm.org/route/v1/driving/"
            f"{start_location['longitude']},{start_location['latitude']};"
            f"{finish_location['longitude']},{finish_location['latitude']}",
            params={
                "overview": "full",
                "geometries": "geojson",
                "steps": "false",
            },
            timeout=30,
        )

        route_response.raise_for_status()
        route_data = route_response.json()

        if (
            route_data.get("code") != "Ok"
            or not route_data.get("routes")
        ):
            return Response(
                {"error": "No driving route found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        route = route_data["routes"][0]

        return Response({
            "start": start_location,
            "finish": finish_location,
            "distance_miles": round(
                route["distance"] / METERS_PER_MILE,
                2,
            ),
            "duration_minutes": round(
                route["duration"] / 60,
                2,
            ),
            "route_geometry": route["geometry"],
        })

    except requests.RequestException as exc:
        return Response(
            {"error": f"External map service error: {str(exc)}"},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    except Exception as exc:
        return Response(
            {"error": str(exc)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
def fuel_optimize(request):
    start = request.query_params.get("start")
    finish = request.query_params.get("finish")

    if not start or not finish:
        return Response(
            {"error": "Please provide start and finish locations."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        start_location = geocode_us_location(start)
        finish_location = geocode_us_location(finish)

        if not start_location or not finish_location:
            return Response(
                {"error": "Could not find one or both US locations."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        route_response = requests.get(
            "https://router.project-osrm.org/route/v1/driving/"
            f"{start_location['longitude']},{start_location['latitude']};"
            f"{finish_location['longitude']},{finish_location['latitude']}",
            params={
                "overview": "full",
                "geometries": "geojson",
                "steps": "false",
            },
            timeout=30,
        )

        route_response.raise_for_status()
        route_data = route_response.json()

        if (
            route_data.get("code") != "Ok"
            or not route_data.get("routes")
        ):
            return Response(
                {"error": "No driving route found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        route = route_data["routes"][0]
        coordinates = route["geometry"]["coordinates"]

        total_distance = route["distance"] / METERS_PER_MILE

        base_response = {
            "start": start_location,
            "finish": finish_location,
            "distance_miles": round(total_distance, 2),
            "maximum_vehicle_range_miles": VEHICLE_RANGE_MILES,
            "miles_per_gallon": MILES_PER_GALLON,
            "estimated_total_fuel_required_gallons":
                round(total_distance / MILES_PER_GALLON, 2),
            "initial_fuel_assumption": (
                "Vehicle starts with a full 50-gallon tank; "
                "initial tank cost is excluded."
            ),
            "route_geometry": route["geometry"],
        }

        # No refueling is required for routes within 500 miles.
        if total_distance <= VEHICLE_RANGE_MILES:
            base_response.update({
                "fuel_stations_found": 0,
                "fuel_stops": [],
                "total_fuel_cost": 0.0,
                "optimization_status": "NO_REFUEL_REQUIRED",
                "message": (
                    "The trip is within the initial full-tank range. "
                    "No fuel purchase is required during this trip; "
                    "the cost of fuel already in the tank is excluded."
                ),
            })

            return Response(base_response)

        candidates = load_route_station_candidates(
            coordinates,
            total_distance,
        )

        stops, total_cost = optimize_fuel_stops(
            candidates,
            total_distance,
        )

        if stops is None:
            base_response.update({
                "fuel_stations_found": len(candidates),
                "fuel_stops": [],
                "total_fuel_cost": None,
                "optimization_status":
                    "NO_FEASIBLE_ROUTE_WITH_AVAILABLE_STATIONS",
                "warning": (
                    "The supplied candidate dataset does not contain "
                    "a reachable sequence of stations for this route. "
                    "Station coordinates are approximate and unverified."
                ),
            })

            return Response(
                base_response,
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        base_response.update({
            "fuel_stations_found": len(candidates),
            "fuel_stops": stops,
            "total_fuel_cost": total_cost,
            "currency": "USD",
            "optimization_status":
                "COST_MINIMIZED_WITHIN_CANDIDATE_DATASET",
            "optimization_method": (
                "Shortest-path search with fuel remaining "
                "discretized to 1-mile increments; initial tank is full."
            ),
            "station_data_warning": (
                "Station coordinates are approximate city/state name "
                "matches with score >= 80. They are not independently "
                "verified; confirm station identity and availability "
                "before relying on them."
            ),
            "cost_scope": (
                "Includes fuel purchased at selected stops only. "
                "Excludes the cost of the initial full tank and "
                "any unlisted stations."
            ),
        })

        return Response(base_response)

    except FileNotFoundError as exc:
        return Response(
            {"error": str(exc)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    except requests.RequestException as exc:
        return Response(
            {"error": f"Map service error: {str(exc)}"},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    except Exception as exc:
        return Response(
            {"error": str(exc)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
