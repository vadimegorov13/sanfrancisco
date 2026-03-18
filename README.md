# San Francisco Neighborhood Issue Pressure

Data mining course project (CSCE A662) using San Francisco Open Data.  
Source: https://data.sfgov.org/

**Project Question:** Which SF neighborhoods appear to experience higher recent issue pressure based on public service requests and emergency incident activity?

---

## Table of Contents

1. [Problem Definition](#problem-definition)
2. [Design Decisions](#design-decisions)
3. [Project Structure](#project-structure)
4. [Setup](#setup)
5. [Load the Datasets](#load-the-datasets)
6. [Run the Analysis](#run-the-analysis)
7. [Pipeline Overview](#pipeline-overview)
8. [Findings](#findings)
9. [Robustness](#robustness)

---

## Problem Definition

The goal is to discover patterns from San Francisco public operational datasets and build an interpretable comparison across neighborhoods.

The project focuses on **recent issue pressure**: how active a neighborhood appears to be in terms of reported public issues and selected emergency incidents, measured monthly over a consistent two-year window.

---

## Design Decisions

| Decision          | Choice                                                  | Reason                                                                                        |
| ----------------- | ------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| Primary dataset   | SF 311 Cases (`sf_311_cases`)                           | Strongest and most consistent; provides the main issue-volume signal                          |
| Secondary dataset | SF Fire Incidents (`sf_fire_incidents`)                 | Adds emergency-incident context after filtering; includes a neighborhood field                |
| Analysis window   | 2024-01-01 to 2025-12-31                                | Both datasets have stable coverage in this range;                                             |
| Unit of analysis  | Neighborhood-month                                      | Fine enough to detect temporal spikes; coarse enough to be meaningful across 41 neighborhoods |
| Neighborhood key  | `analysis_neighborhood` (311), normalized to match fire | Canonical neighborhood labels; fire labels normalized to match                                |

---

## Project Structure

```text
sanfrancisco/
├── src/
│   ├── preprocessing/
│   │   ├── filters_311.py          # 311 filtering rules and time window
│   │   ├── filters_fire.py         # fire filtering rules and time window
│   │   ├── aggregator_311.py       # 311 neighborhood-month feature builder
│   │   ├── aggregator_fire.py      # fire neighborhood-month feature builder
│   │   ├── merger.py               # outer join of 311 and fire feature tables
│   │   └── neighborhood_normalizer.py  # canonical neighborhood key mapping
│   ├── analysis/
│   │   ├── scorer.py               # composite issue-pressure score (0–100)
│   │   ├── clusterer.py            # hierarchical clustering (Ward, k=4)
│   │   ├── anomaly.py              # z-score anomaly detection
│   │   ├── robustness.py           # sensitivity checks (Story 11)
│   │   ├── plotter.py              # figure generation
│   │   └── pipeline.py             # end-to-end orchestrator
│   ├── database/
│   │   └── db_connector.py
│   └── utils/
│       ├── data_loader.py
│       └── logger.py
├── main.py
├── requirements.txt
└── .env.example
```

---

## Setup

### 1. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate   # fish: source venv/bin/activate.fish
pip install -r requirements.txt
```

### 2. Configure database access

```bash
cp .env.example .env
```

Edit `.env` with your local MySQL credentials. The pipeline reads from a local MySQL database named `assignment_1`.

---

## Load the Datasets

The loader downloads from the SF Open Data API and inserts rows into MySQL. Run once before the analysis.

### 311 Cases

```bash
python main.py load \
  --dataset vw6y-z8j6 \
  --table sf_311_cases \
  --columns "service_request_id,requested_datetime,closed_date,updated_datetime,status_description,status_notes,agency_responsible,service_name,service_subtype,service_details,address,street,supervisor_district,neighborhoods_sffind_boundaries,analysis_neighborhood,police_district,lat,long,source,data_as_of,data_loaded_at" \
  --where "requested_datetime >= '2024-01-01T00:00:00' AND requested_datetime < '2026-04-01T00:00:00' AND analysis_neighborhood IS NOT NULL AND neighborhoods_sffind_boundaries IS NOT NULL AND status_description = 'Closed' AND status_notes LIKE 'Case Resolved%' AND source IN ('Phone','Mobile/Open311','Web','Mobile') AND service_name NOT IN ('Parking Enforcement','Graffiti Public','Graffiti','Street and Sidewalk Cleaning','Street and Sidewalk Cleaning')" \
  --exists replace \
  --sample 1
```

### Fire Incidents

```bash
python main.py load \
  --dataset wr8u-xric \
  --table sf_fire_incidents \
  --columns "incident_number,id,address,incident_date,alarm_dttm,arrival_dttm,close_dttm,city,zipcode,battalion,station_area,suppression_units,suppression_personnel,ems_units,ems_personnel,estimated_property_loss,estimated_contents_loss,fire_fatalities,fire_injuries,civilian_fatalities,civilian_injuries,number_of_alarms,primary_situation,action_taken_primary,action_taken_secondary,action_taken_other,property_use,ignition_cause,heat_source,supervisor_district,neighborhood_district,data_as_of,data_loaded_at" \
  --where "incident_date >= '2024-01-01T00:00:00' AND incident_date < '2026-04-01T00:00:00'" \
  --exists replace \
  --sample 1
```

---

## Run the Analysis

```bash
python main.py analyze
```

All outputs are saved under `outputs/`:

| Directory            | Contents                                                          |
| -------------------- | ----------------------------------------------------------------- |
| `outputs/logs/`      | Timestamped run log                                               |
| `outputs/tables/`    | CSV artifacts (features, scores, clusters, anomalies, robustness) |
| `outputs/figures/`   | PNG plots                                                         |
| `outputs/summaries/` | `analysis_summary.md`, `robustness_report.md`                     |

---

## Pipeline Overview

The pipeline runs nine top-level steps, each logged to the console and the log file.

| Step                | What it does                                                                  |
| ------------------- | ----------------------------------------------------------------------------- |
| [1/9] Load          | Load `sf_311_cases` and `sf_fire_incidents` from MySQL                        |
| [2/9] Filter 311    | Apply issue-group inclusion rules and 2024–2025 time window                   |
| [3/9] Filter fire   | Apply incident-group inclusion rules and 2024–2025 time window                |
| [4/9] Normalize     | Map neighborhood labels from both datasets to a shared canonical key          |
| [5/9] 311 features  | Aggregate filtered 311 rows to neighborhood-month counts and rates            |
| [6/9] Fire features | Aggregate filtered fire rows to neighborhood-month counts and severity        |
| [7/9] Merge         | Outer join on (neighborhood, year_month); fill fire zeros for 311-only months |
| [8/9] Figures       | Generate overview plots from the merged table                                 |
| [9/9] Downstream    | Score → cluster → anomaly → robustness → summary                              |

### Feature table

The merged table contains **984 rows** (41 neighborhoods × 24 months) and **18 columns**:

| Feature group | Features                                                                                                        |
| ------------- | --------------------------------------------------------------------------------------------------------------- |
| 311 volume    | `total_311_count`, counts by issue group (street/pavement, sidewalk, sewer, streetlights, traffic signs, trees) |
| 311 breadth   | `distinct_issue_groups`, `avg_closure_days`                                                                     |
| Fire volume   | `total_fire_count`, counts by incident group (building, electrical, gas, water)                                 |
| Fire severity | `total_fire_injuries`, `avg_suppression_units`                                                                  |

### Composite score

Six non-redundant features (3 from 311, 3 from fire) are min-max scaled and combined with a 60/40 bucket weight to produce a `pressure_score` (0–100) per neighborhood-month. Per-neighborhood scores are the mean of the 24 monthly values.

The score is transparent by design: every component, weight, and direction is documented in `scorer.py`. It is **not** presented as an objective measure of neighborhood quality.

### Hierarchical clustering

All 16 features are standardized with `StandardScaler` and clustered with Ward linkage (Euclidean distance) cut at **k = 4**. k = 4 was chosen because k = 3 merges two visually distinct groups and k = 5 over-splits the low-volume tail.

### Anomaly detection

Per-feature z-scores are computed across all 984 rows. A neighborhood-month is flagged when **≥ 2 features** have z > 2.0 (positive direction only, consistent with the issue-pressure framing).

---

## Findings

### Top neighborhoods by composite issue-pressure score

| Rank | Neighborhood          |
| ---- | --------------------- |
| 1    | Mission               |
| 2    | Bayview Hunters Point |
| 3    | Sunset/Parkside       |
| 4    | West of Twin Peaks    |
| 5    | South of Market       |

Mission ranks first by a clear margin on both 311 volume and fire incident activity.

### Cluster structure (k = 4)

| Cluster | Size             | Character                                                           |
| ------- | ---------------- | ------------------------------------------------------------------- |
| 1       | 20 neighborhoods | Mid-volume, broad issue mix — the typical residential group         |
| 2       | 7 neighborhoods  | Low activity — parks, Presidio, Treasure Island, Seacliff           |
| 3       | 3 neighborhoods  | High pressure — Mission, Bayview Hunters Point, Sunset/Parkside     |
| 4       | 11 neighborhoods | Mid-high — includes South of Market, Tenderloin, Financial District |

Clusters separate primarily on overall 311 volume. Fire features contribute additional differentiation within high-volume groups.

### Anomaly detection

**121 neighborhood-months** were flagged (≥ 2 features spiked above z = 2.0) out of 984.

Top anomalies:

| Neighborhood | Month   | Spikes | Top feature                      |
| ------------ | ------- | ------ | -------------------------------- |
| Mission      | 2024-12 | 11     | `count_trees` (z = 11.86)        |
| Mission      | 2025-02 | 9      | `count_traffic_signs` (z = 7.67) |
| Mission      | 2025-07 | 9      | `count_traffic_signs` (z = 5.46) |

Mission 2024-12 is the strongest anomaly: 11 of 16 features spiked simultaneously, driven by an extreme tree-related 311 spike. This is consistent with its top ranking in the composite score and cluster 3 membership.

---

## Robustness

All five checks are run automatically during `python main.py analyze` and saved to `outputs/summaries/robustness_report.md`.

| Check                                                                | Result                                                                    |
| -------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| Score weight sensitivity (varies 311/fire split from 60/40 to 100/0) | Min Spearman ρ = **0.991** — rankings are highly stable                   |
| Score feature drop (drop each of the 6 score features in turn)       | Min top-5 overlap = **4/5**, min ρ = **0.971** — robust                   |
| Fire removed — scoring                                               | ρ = **0.991**, top-5 overlap = **5/5** — score is 311-driven              |
| Fire removed — clustering                                            | ARI = **0.304** — fire features materially affect cluster structure       |
| Cluster k sensitivity (k = 3, 4, 5)                                  | Min ARI vs k=4: **0.658** — k=4 is a reasoned choice, not uniquely stable |
| Anomaly threshold (z = 1.5, 2.0, 2.5)                                | Top anomaly (Mission 2024-12) is **consistent** across all thresholds     |

The main finding — Mission, Bayview Hunters Point, and Sunset/Parkside as the highest-pressure neighborhoods — holds under all weight and feature variations tested. Cluster assignments are more sensitive to the presence of fire features and the choice of k, which is expected and documented.
