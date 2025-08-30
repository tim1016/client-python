import datetime as dt
from polygon import RESTClient
import pandas as pd

# Replace with your actual API key from your Polygon.io dashboard
# You can also set it as an environment variable 'POLYGON_API_KEY'
# which is the recommended approach for security
# api_key = "YOUR_API_KEY"

# Initialize the Polygon.io REST client
client = RESTClient()

# Define the date and underlying ticker
date_str = "2024-01-04"
underlying_ticker = "SPY"

# Step 1: Find all active options contracts for SPY on the specified day
print(f"Fetching all active options contracts for {underlying_ticker} on {date_str}...")
options_contracts = []
try:
    for c in client.list_options_contracts(
        underlying_ticker=underlying_ticker,
        as_of=date_str,
        expired=False,  # Exclude expired contracts
        limit=1000,
    ):
        options_contracts.append(c)
    print(f"Found {len(options_contracts)} contracts.")
except Exception as e:
    print(f"Error fetching options contracts: {e}")
    exit()

if not options_contracts:
    print("No options contracts found for the specified date and ticker.")
    exit()

# Step 2: Get OHLCV data for each contract and store it
all_options_data = []
print("Fetching daily OHLCV data for each contract...")

for contract in options_contracts:
    options_ticker = contract.ticker
    try:
        # Get daily aggregates (OHLCV) for the specific date
        aggs = client.get_aggs(
            ticker=options_ticker,
            multiplier=1,
            timespan="day",
            from_=date_str,
            to=date_str,
        )

        if aggs:
            # The API returns an AggsResponse object, we are interested in the results attribute
            daily_data = aggs[0]
            # Create a dictionary with the required data
            data_row = {
                'ticker': options_ticker,
                'underlying': underlying_ticker,
                'open': daily_data.open,
                'high': daily_data.high,
                'low': daily_data.low,
                'close': daily_data.close,
                'volume': daily_data.volume,
                'date': date_str,
                'strike_price': contract.strike_price,
                'contract_type': contract.contract_type
            }
            all_options_data.append(data_row)
            print(f"✅ Data for {options_ticker} retrieved.")
        else:
            print(f"❌ No data found for {options_ticker} on {date_str}.")
    except Exception as e:
        print(f"Error fetching data for {options_ticker}: {e}")

# Convert the list of dictionaries into a pandas DataFrame for easy analysis
if all_options_data:
    df = pd.DataFrame(all_options_data)
    print("\nDataFrame created successfully:")
    print(df.head())
    # You can now save the DataFrame to a CSV or perform further analysis
    # df.to_csv("spy_options_ohlcv_jan_4_2024.csv", index=False)
else:
    print("\nNo OHLCV data was retrieved for any contracts.")