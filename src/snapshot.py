import requests
import pandas as pd
from datetime import date, datetime, timedelta
import time
from typing import Dict, List, Optional, Tuple
import json

class SPYOptionsSnapshotFetcher:
    def __init__(self, api_key: str):
        """
        Initialize the Polygon.io API client for SPY options snapshots.
        
        Args:
            api_key: Your Polygon.io API key
        """
        self.api_key = api_key
        self.base_url = "https://api.polygon.io"
        
    def get_options_snapshots_for_date(self, trade_date: str) -> Optional[Dict]:
        """
        Get all SPY options snapshots for a specific date.
        
        Args:
            trade_date: Trading date in YYYY-MM-DD format
            
        Returns:
            Dictionary containing all options data or None if error
        """
        # Convert date for the snapshot API (uses timestamp)
        date_obj = datetime.strptime(trade_date, '%Y-%m-%d')
        
        # The snapshot API gets current data, but we can use the historical endpoint
        # For historical data, we'll use the options contract endpoint with date filter
        url = f"{self.base_url}/v3/snapshot/options/SPY"
        
        params = {
            'apikey': self.api_key,
            'limit': 250,  # Max limit per request
            'order': 'asc',
            'sort': 'ticker'
        }
        
        try:
            all_results = []
            next_url = None
            page = 1
            
            while True:
                if next_url:
                    response = requests.get(next_url)
                else:
                    response = requests.get(url, params=params)
                
                response.raise_for_status()
                data = response.json()
                
                if 'results' in data and data['results']:
                    all_results.extend(data['results'])
                    print(f"  Page {page}: Retrieved {len(data['results'])} options contracts")
                    page += 1
                else:
                    print(f"  No results found for {trade_date}")
                    break
                
                # Check if there's more data
                if 'next_url' in data and data['next_url']:
                    next_url = data['next_url'] + f"&apikey={self.api_key}"
                else:
                    break
                
                # Rate limiting
                time.sleep(0.12)  # 12ms delay to stay under rate limits
            
            if all_results:
                return {
                    'date': trade_date,
                    'results': all_results,
                    'total_contracts': len(all_results)
                }
            else:
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"  Error fetching snapshots for {trade_date}: {e}")
            return None
    
    def flatten_options_data(self, snapshot_data: Dict) -> List[Dict]:
        """
        Flatten the nested options snapshot data into a list of dictionaries.
        
        Args:
            snapshot_data: Dictionary containing the snapshot data
            
        Returns:
            List of flattened option contract dictionaries
        """
        flattened_data = []
        trade_date = snapshot_data['date']
        
        for option in snapshot_data['results']:
            flat_row = {'date': trade_date}
            
            # Basic option details
            if 'details' in option:
                details = option['details']
                flat_row.update({
                    'ticker': details.get('ticker'),
                    'contract_type': details.get('contract_type'),
                    'exercise_style': details.get('exercise_style'),
                    'expiration_date': details.get('expiration_date'),
                    'shares_per_contract': details.get('shares_per_contract'),
                    'strike_price': details.get('strike_price')
                })
            
            # Day trading data
            if 'day' in option:
                day_data = option['day']
                flat_row.update({
                    'day_change': day_data.get('change'),
                    'day_change_percent': day_data.get('change_percent'),
                    'day_close': day_data.get('close'),
                    'day_high': day_data.get('high'),
                    'day_low': day_data.get('low'),
                    'day_open': day_data.get('open'),
                    'day_previous_close': day_data.get('previous_close'),
                    'day_volume': day_data.get('volume'),
                    'day_vwap': day_data.get('vwap'),
                    'day_last_updated': day_data.get('last_updated')
                })
            
            # Greeks
            if 'greeks' in option:
                greeks = option['greeks']
                flat_row.update({
                    'delta': greeks.get('delta'),
                    'gamma': greeks.get('gamma'),
                    'theta': greeks.get('theta'),
                    'vega': greeks.get('vega')
                })
            
            # Implied volatility and other metrics
            flat_row.update({
                'implied_volatility': option.get('implied_volatility'),
                'break_even_price': option.get('break_even_price'),
                'open_interest': option.get('open_interest')
            })
            
            # Last quote data
            if 'last_quote' in option:
                quote = option['last_quote']
                flat_row.update({
                    'ask': quote.get('ask'),
                    'ask_size': quote.get('ask_size'),
                    'bid': quote.get('bid'),
                    'bid_size': quote.get('bid_size'),
                    'midpoint': quote.get('midpoint'),
                    'quote_last_updated': quote.get('last_updated'),
                    'quote_timeframe': quote.get('timeframe')
                })
            
            # Underlying asset data
            if 'underlying_asset' in option:
                underlying = option['underlying_asset']
                flat_row.update({
                    'underlying_ticker': underlying.get('ticker'),
                    'underlying_price': underlying.get('price'),
                    'underlying_change_to_break_even': underlying.get('change_to_break_even'),
                    'underlying_last_updated': underlying.get('last_updated'),
                    'underlying_timeframe': underlying.get('timeframe')
                })
            
            flattened_data.append(flat_row)
        
        return flattened_data
    
    def fetch_past_n_days_snapshots(self, days: int = 7) -> pd.DataFrame:
        """
        Fetch SPY options snapshots for the past N trading days.
        
        Args:
            days: Number of past days to fetch (default 7)
            
        Returns:
            DataFrame with all options snapshots data
        """
        end_date = date.today()
        # start_date = end_date - timedelta(days=days + 5)  # Add buffer for weekends
        start_date = end_date
        

        
        # Generate list of potential trading dates (excluding weekends)
        trading_dates = []
        current_date = start_date
        while current_date <= end_date and len(trading_dates) < days:
            # Skip weekends (Saturday = 5, Sunday = 6)
            if current_date.weekday() < 5:
                trading_dates.append(current_date.strftime('%Y-%m-%d'))
            current_date += timedelta(days=1)
        
        # Get the most recent N days
        trading_dates = trading_dates[-days:]
        
        print(f"Fetching SPY options snapshots for {len(trading_dates)} trading days:")
        print(f"Date range: {trading_dates[0]} to {trading_dates[-1]}")
        
        all_flattened_data = []
        
        for trade_date in trading_dates:
            print(f"\nProcessing {trade_date}...")
            snapshot_data = self.get_options_snapshots_for_date(trade_date)
            
            if snapshot_data:
                print(f"  Found {snapshot_data['total_contracts']} options contracts")
                flattened_data = self.flatten_options_data(snapshot_data)
                all_flattened_data.extend(flattened_data)
            else:
                print(f"  No data available for {trade_date}")
            
            # Rate limiting between dates
            time.sleep(1)
        
        if all_flattened_data:
            df = pd.DataFrame(all_flattened_data)
            print(f"\nTotal records collected: {len(df)}")
            return df
        else:
            print("No data collected")
            return pd.DataFrame()
    
    def create_schema_csv(self, df: pd.DataFrame, schema_filename: str = "spy_options_schema.csv"):
        """
        Create a schema CSV file describing all columns in the dataset.
        
        Args:
            df: DataFrame with options data
            schema_filename: Name of the schema file to create
        """
        schema_data = [
            ["Column", "Type", "Description"],
            ["date", "string", "Trading date in YYYY-MM-DD format"],
            ["ticker", "string", "Options contract ticker symbol (e.g., O:SPY241230C00600000)"],
            ["contract_type", "string", "Type of contract (call or put)"],
            ["exercise_style", "string", "Exercise style (american or european)"],
            ["expiration_date", "string", "Contract expiration date in YYYY-MM-DD format"],
            ["shares_per_contract", "integer", "Number of shares per contract (typically 100)"],
            ["strike_price", "float", "Strike price of the option contract"],
            ["day_change", "float", "Price change for the trading day"],
            ["day_change_percent", "float", "Percentage change for the trading day"],
            ["day_close", "float", "Closing price for the trading day"],
            ["day_high", "float", "Highest price during the trading day"],
            ["day_low", "float", "Lowest price during the trading day"],
            ["day_open", "float", "Opening price for the trading day"],
            ["day_previous_close", "float", "Previous day's closing price"],
            ["day_volume", "integer", "Trading volume for the day"],
            ["day_vwap", "float", "Volume-weighted average price for the day"],
            ["day_last_updated", "integer", "Unix timestamp (nanoseconds) of last day data update"],
            ["delta", "float", "Delta Greek - sensitivity to underlying price changes"],
            ["gamma", "float", "Gamma Greek - rate of change of delta"],
            ["theta", "float", "Theta Greek - time decay sensitivity"],
            ["vega", "float", "Vega Greek - volatility sensitivity"],
            ["implied_volatility", "float", "Implied volatility of the option"],
            ["break_even_price", "float", "Break-even price for the option position"],
            ["open_interest", "integer", "Number of outstanding contracts"],
            ["ask", "float", "Current ask price"],
            ["ask_size", "integer", "Number of contracts at ask price"],
            ["bid", "float", "Current bid price"],
            ["bid_size", "integer", "Number of contracts at bid price"],
            ["midpoint", "float", "Midpoint between bid and ask"],
            ["quote_last_updated", "integer", "Unix timestamp (nanoseconds) of last quote update"],
            ["quote_timeframe", "string", "Quote timeframe (REAL-TIME or DELAYED)"],
            ["underlying_ticker", "string", "Ticker symbol of underlying asset (SPY)"],
            ["underlying_price", "float", "Current price of underlying asset"],
            ["underlying_change_to_break_even", "float", "Points needed for underlying to reach break-even"],
            ["underlying_last_updated", "integer", "Unix timestamp (nanoseconds) of underlying price update"],
            ["underlying_timeframe", "string", "Underlying data timeframe (REAL-TIME or DELAYED)"]
        ]
        
        schema_df = pd.DataFrame(schema_data)
        schema_df.to_csv(schema_filename, index=False, header=False)
        print(f"Schema saved to {schema_filename}")
        
        return schema_df

