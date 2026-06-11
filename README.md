# Weekly Supply-Demand Reactivation Opportunity Engine

Automated weekly engine that ranks Wolt cities by courier reactivation urgency. Runs every Monday at 08:00 and refreshes a public Google Sheet dashboard.

## 📊 Live Dashboard

[View the live dashboard →](https://docs.google.com/spreadsheets/d/1_gL4Aac5xQ3pKuR4Cli3IMeJCwDyx4yswZmgfe_v9BA/pubhtml)

The dashboard has 4 tabs:
- **🏆 City Ranking** — all cities ranked by priority score
- **🔍 City Deep Dive** — full metrics for every city
- **🚀 RTD Activation** — top 50 cities by dormant + RTD opportunity
- **📖 Glossary & FAQ** — metric definitions and scoring explained

## How It Works

Each Monday, the engine:
1. Pulls last week's supply, demand and onboarding data from Snowflake
2. Computes a weighted priority score per city (normalized 0–100)
3. Overwrites the Google Sheet with fresh rankings

### Scoring Model

| Component | Weight | Signal | Source |
|-----------|--------|--------|--------|
| Demand Intensity | 35% | Orders ÷ Active Couriers (normalized) | `FLEET_SUPPLY_HOURS` |
| Supply Decline | 25% | Courier WoW % drop (max(0, -WoW%)) | `CITY_METRICS_GD` |
| Dormant Pool | 25% | Dormant courier count (normalized) | `COURIER_PARTNER_METRICS` |
| ETA Pressure | 15% | Avg delivery time (normalized) | `FLEET_SUPPLY_HOURS` |

**Tier thresholds:**
- 🔴 Critical ≥ 70
- 🟡 Opportunity 40–69
- 🟢 Stable < 40

### Definitions

**Dormant courier:** Active (≥1 delivery) in weeks 5–24 ago, zero deliveries in last 4 weeks. Primary CRM reactivation target.

**RTD conversion:** Couriers who made their first delivery this week (`COUNT_FIRST_DELIVERIES`). Proxy for the onboarding-complete pool converting.

Only cities with ≥ 100 active couriers are included to filter out small-sample noise.

## Data Sources

All data from `PRODUCTION` database on `DOORDASH-IG78751_AWS_EU_WEST_1` (Wolt Snowflake):

| Table | Usage |
|-------|-------|
| `PRODUCTION.COURIER.CITY_METRICS_GD` | Active couriers, WoW change, active hours |
| `PRODUCTION.COURIER.FLEET_SUPPLY_HOURS` | Orders, avg delivery time, supply hours |
| `PRODUCTION.COURIER.COURIER_PARTNER_METRICS` | Individual courier delivery history (dormant calc) |
| `PRODUCTION.COURIER.ONBOARDING_METRICS_GD` | First deliveries, applications, conversion rates |

## Repository Structure

```
reactivation-engine/
├── README.md
├── sql/
│   ├── 01_supply_demand_onboarding.sql   # Query A: fast, pre-aggregated
│   └── 02_dormant_pool.sql               # Query B: heavy, run separately
└── scripts/
    └── score_cities.py                   # Scoring + normalization logic
```

## Running Manually

Requires Wolt Snowflake access (`EXPLORATION_XS` warehouse) and Google Sheets API credentials.

```bash
# 1. Run Snowflake queries (see sql/ folder)
# 2. Score cities
python3 scripts/score_cities.py supply_demand.json dormant.json

# Output: city_scores.json sorted by priority_score DESC
```

## Configuration

| Setting | Value |
|---------|-------|
| Snowflake account | `DOORDASH-IG78751_AWS_EU_WEST_1` |
| Warehouse | `EXPLORATION_XS` |
| Schedule | Every Monday 08:00 (local time) |
| Min city size | 100 active couriers |
| Google Sheet ID | `1_gL4Aac5xQ3pKuR4Cli3IMeJCwDyx4yswZmgfe_v9BA` |

## Owner

Built by [Cayo Silva](mailto:cayo.silva@wolt.com) — Wolt CRM team.
