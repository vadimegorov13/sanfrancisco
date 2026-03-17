# San Francisco Neighborhood Issue Pressure

Data Mining course project based on the data sets from https://data.sfgov.org/

## Project Structure

```text
sanfrancisco/
├── src/
│   ├── database/
│   │   └── db_connector.py
│   ├── preprocessing/
│   │   └── data_cleaner.py
│   └── utils/
│       ├── data_loader.py
│       └── logger.py
├── main.py
├── requirements.txt
└── .env.example
```

## Setup

### 1. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure database access

```bash
cp .env.example .env
```

Then edit `.env` with your local MySQL credentials.

## Load the datasets into MySQL

The loader supports:

- dataset ID
- target table name
- selected columns
- a WHERE clause
- replace/append/fail behavior
- optional sample preview

### 311 Cases

```bash
python main.py load \
  --dataset vw6y-z8j6 \
  --table sf_311_cases \
  --columns "service_request_id,requested_datetime,closed_date,updated_datetime,status_description,agency_responsible,service_name,service_subtype,service_details,address,street,supervisor_district,neighborhoods_sffind_boundaries,analysis_neighborhood,police_district,lat,long,source,data_as_of,data_loaded_at" \
  --where "requested_datetime >= '2024-01-01T00:00:00' AND requested_datetime < '2026-04-01T00:00:00' AND analysis_neighborhood IS NOT NULL AND neighborhoods_sffind_boundaries IS NOT NULL AND source = 'Mobile/Open311' AND status_description = 'Closed'" \
  --exists replace \
  --sample 1
```

### Utility Excavation Permits

```bash
python main.py load \
  --dataset smdf-6c45 \
  --table sf_utility_excavation_permits \
  --columns "permit_number,streetname,cross_street_1,cross_street_2,utility_contractor,permit_reason,utility_type,effective_date,expiration_date,status,cnn" \
  --where "effective_date >= '2024-01-01T00:00:00' AND effective_date < '2026-04-01T00:00:00'" \
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

## Implementation

### Initial work

I started this project by setting up the Python environment and organizing the repository structure so the work can continue cleanly as the project grows. Since the assignment requires reproducible code and a clear implementation process, I also set up the project to work with a local MySQL database where the San Francisco Open Data datasets can be stored and queried.

An important part of the initial setup was making sure the project can reliably download datasets from the San Francisco Open Data API and load them into local tables. This makes it easier to explore the data, filter it to a specific time window, and later build the analysis in a way that can be repeated without manually redoing the data collection process.

Another goal from the start was to keep the project flexible. I do not want the implementation to depend too heavily on one specific dataset combination. Instead, I want the structure of the project to make it easy to plug in another relevant dataset later and test whether it improves the analysis or reveals a new pattern.

### Working with data

For this project I decided to focus only on recent data instead of mixing older datasets with newer ones. At first I considered combining datasets that described long-term infrastructure condition, but many of them did not align well in time with the more current operational datasets. Because of that, I narrowed the scope to datasets that have useful updates through 2024, 2025, and into 2026.

This shift made the project much more coherent. Instead of trying to measure general long-term infrastructure condition, the analysis now focuses on identifying neighborhoods that are currently experiencing more pressure based on public issue reports, infrastructure work activity, and emergency incident signals.

The current approach is to use the data in a way that supports neighborhood-level comparison. The idea is not to treat any single dataset as a direct measure of neighborhood quality, but instead to combine multiple public signals that may reflect where issues are happening more often, where disruption is more common, and where unusual activity may be concentrated.

### Problem Definition

For this project I decided to focus on a city operations and infrastructure question: **how can we identify which San Francisco neighborhoods appear to be experiencing more issues in recent years using only public city data?**

Unlike problems where there is a clear labeled target, this one is less direct. There is no public dataset that simply tells us which neighborhoods are under more infrastructure pressure.

The goal is to discover patterns from recent San Francisco operational datasets and compare neighborhoods based on signals such as service requests, planned utility work, and selected emergency incidents.

### Reasoning Behind Data Selection

The datasets for this project were chosen based on two main requirements: they needed to be relevant to the problem, and they needed to have recent enough data to support a consistent analysis window.

The first dataset is SF 311 Cases (vw6y-z8j6). This is the main source of public issue and service request activity. It includes reports submitted by residents and can capture a wide variety of operational and infrastructure-related problems across the city. For this project, the dataset is useful because it provides a direct signal of where people are reporting issues. It also includes neighborhood and location-related fields that make neighborhood-level aggregation possible.

The second dataset is Utility Excavation Permits (smdf-6c45). This dataset represents planned utility-related work and excavation activity. It does not measure neighborhood problems directly, but it provides an important complementary signal. Areas with repeated excavation or utility work may be experiencing more disruption, construction activity, or ongoing maintenance. This helps the project move beyond only resident complaints and include a second type of infrastructure-related pressure.

The third dataset is Fire Incidents (wr8u-xric). This dataset is broader than the other two, so it will likely need careful filtering during the analysis. Still, it is one of the few recent datasets that provides another operational view of activity across the city, and it includes a neighborhood field that is useful for aggregation. The goal is not to use every fire incident as an infrastructure signal, but rather to explore whether certain incident categories can serve as an additional neighborhood-level indicator of unusual pressure or disruption.

Together, these three datasets provide a practical starting point for the assignment. They are recent, publicly available, and different enough from each other to support a multi-source analysis. At the same time, they are limited enough in number to keep the project manageable and reproducible.

### Analysis Window

January 1, 2024 through March 31, 2026

This window keeps the analysis focused on recent city activity and avoids combining much older records with current operational data.
