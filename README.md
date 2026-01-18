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

3. **Run:**

```bash
python main.py
```

## Implementation

### Initial work

I've started from the set up of the python environment and architecture of the project for the easy of continuous work. One of the steps involved the implemention of the databse connector to establish the connection between this project and my MySQL database. Also, an important step was intitiation of the formatter into the project for good redibility and consistency in code style.

### Working with data

Working with the SF data API, knowing that my project will eveolve into using myltiple dataset to find correlation I've implemnted a simple yet robust function for collecting the data using SF API. by providing some argument like API endpoint and table name it is enough to create a table in the local database and download data using SF databse API.
