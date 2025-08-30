import requests
import pandas as pd
from datetime import date, datetime, timedelta
import time
from typing import Dict, List, Optional, Tuple

class PolygonSPYOptionsData:
    def __init__(self, api_key: str):
        """
        Initialize the Polygon.io API client for SPY options data.
        
        Args:
            api_key: Your Polygon.io API key
        """
        self.api_key = api_key
        self.base_url = "https://api.polygon.io"
        
    def get_spy_stock_data(self, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Get SPY stock OHLC data for the specified date range.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            DataFrame with SPY stock data
        """
        url = f"{self.base_url}/v2/aggs/ticker/SPY/range/1/day/{start_date}/{end_date}"
        params = {
            'adjusted': 'true',
            'sort': 'asc',
            'apikey': self.api_key
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if 'results' not in data:
                print(f"No stock data found for the date range")
                return pd.DataFrame()
                
            # Convert to DataFrame
            df = pd.DataFrame(data['results'])
            df['date'] = pd.to_datetime(df['t'], unit='ms').dt.date
            df = df.rename(columns={
                'o': 'open',
                'h': 'high', 
                'l': 'low',
                'c': 'close',
                'v': 'volume'
            })

            # Add previous day's close column
            df['spy_close_prev_day'] = df['close'].shift(1)

            # Calculate multiple strike prices based on previous day's close
            df['atm_strike'] = df['close'].shift(1).round(0)
            df['strike_plus_1'] = df['atm_strike'] + 1
            df['strike_plus_2'] = df['atm_strike'] + 2
            df['strike_plus_3'] = df['atm_strike'] + 3
            df['strike_minus_1'] = df['atm_strike'] - 1
            df['strike_minus_2'] = df['atm_strike'] - 2

            # Drop the first row since it has no previous close for ATM strike
            df = df.dropna(subset=['atm_strike'])

            # Now convert to int after dropping NaN values
            strike_columns = ['atm_strike', 'strike_plus_1', 'strike_plus_2', 'strike_plus_3', 'strike_minus_1', 'strike_minus_2']
            for col in strike_columns:
                df[col] = df[col].astype(int)

            # Return columns with spy_close_prev_day next to spy_close
            return df[['date', 'open', 'high', 'low', 'close', 'spy_close_prev_day', 'volume'] + strike_columns]
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching stock data: {e}")
            return pd.DataFrame()
    
    def get_options_data_multiple_strikes(self, strikes_dict: Dict[str, int], expiration_date: str, trade_date: str) -> Dict:
        """
        Get call and put options data for multiple strikes and expiration.
        
        Args:
            strikes_dict: Dictionary with strike labels and values (e.g., {'atm': 450, 'plus_1': 451})
            expiration_date: Expiration date in YYYY-MM-DD format
            trade_date: Trading date in YYYY-MM-DD format
            
        Returns:
            Dictionary containing call and put options data for all strikes
        """
        results = {}
        
        for strike_label, strike_price in strikes_dict.items():
            print(f"  Fetching {strike_label} strike: {strike_price}")
            
            # Format strike price for options ticker (multiply by 1000)
            formatted_strike = str(strike_price * 1000).zfill(8)
            
            # Format expiration date (YYMMDD)
            exp_date_obj = datetime.strptime(expiration_date, '%Y-%m-%d')
            formatted_exp = exp_date_obj.strftime('%y%m%d')
            
            # Construct options tickers
            call_ticker = f"O:SPY{formatted_exp}C{formatted_strike}"
            put_ticker = f"O:SPY{formatted_exp}P{formatted_strike}"
            
            # Get call option data
            call_data = self._fetch_single_option(call_ticker, trade_date)
            time.sleep(0.1)  # Rate limiting
            
            # Get put option data  
            put_data = self._fetch_single_option(put_ticker, trade_date)
            time.sleep(0.1)  # Rate limiting
            
            results[strike_label] = {
                'call_data': call_data,
                'put_data': put_data,
                'call_ticker': call_ticker,
                'put_ticker': put_ticker,
                'strike_price': strike_price
            }
        
        return results
    
    def _fetch_single_option(self, ticker: str, trade_date: str) -> Optional[Dict]:
        """
        Fetch data for a single option ticker.
        
        Args:
            ticker: Options ticker symbol
            trade_date: Trading date in YYYY-MM-DD format
            
        Returns:
            Dictionary with option data or None if not found
        """
        url = f"{self.base_url}/v2/aggs/ticker/{ticker}/range/1/day/{trade_date}/{trade_date}"
        params = {
            'adjusted': 'true',
            'apikey': self.api_key
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if 'results' in data and len(data['results']) > 0:
                result = data['results'][0]
                return {
                    'ticker': ticker,
                    'date': trade_date,
                    'open': result.get('o'),
                    'high': result.get('h'),
                    'low': result.get('l'),
                    'close': result.get('c'),
                    'volume': result.get('v'),
                    'volume_weighted_avg_price': result.get('vw')
                }
            else:
                print(f"    No data found for {ticker} on {trade_date}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"    Error fetching {ticker}: {e}")
            return None
    
    def process_spy_options_data(self, start_date: str, end_date: str, 
                               same_day_expiry: bool = True) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Main function to process SPY stock data and fetch corresponding options for multiple strikes.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format  
            same_day_expiry: If True, look for options that expire on the same day
            
        Returns:
            Tuple of (ordered_df, default_df) - ordered DataFrame and default grouping DataFrame
        """
        # Get SPY stock data
        print("Fetching SPY stock data...")
        stock_data = self.get_spy_stock_data(start_date, end_date)
        
        if stock_data.empty:
            print("No stock data available")
            return pd.DataFrame()
        
        print(f"Found {len(stock_data)} days of stock data")
        
        # Process each day
        all_data = []
        
        for idx, row in stock_data.iterrows():
            trade_date = row['date'].strftime('%Y-%m-%d')
            
            # For same day expiry, expiration date = trade date
            if same_day_expiry:
                expiration_date = trade_date
            else:
                # You can modify this logic for different expiration strategies
                expiration_date = trade_date
            
            # Prepare strikes dictionary
            strikes_dict = {
                'atm': row['atm_strike'],
                'plus_1': row['strike_plus_1'],
                'plus_2': row['strike_plus_2'], 
                'plus_3': row['strike_plus_3'],
                'minus_1': row['strike_minus_1'],
                'minus_2': row['strike_minus_2']
            }
            
            print(f"Processing {trade_date}, Strikes: {strikes_dict}, Expiry: {expiration_date}")
            
            # Get options data for all strikes
            options_data = self.get_options_data_multiple_strikes(strikes_dict, expiration_date, trade_date)
            
            # Start with base stock data
            combined_row = {
                'date': trade_date,
                'spy_open': row['open'],
                'spy_high': row['high'],
                'spy_low': row['low'],
                'spy_close': row['close'],
                'spy_close_prev_day': row['spy_close_prev_day'],  # Add this line
                'spy_volume': row['volume'],
                'expiration_date': expiration_date
            }
            
            # Add data for each strike
            for strike_label, strike_data in options_data.items():
                strike_price = strike_data['strike_price']
                
                # Add strike price
                combined_row[f'{strike_label}_strike'] = strike_price
                
                # Add call data
                if strike_data['call_data']:
                    call_data = strike_data['call_data']
                    combined_row.update({
                        f'{strike_label}_call_ticker': strike_data['call_ticker'],
                        f'{strike_label}_call_open': call_data['open'],
                        f'{strike_label}_call_high': call_data['high'],
                        f'{strike_label}_call_low': call_data['low'],
                        f'{strike_label}_call_close': call_data['close'],
                        f'{strike_label}_call_volume': call_data['volume'],
                        f'{strike_label}_call_vwap': call_data.get('volume_weighted_avg_price')
                    })
                
                # Add put data
                if strike_data['put_data']:
                    put_data = strike_data['put_data']
                    combined_row.update({
                        f'{strike_label}_put_ticker': strike_data['put_ticker'],
                        f'{strike_label}_put_open': put_data['open'],
                        f'{strike_label}_put_high': put_data['high'],
                        f'{strike_label}_put_low': put_data['low'],
                        f'{strike_label}_put_close': put_data['close'],
                        f'{strike_label}_put_volume': put_data['volume'],
                        f'{strike_label}_put_vwap': put_data.get('volume_weighted_avg_price')
                    })
            
            all_data.append(combined_row)
            
            # Small delay to respect rate limits
            time.sleep(0.5)  # Increased delay due to more API calls
        
        # Create both DataFrames
        default_df = pd.DataFrame(all_data)  # Original column order
        ordered_df = pd.DataFrame(all_data)  # Will be reordered
        
        # Reorder columns for the ordered DataFrame
        if not ordered_df.empty:
            ordered_df = self._reorder_columns(ordered_df)
        
        return ordered_df, default_df
    
    def _reorder_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Reorder columns to group by option type (calls/puts) and then by strike price order."""
        # Base columns (stock data and metadata)
        base_columns = ['date', 'spy_open', 'spy_high', 'spy_low', 'spy_close', 
                       'spy_close_prev_day', 'spy_volume', 'expiration_date']
        
        # Strike labels in order
        strike_order = ['minus_2', 'minus_1', 'atm', 'plus_1', 'plus_2', 'plus_3']
        
        # Option data types in desired order
        option_data_types = ['open', 'high', 'low', 'close', 'volume', 'vwap']
        
        # Start with base columns
        ordered_columns = base_columns.copy()
        
        # Add strike prices first
        for strike in strike_order:
            strike_col = f'{strike}_strike'
            if strike_col in df.columns:
                ordered_columns.append(strike_col)
        
        # Add call tickers
        for strike in strike_order:
            ticker_col = f'{strike}_call_ticker'
            if ticker_col in df.columns:
                ordered_columns.append(ticker_col)
        
        # Add call data (grouped by data type, then by strike)
        for data_type in option_data_types:
            for strike in strike_order:
                col_name = f'{strike}_call_{data_type}'
                if col_name in df.columns:
                    ordered_columns.append(col_name)
        
        # Add put tickers
        for strike in strike_order:
            ticker_col = f'{strike}_put_ticker'
            if ticker_col in df.columns:
                ordered_columns.append(ticker_col)
        
        # Add put data (grouped by data type, then by strike)
        for data_type in option_data_types:
            for strike in strike_order:
                col_name = f'{strike}_put_{data_type}'
                if col_name in df.columns:
                    ordered_columns.append(col_name)
        
        # Add any remaining columns that weren't explicitly ordered
        remaining_columns = [col for col in df.columns if col not in ordered_columns]
        ordered_columns.extend(remaining_columns)
        
        return df[ordered_columns]

def write_schema_files():
    """Write schema files for results and default DataFrames"""
    
    # Schema for results DataFrame
    results_schema = [
        ["Column", "Type", "Description"],
        ["date", "date", "Trading date in YYYY-MM-DD format"],
        ["spy_open", "float", "Opening price of SPY for the day"],
        ["spy_high", "float", "Highest price of SPY during the day"],
        ["spy_low", "float", "Lowest price of SPY during the day"],
        ["spy_close", "float", "Closing price of SPY for the day"],
        ["spy_close_prev_day", "float", "Previous day's closing price of SPY"],
        ["spy_volume", "integer", "Trading volume for the day"],
        ["expiration_date", "date", "Option expiration date"],
        ["atm_strike", "integer", "At-the-money strike price based on previous day's close"],
        ["strike_plus_1", "integer", "Strike price 1 point above ATM"],
        ["strike_plus_2", "integer", "Strike price 2 points above ATM"],
        ["strike_plus_3", "integer", "Strike price 3 points above ATM"],
        ["strike_minus_1", "integer", "Strike price 1 point below ATM"],
        ["strike_minus_2", "integer", "Strike price 2 points below ATM"]
    ]

    # Schema for default DataFrame - Update with all columns
    default_schema = [
        ["Column", "Type", "Description"],
        ["date", "date", "Trading date in YYYY-MM-DD format"],
        ["spy_open", "float", "Opening price of SPY for the day"],
        ["spy_high", "float", "Highest price of SPY during the day"],
        ["spy_low", "float", "Lowest price of SPY during the day"],
        ["spy_close", "float", "Closing price of SPY for the day"],
        ["spy_close_prev_day", "float", "Previous day's closing price of SPY"],
        ["spy_volume", "integer", "Trading volume for the day"],
        ["expiration_date", "date", "Option expiration date"],
        ["call_volume", "integer", "Total trading volume for call options"],
        ["put_volume", "integer", "Total trading volume for put options"],
        ["call_vwap", "float", "Volume-weighted average price for calls"],
        ["put_vwap", "float", "Volume-weighted average price for puts"],
        ["call_open", "float", "Opening price for call options"],
        ["put_open", "float", "Opening price for put options"],
        ["call_close", "float", "Closing price for call options"],
        ["put_close", "float", "Closing price for put options"]
    ]

    # Write schemas to CSV
    pd.DataFrame(results_schema).to_csv('results_schema.csv', index=False, header=False)
    pd.DataFrame(default_schema).to_csv('default_schema.csv', index=False, header=False)

# Example usage
def main():
    # Replace with your actual Polygon.io API key
    API_KEY = "Z_ENWpm0RRrvXvLOY65uMH8RB93B4gBN"
    
    # Initialize the data fetcher
    fetcher = PolygonSPYOptionsData(API_KEY)
    
    # Define date range for 2024
    start_date = "2024-12-28"
    end_date = "2025-08-28"

    # end_date = date.today().strftime('%Y-%m-%d')
    
    # Process the data
    print("Starting SPY options data collection...")
    results_df, default_df = fetcher.process_spy_options_data(
        start_date=start_date,
        end_date=end_date,
        same_day_expiry=True  # Look for same-day expiring options
    )
    
    # Display results
    if not results_df.empty:
        print(f"\nCollected data for {len(results_df)} trading days")
        print("\nColumn organization:")
        print("Base columns: date, spy_open, spy_high, spy_low, spy_close, spy_volume, expiration_date")
        print("Strike prices: minus_2_strike -> plus_3_strike")
        print("Call tickers: minus_2_call_ticker -> plus_3_call_ticker")
        print("Call data: grouped by type (open, high, low, close, volume, vwap), then by strike (minus_2 -> plus_3)")
        print("Put tickers: minus_2_put_ticker -> plus_3_put_ticker")
        print("Put data: grouped by type (open, high, low, close, volume, vwap), then by strike (minus_2 -> plus_3)")
        print(f"\nTotal columns: {len(results_df.columns)}")
        
        print("\nSample of call high columns:")
        call_high_cols = [col for col in results_df.columns if 'call_high' in col]
        print(call_high_cols)
        
        print("\nFirst few rows (showing first 15 columns):")
        print(results_df.iloc[:, :15].head())
        
        # Save ordered CSV (strike price organized)
        ordered_output_file = f"spy_options_multiple_strikes_{start_date}_to_{end_date}.csv"
        results_df.to_csv(ordered_output_file, index=False)
        print(f"\nOrdered data saved to {ordered_output_file}")
        
        # Create and save default grouping CSV (grouped by tickers, no strike ordering)
        default_output_file = f"spy_options_default_grouping_{start_date}_to_{end_date}.csv"
        default_df.to_csv(default_output_file, index=False)
        print(f"Default grouping data saved to {default_output_file}")
        
        # Summary statistics
        print("\nSummary:")
        strike_labels = ['atm', 'plus_1', 'plus_2', 'plus_3', 'minus_1', 'minus_2']
        for label in strike_labels:
            call_col = f'{label}_call_close'
            put_col = f'{label}_put_close'
            if call_col in results_df.columns:
                print(f"Days with {label} call data: {results_df[call_col].notna().sum()}")
            if put_col in results_df.columns:
                print(f"Days with {label} put data: {results_df[put_col].notna().sum()}")
        
        print(f"\nTwo CSV files created:")
        print(f"1. {ordered_output_file} - Strike price ordered (calls grouped by type, puts grouped by type)")
        print(f"2. {default_output_file} - Default ticker grouping (as data was collected)")
    else:
        print("No data collected")

if __name__ == "__main__":
    main()