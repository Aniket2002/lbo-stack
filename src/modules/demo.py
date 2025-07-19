import os

import pandas as pd

# Ensure the data directory exists
os.makedirs("data", exist_ok=True)

# Define the assumptions data
assumptions = {
    "Driver": [
        "Revenue CAGR (2024–29)",
        "EBITDA Margin",
        "CapEx / Revenue",
        "ΔWC / Revenue",
        "Tax Rate",
        "Entry EV / EBITDA Multiple",
        "Exit EV / EBITDA Multiple",
        "Total Debt / EV",
        "Cost of Debt (Senior/Mezz)",
        "Revolver Availability / Sweep",
        "WACC",
        "Terminal Growth (Gordon)",
    ],
    "Stress Case": [
        "4.0%",
        "19.5%",
        "4.5%",
        "1.25%",
        "26.0%",
        "8.0×",
        "7.5×",
        "50%",
        "5.0% / 7.0%",
        "50% / 75%",
        "8.0%",
        "1.0%",
    ],
    "Base Case": [
        "5.0%",
        "21.0%",
        "4.0%",
        "1.0%",
        "25.0%",
        "8.5×",
        "9.0×",
        "60%",
        "4.0% / 6.0%",
        "75% / 75%",
        "7.0%",
        "2.0%",
    ],
    "Upside Case": [
        "6.0%",
        "22.5%",
        "3.5%",
        "0.75%",
        "24.0%",
        "9.0×",
        "10.0×",
        "65%",
        "3.0% / 5.0%",
        "75% / 95%",
        "6.0%",
        "2.5%",
    ],
}

# Create DataFrame and write to CSV
df = pd.DataFrame(assumptions)
csv_path = "data/accor_assumptions.csv"
df.to_csv(csv_path, index=False)

print(f"CSV file recreated at: {csv_path}")
