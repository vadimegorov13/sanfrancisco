"""
For initial data exploration, visualization, and analysis.
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Visualization style
sns.set_style('whitegrid')
plt.rcParams['figure.figsize'] = (12, 6)

def explore_data(df: pd.DataFrame):
    print("DATASET OVERVIEW")
    print(f"\nShape: {df.shape}")
    print(f"\nData Types:\n{df.dtypes}")
    print(f"\nMissing Values:\n{df.isnull().sum()}")
    print(f"\nBasic Statistics:\n{df.describe()}")
    
    # TODO: Visualization code and other stuff

if __name__ == "__main__":
    # Load your data here
    # df = pd.read_csv('data/raw/your_data.csv')
    # explore_data(df)
    pass
