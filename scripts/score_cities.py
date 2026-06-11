#!/usr/bin/env python3
"""
Supply-Demand Reactivation Opportunity Engine — City Scorer

Usage:
    python3 score_cities.py supply_demand.json dormant.json [--output city_scores.json]

Input JSON formats:
    supply_demand.json — list of rows from sql/01_supply_demand_onboarding.sql
    dormant.json       — list of rows from sql/02_dormant_pool.sql

Output:
    city_scores.json   — cities sorted by priority_score DESC with scoring breakdown
"""

import json
import sys
import argparse
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────────────────

MIN_ACTIVE_COURIERS = 100  # Filter out cities too small to reactivate meaningfully

WEIGHTS = {
    "demand":         0.35,  # Orders per active courier (demand pressure per supply unit)
    "supply_decline": 0.25,  # WoW% courier count drop
    "dormant":        0.25,  # Dormant pool depth
    "eta":            0.15,  # Average delivery time (ETA pressure)
}

TIER_THRESHOLDS = {
    "Critical":    70,
    "Opportunity": 40,
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def normalize(values: list[float]) -> list[float]:
    """Scale values to [0, 100] by dividing by the max."""
    mx = max(values) if values else 1
    if mx == 0:
        return [0.0] * len(values)
    return [round(100.0 * v / mx, 1) for v in values]


def tier(score: float) -> str:
    if score >= TIER_THRESHOLDS["Critical"]:
        return "Critical"
    if score >= TIER_THRESHOLDS["Opportunity"]:
        return "Opportunity"
    return "Stable"


def tier_icon(t: str) -> str:
    return {"Critical": "🔴", "Opportunity": "🟡", "Stable": "🟢"}.get(t, "")


# ── Core scoring ──────────────────────────────────────────────────────────────

def score_cities(supply_demand: list[dict], dormant: list[dict]) -> list[dict]:
    # Build dormant lookup
    dorm_map = {
        (r["CITY"], r["COUNTRY"]): int(r.get("DORMANT_COURIERS", 0))
        for r in dormant
    }

    # Filter + enrich
    cities = []
    for r in supply_demand:
        active = float(r.get("ACTIVE_COURIERS") or r.get("active_couriers") or 0)
        if active < MIN_ACTIVE_COURIERS:
            continue
        city    = r.get("CITY") or r.get("city")
        country = r.get("COUNTRY") or r.get("country")
        cities.append({
            "city":                    city,
            "country":                 country,
            "active_couriers":         int(active),
            "active_couriers_prev":    int(float(r.get("ACTIVE_COURIERS_PREV_WEEK") or r.get("active_couriers_prev_week") or 0)),
            "courier_wow_pct":         float(r.get("COURIER_WOW_PCT") or r.get("courier_wow_pct") or 0),
            "avg_hours_per_courier":   float(r.get("AVG_HOURS_PER_COURIER") or r.get("avg_hours_per_courier") or 0),
            "orders_last_week":        int(float(r.get("ORDERS_LAST_WEEK") or r.get("orders_last_week") or 0)),
            "avg_delivery_time_mins":  float(r.get("AVG_DELIVERY_TIME_MINS") or r.get("avg_delivery_time_mins") or 0),
            "total_supply_hours":      int(float(r.get("TOTAL_SUPPLY_HOURS") or r.get("total_supply_hours") or 0)),
            "applications_last_week":  int(float(r.get("APPLICATIONS_LAST_WEEK") or r.get("applications_last_week") or 0)),
            "rtd_first_deliveries":    int(float(r.get("RTD_FIRST_DELIVERIES") or r.get("rtd_first_deliveries") or 0)),
            "onboarding_conversion_28d": float(r.get("ONBOARDING_CONVERSION_28D") or r.get("onboarding_conversion_28d") or 0),
            "dormant_couriers":        dorm_map.get((city, country), 0),
        })

    if not cities:
        print("WARNING: no cities passed the MIN_ACTIVE_COURIERS filter.", file=sys.stderr)
        return []

    # Raw signal values
    demand_raw   = [c["orders_last_week"] / max(c["active_couriers"], 1) for c in cities]
    decline_raw  = [max(0.0, -c["courier_wow_pct"]) for c in cities]
    dormant_raw  = [float(c["dormant_couriers"]) for c in cities]
    eta_raw      = [c["avg_delivery_time_mins"] for c in cities]

    # Normalize each signal
    demand_scores  = normalize(demand_raw)
    decline_scores = normalize(decline_raw)
    dormant_scores = normalize(dormant_raw)
    eta_scores     = normalize(eta_raw)

    # Composite score + tier
    for i, c in enumerate(cities):
        ds  = demand_scores[i]
        ss  = decline_scores[i]
        dms = dormant_scores[i]
        es  = eta_scores[i]
        score = round(
            WEIGHTS["demand"] * ds +
            WEIGHTS["supply_decline"] * ss +
            WEIGHTS["dormant"] * dms +
            WEIGHTS["eta"] * es,
            1,
        )
        t = tier(score)
        c.update({
            "demand_score":         int(ds),
            "supply_decline_score": int(ss),
            "dormant_score":        int(dms),
            "eta_pressure_score":   int(es),
            "priority_score":       int(score),
            "tier":                 t,
            "tier_label":           tier_icon(t) + " " + t,
        })

    cities.sort(key=lambda x: -x["priority_score"])
    return cities


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Score cities by reactivation priority")
    parser.add_argument("supply_demand", help="Path to supply_demand.json (Query A output)")
    parser.add_argument("dormant",       help="Path to dormant.json (Query B output)")
    parser.add_argument("--output", "-o", default="city_scores.json", help="Output file")
    parser.add_argument("--top", type=int, default=20, help="Print top N cities to stdout")
    args = parser.parse_args()

    with open(args.supply_demand) as f:
        supply_demand = json.load(f)
    with open(args.dormant) as f:
        dormant = json.load(f)

    cities = score_cities(supply_demand, dormant)

    with open(args.output, "w") as f:
        json.dump(cities, f, indent=2, ensure_ascii=False)

    tiers = {}
    for c in cities:
        tiers[c["tier"]] = tiers.get(c["tier"], 0) + 1

    print(f"Scored {len(cities)} cities → {args.output}")
    print(f"Tiers: " + " | ".join(f"{t}: {n}" for t, n in sorted(tiers.items())))
    print()
    print(f"{'#':<4} {'City':<22} {'Ctr':<5} {'Score':<6} {'Tier':<12} {'Orders':>8} {'Dormant':>8} {'WoW%':>6}")
    print("─" * 80)
    for i, c in enumerate(cities[:args.top], 1):
        print(
            f"{i:<4} {c['city']:<22} {c['country']:<5} {c['priority_score']:<6} "
            f"{c['tier_label']:<14} {c['orders_last_week']:>8,} {c['dormant_couriers']:>8,} {c['courier_wow_pct']:>6.1f}%"
        )


if __name__ == "__main__":
    main()
