#!/bin/bash
set -euo pipefail

python3 <<'PY'
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

START = "depot_start"
END = "depot_end"
DATA_PATH = Path("/root/data.json")
OUTPUT_PATH = Path("/root/report.json")

# Deterministic controlled-local-snapshot construction for the pinned data.json.
# Positive service means pickup; negative service means dropoff.
VEHICLE_PLANS = [
    {
        "vehicle_id": 1,
        "start_load": 0,
        "services": [
            (150, 13),
            (302, 7),
            (433, 3),
            (285, -20),
            (432, 3),
            (301, 6),
            (229, -11),
            (251, 3),
            (265, -4),
        ],
    },
    {
        "vehicle_id": 2,
        "start_load": 10,
        "services": [
            (312, 1),
            (335, 6),
            (280, -3),
            (285, -14),
            (297, 20),
            (326, 4),
            (317, -8),
        ],
    },
]


def great_circle_miles(a: dict[str, float], b: dict[str, float]) -> float:
    lat1 = float(a["latitude"])
    lon1 = float(a["longitude"])
    lat2 = float(b["latitude"])
    lon2 = float(b["longitude"])
    degrees_to_radians = math.pi / 180.0
    phi1 = (90.0 - lat1) * degrees_to_radians
    phi2 = (90.0 - lat2) * degrees_to_radians
    theta1 = lon1 * degrees_to_radians
    theta2 = lon2 * degrees_to_radians
    cos_arc = math.sin(phi1) * math.sin(phi2) * math.cos(theta1 - theta2) + math.cos(phi1) * math.cos(phi2)
    cos_arc = max(-1.0, min(1.0, cos_arc))
    return math.acos(cos_arc) * 3960.0


def node_location(node: int | str, data: dict[str, Any], station_by_id: dict[int, dict[str, Any]]) -> dict[str, float]:
    if node in (START, END):
        return data["depot"]
    return station_by_id[int(node)]


def route_distance(route: list[int | str], data: dict[str, Any], station_by_id: dict[int, dict[str, Any]]) -> float:
    return sum(
        great_circle_miles(node_location(i, data, station_by_id), node_location(j, data, station_by_id))
        for i, j in zip(route, route[1:])
    )


def clean_number(value: float, digits: int = 6) -> float:
    rounded = round(float(value), digits)
    if abs(rounded - round(rounded)) < 1e-9:
        return float(round(rounded))
    return rounded


def main() -> None:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    if data.get("vehicle_count") != 2 or data.get("vehicle_capacity") != 25:
        raise ValueError("unexpected bike-rebalance snapshot; refusing to emit a stale oracle report")
    station_by_id = {int(station["id"]): station for station in data["stations"]}
    station_sums = {sid: {"pickup": 0.0, "dropoff": 0.0} for sid in station_by_id}

    vehicles: list[dict[str, Any]] = []
    travel_distance = 0.0
    for plan in VEHICLE_PLANS:
        route = [START, *[sid for sid, _service in plan["services"]], END]
        load = float(plan["start_load"])
        stops: list[dict[str, Any]] = []
        for sid, service in plan["services"]:
            if sid not in station_by_id:
                raise ValueError(f"snapshot station id {sid} is not present in data.json")
            pickup = float(max(service, 0))
            dropoff = float(max(-service, 0))
            load = load + pickup - dropoff
            if not (0.0 <= load <= float(data["vehicle_capacity"])):
                raise ValueError(f"vehicle {plan['vehicle_id']} load invariant failed at station {sid}")
            station_sums[sid]["pickup"] += pickup
            station_sums[sid]["dropoff"] += dropoff
            stops.append(
                {
                    "station_id": sid,
                    "bikes_picked_up": clean_number(pickup),
                    "bikes_dropped_off": clean_number(dropoff),
                    "load_after_stop": clean_number(load),
                }
            )
        travel_distance += route_distance(route, data, station_by_id)
        vehicles.append(
            {
                "vehicle_id": plan["vehicle_id"],
                "start_load": clean_number(float(plan["start_load"])),
                "route": route,
                "stops": stops,
                "end_load": clean_number(load),
            }
        )

    station_reports: list[dict[str, Any]] = []
    total_unmet = 0.0
    for station in data["stations"]:
        sid = int(station["id"])
        pickup = station_sums[sid]["pickup"]
        dropoff = station_sums[sid]["dropoff"]
        net_change = pickup - dropoff
        final_inventory = float(station["initial_bikes"]) - pickup + dropoff
        if not (0.0 <= final_inventory <= float(station["station_capacity"])):
            raise ValueError(f"station {sid} inventory invariant failed")
        target = float(station["net_rebalancing_target"])
        unmet = abs(target - net_change)
        total_unmet += unmet
        station_reports.append(
            {
                "station_id": sid,
                "net_rebalancing_target": clean_number(target),
                "total_bikes_picked_up": clean_number(pickup),
                "total_bikes_dropped_off": clean_number(dropoff),
                "net_bike_change": clean_number(net_change),
                "unmet_rebalancing_amount": clean_number(unmet),
            }
        )

    penalty = float(data["penalty_weight"]) * total_unmet
    objective = travel_distance + penalty
    report = {
        "summary": {
            "objective": clean_number(objective),
            "travel_distance_miles": clean_number(travel_distance),
            "unmet_rebalancing_penalty": clean_number(penalty),
            "total_unmet_rebalancing_amount": clean_number(total_unmet),
        },
        "vehicles": vehicles,
        "stations": station_reports,
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
PY
