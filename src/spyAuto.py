import requests
import pandas as pd
from datetime import datetime, timedelta
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
            
            # Calculate ATM strike (previous day's close price rounded to nearest dollar)
            df['atm_strike'] = df['close'].shift(1).round(0)
            
            # Drop the first row since it has no previous close for ATM strike
            df = df.dropna(subset=['atm_strike'])
            
            # Now convert to int after dropping NaN values
            df['atm_strike'] = df['atm_strike'].astype(int)
            
            return df[['date', 'open', 'high', 'low', 'close', 'volume', 'atm_strike']]
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching stock data: {e}")
            return pd.DataFrame()
    
    def get_options_data(self, strike_price: int, expiration_date: str, trade_date: str) -> Dict:
        """
        Get call and put options data for a specific strike and expiration.
        
        Args:
            strike_price: Strike price (integer)
            expiration_date: Expiration date in YYYY-MM-DD format
            trade_date: Trading date in YYYY-MM-DD format
            
        Returns:
            Dictionary containing call and put options data
        """
        # Format strike price for options ticker (multiply by 1000)
        formatted_strike = str(strike_price * 1000).zfill(8)
        
        # Format expiration date (YYMMDD)
        exp_date_obj = datetime.strptime(expiration_date, '%Y-%m-%d')
        formatted_exp = exp_date_obj.strftime('%y%m%d')
        
        # Construct options tickers
        call_ticker = f"O:SPY{formatted_exp}C{formatted_strike}"
        put_ticker = f"O:SPY{formatted_exp}P{formatted_strike}"
        
        results = {
            'call_data': None,
            'put_data': None,
            'call_ticker': call_ticker,
            'put_ticker': put_ticker
        }
        
        # Get call option data
        results['call_data'] = self._fetch_single_option(call_ticker, trade_date)
        time.sleep(0.1)  # Rate limiting
        
        # Get put option data  
        results['put_data'] = self._fetch_single_option(put_ticker, trade_date)
        time.sleep(0.1)  # Rate limiting
        
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
                print(f"No data found for {ticker} on {trade_date}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {ticker}: {e}")
            return None
    
    def process_spy_options_data(self, start_date: str, end_date: str, 
                               same_day_expiry: bool = True) -> pd.DataFrame:
        """
        Main function to process SPY stock data and fetch corresponding options.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format  
            same_day_expiry: If True, look for options that expire on the same day
            
        Returns:
            DataFrame with combined stock and options data
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
            strike_price = row['atm_strike']
            
            # For same day expiry, expiration date = trade date
            if same_day_expiry:
                expiration_date = trade_date
            else:
                # You can modify this logic for different expiration strategies
                # For example, next Friday, monthly expiry, etc.
                expiration_date = trade_date
            
            print(f"Processing {trade_date}, Strike: {strike_price}, Expiry: {expiration_date}")
            
            # Get options data
            options_data = self.get_options_data(strike_price, expiration_date, trade_date)
            
            # Combine data
            combined_row = {
                'date': trade_date,
                'spy_open': row['open'],
                'spy_high': row['high'],
                'spy_low': row['low'],
                'spy_close': row['close'],
                'spy_volume': row['volume'],
                'atm_strike': strike_price,
                'expiration_date': expiration_date
            }
            
            # Add call data
            if options_data['call_data']:
                call_data = options_data['call_data']
                combined_row.update({
                    'call_ticker': options_data['call_ticker'],
                    'call_open': call_data['open'],
                    'call_high': call_data['high'],
                    'call_low': call_data['low'],
                    'call_close': call_data['close'],
                    'call_volume': call_data['volume'],
                    'call_vwap': call_data.get('volume_weighted_avg_price')
                })
            
            # Add put data
            if options_data['put_data']:
                put_data = options_data['put_data']
                combined_row.update({
                    'put_ticker': options_data['put_ticker'],
                    'put_open': put_data['open'],
                    'put_high': put_data['high'],
                    'put_low': put_data['low'],
                    'put_close': put_data['close'],
                    'put_volume': put_data['volume'],
                    'put_vwap': put_data.get('volume_weighted_avg_price')
                })
            
            all_data.append(combined_row)
            
            # Small delay to respect rate limits
            time.sleep(0.2)
        
        return pd.DataFrame(all_data)

# Example usage
def main():
    # Replace with your actual Polygon.io API key
    API_KEY = "Z_ENWpm0RRrvXvLOY65uMH8RB93B4gBN"
    
    # Initialize the data fetcher
    fetcher = PolygonSPYOptionsData(API_KEY)
    
    # Define date range for 2024
    start_date = "2024-01-01"
    end_date = "2024-01-31"
    
    # Process the data
    print("Starting SPY options data collection...")
    results_df = fetcher.process_spy_options_data(
        start_date=start_date,
        end_date=end_date,
        same_day_expiry=True  # Look for same-day expiring options
    )
    
    # Display results
    if not results_df.empty:
        print(f"\nCollected data for {len(results_df)} trading days")
        print("\nFirst few rows:")
        print(results_df.head())
        
        # Save to CSV
        output_file = f"spy_options_data_{start_date}_to_{end_date}.csv"
        results_df.to_csv(output_file, index=False)
        print(f"\nData saved to {output_file}")
        
        # Summary statistics
        print("\nSummary:")
        print(f"Days with call data: {results_df['call_close'].notna().sum()}")
        print(f"Days with put data: {results_df['put_close'].notna().sum()}")
    else:
        print("No data collected")

if __name__ == "__main__":
    main()