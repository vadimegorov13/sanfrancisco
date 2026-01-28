# San Francisco Data Mining Project

Data Mining course project based on the data sets from https://data.sfgov.org/

## Project Structure

```
sanfrancisco/
├── data/
│   ├── raw/          # Downloaded SF datasets
│   ├── processed/    # Cleaned data
│   └── cache/        # Temp files
├── notebooks/
│   └── exploratory_analysis.py
├── src/
│   ├── database/
│   │   └── db_connector.py      # MySQL connector
│   ├── preprocessing/
│   │   └── data_cleaner.py      # Basic cleaning functions
│   └── utils/
│       └── data_loader.py       # Data loader for SF datasets
├── main.py
├── requirements.txt
└── .env.example
```

## Setup

1. **Create virtual environment:**

```bash
python -m venv venv

source venv/bin/activate

pip install -r requirements.txt
```

2. **Configure database:**

```bash
cp .env.example .env
# Edit .env with MySQL variables
```

3. **Inject datasets into local MySQL database:**

Load datasets from the SF Database

```bash
# 311 cases
python main.py load --dataset vw6y-z8j6 --table sf_311_cases --columns "service_request_id, requested_datetime, closed_date, agency_responsible, service_name, service_subtype, service_details, address, street, neighborhoods_sffind_boundaries, analysis_neighborhood, lat, long, source" --where "status_description='Closed'" --sample 1 --limit 80000

python main.py load --dataset smdf-6c45 --table sf_utility_excavation_permits --columns "permit_number, streetname, cross_street_1, cross_street_2, utility_contractor, permit_reason, utility_type, effective_date, expiration_date, status" --sample 1

python main.py load --dataset gfpk-269f --table sf_find_neighborhoods --columns "the_geom, name" --sample 1

```

4. **Run the avaluation of the data**

```bash
python main.py analyze
```

## Implementation

### Initial work

I've started from the set up of the python environment and architecture of the project for the easy of continuous work. One of the steps involved the implemention of the database connector to establish the connection between this project and my MySQL database. Also, an important step was intitiation of the formatter into the project for good redibility and consistency in code style.

### Working with data

Working with the SF data API, knowing that my project will evolve into using myltiple dataset to find correlation I've implemnted a simple yet robust function for collecting the data using SF API. by providing some argument like API endpoint and table name it is enough to create a table in the local database and download data using SF databse API.

### Problem Definition

For this project I decided to pick the issue from my own experience dealing with unreliable internet connectivity during my gaming hours that roughly starts at 7pm until 2am. While living in Anchorage, Alaska, I use GCI as my internet provider (because this is the only option apparently) and often run into connection issues during online competitive gaming. And after months of back-and-forth discussion with GCI's support team the connectivity issue has not been resolved.

That experience raised a practical question: if I ever want to move to San Francisco, how would I know which areas are more likely to have stable internet connectivity, especially in the evenings when my online activity is highest? After a quick research (I've googled "which area in SF has the best internet connectivity") I could not find a reliable source on identifiing the areas with the best internet quality. So I think answering this question requires looking at indirect signals using available San Fransico datasets, and that this problem is a perfect for this assignment.

#### Problem Title

**_Urban Infrastructure Reliability During Peak Online Activity Hours_**

### Reasoning Behind Data Selection

Since there is no public dataset that directly shows internet quality or reliability by neighborhood, this project relies on indirect but realistic signals that can impact internet connectivity, especially during evening and nighttime hours.

The **SF 311 Cases** dataset (vw6y-z8j6) is used in a heavily filtered form. Instead of downloading the entire dataset, only request types related to power outages, street light issues, and utility-related disruptions are included. These types of incidents are related to infrastructure failures that can affect home and neighborhood-level internet connectivity.

**Dataset:** https://data.sfgov.org/City-Infrastructure/311-Cases/vw6y-z8j6

**Streetlighta** dataset (6tt8-ugnj) is included as a proxy for local power stability. When streetlights are out, it often indicates broader issues in the area, which can also affect internet connectivity. This dataset is relatively small and include clear timestamps, making it possible to measure how frequently outages occur and how long they take to resolve.

**Dataset:** https://data.sfgov.org/City-Infrastructure/Streetlights/6tt8-ugnj

**Utility and excavation permit** datasets are used to capture planned construction activity. Utility digging and excavation work is a known cause of temporary service disruptions, including fiber cuts and localized outages. Including this data helps identify areas that may be at higher risk of connectivity issues due to ongoing or frequent infrastructure work.

**Datasets:**

**Utility Excavation Permits (smdf-6c45):** https://data.sfgov.org/City-Infrastructure/Utility-Excavation-Permits/smdf-6c45

**Large Utility Excavation Permits (i926-ujnc):** https://data.sfgov.org/City-Infrastructure/Large-Utility-Excavation-Permits/i926-ujnc

**Neighborhood boundary** dataset (pty2-tcw4) is used as a spatial layer to group events and compare patterns across different areas of San Francisco. This allows the analysis to move from individual incidents to neighborhood-level reliability trends.

**Dataset:** https://data.sfgov.org/Geographic-Locations-and-Boundaries/SF-Find-Neighborhoods/pty2-tcw4

Finally, external broadband availability data from the FCC is used to understand which areas have more provider options or access to fiber.

**Dataset:** https://www.fcc.gov/broadbanddata

Together, these datasets provide a realistic and manageable way to study urban infrastructure reliability during peak online activity hours, using publicly available data.
