
import pandas as pd

# Load the training dataset
df = pd.read_csv("data/train.csv")

# Display basic information
print("\n--- Dataset Shape ---")
print(df.shape)

print("\n--- Column Names ---")
print(df.columns.tolist())

print("\n--- First 5 Rows ---")
print(df.head())

print("\n--- Missing Values ---")
print(df.isnull().sum())

print("\n--- Placement Status Distribution ---")
print(df["PlacementStatus"].value_counts())
    