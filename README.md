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
# Edit .env with your MySQL credentials
```

3. **Run:**
```bash
python main.py
```