def main():
    # Replace with your actual Polygon.io API key
    API_KEY = "Z_ENWpm0RRrvXvLOY65uMH8RB93B4gBN"
    
    # Initialize the fetcher
    fetcher = SPYOptionsSnapshotFetcher(API_KEY)
    
    # Fetch past 7 days of SPY options snapshots
    print("Starting SPY options snapshots collection for past 7 days...")
    df = fetcher.fetch_past_n_days_snapshots(days=7)
    
    if not df.empty:
        # Generate output filename with date range
        today = date.today().strftime('%Y%m%d')
        seven_days_ago = (date.today() - timedelta(days=7)).strftime('%Y%m%d')
        output_filename = f"spy_options_snapshots_{today}.csv"
        schema_filename = f"spy_options_snapshots_{today}.csv"
        
        # Save the main data
        df.to_csv(output_filename, index=False)
        print(f"\nData saved to {output_filename}")
        
        # Create and save schema
        fetcher.create_schema_csv(df, schema_filename)
        
        # Display summary statistics
        print(f"\nSummary Statistics:")
        print(f"Total options contracts: {len(df)}")
        print(f"Unique trading dates: {df['date'].nunique()}")
        print(f"Date range: {df['date'].min()} to {df['date'].max()}")
        print(f"Contract types: {df['contract_type'].value_counts().to_dict()}")
        print(f"Unique strike prices: {df['strike_price'].nunique()}")
        print(f"Strike price range: ${df['strike_price'].min():.0f} to ${df['strike_price'].max():.0f}")
        
        if 'expiration_date' in df.columns:
            print(f"Expiration dates: {sorted(df['expiration_date'].unique())}")
        
        # Show sample of the data
        print(f"\nSample of collected data (first 5 rows, first 10 columns):")
        print(df.iloc[:5, :10].to_string(index=False))
        
        print(f"\nFiles created:")
        print(f"1. {output_filename} - Main options snapshots data")
        print(f"2. {schema_filename} - Column definitions and data types")
        
    else:
        print("No data was collected. This might be due to:")
        print("- Market being closed")
        print("- API rate limits")
        print("- Invalid API key")
        print("- Network issues")

if __name__ == "__main__":
    main()