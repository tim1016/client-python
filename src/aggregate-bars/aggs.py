import requests
import pandas as pd
from datetime import datetime, timedelta
import time
from typing import Dict, List, Optional, Union
from dataclasses import dataclass

@dataclass
class IntradayConfig:
    """Configuration for intraday data collection"""
    ticker: str = "SPY"
    api_key: str = "Z_ENWpm0RRrvXvLOY65uMH8RB93B4gBN"
    start_date: str = "2025-08-25"  # YYYY-MM-DD format
    end_date: str = "2025-08-30"    # YYYY-MM-DD format
    interval_minutes: int = 5  # 5-minute intervals (can be changed to 1, 15, 30, 60, etc.)
    limit: int = 50000  # Maximum number of bars per request
    adjusted: bool = True  # Whether to adjust for splits/dividends
    sort: str = "asc"  # "asc" or "desc"
    output_filename: str = ""  # Custom output filename (optional)
    rate_limit_delay: float = 0.1  # Delay between API calls

class PolygonIntradayFetcher:
    def __init__(self, config: IntradayConfig):
        """
        Initialize the Polygon.io API client for intraday data.
        
        Args:
            config: IntradayConfig object with all parameters
        """
        self.config = config
        self.base_url = "https://api.polygon.io"
        
        # Validate required fields
        if not config.api_key:
            raise ValueError("API key is required")
        if not config.start_date or not config.end_date:
            raise ValueError("Start date and end date are required")
        if not config.ticker:
            raise ValueError("Ticker is required")
    
    def fetch_intraday_data(self) -> pd.DataFrame:
        """
        Fetch intraday data for the configured ticker and date range.
        
        Returns:
            DataFrame with intraday OHLCV data
        """
        print(f"Fetching {self.config.interval_minutes}-minute data for {self.config.ticker}")
        print(f"Date range: {self.config.start_date} to {self.config.end_date}")
        
        # Construct the API URL
        url = f"{self.base_url}/v2/aggs/ticker/{self.config.ticker}/range/{self.config.interval_minutes}/minute/{self.config.start_date}/{self.config.end_date}"
        
        params = {
            'adjusted': str(self.config.adjusted).lower(),
            'sort': self.config.sort,
            'limit': self.config.limit,
            'apikey': self.config.api_key
        }
        
        all_results = []
        next_url = None
        request_count = 0
        
        try:
            while True:
                request_count += 1
                print(f"Making API request #{request_count}...")
                
                # Use next_url if available (for pagination), otherwise use the original URL
                request_url = next_url if next_url else url
                
                response = requests.get(request_url if next_url else url, 
                                      params=None if next_url else params)
                response.raise_for_status()
                data = response.json()
                
                # Check for results
                if 'results' not in data or not data['results']:
                    print(f"No more data available")
                    break
                
                # Add results to our collection
                results = data['results']
                all_results.extend(results)
                print(f"Retrieved {len(results)} bars (Total: {len(all_results)})")
                
                # Check if there are more pages
                if 'next_url' in data and data['next_url']:
                    next_url = data['next_url'] + f"&apikey={self.config.api_key}"
                    time.sleep(self.config.rate_limit_delay)  # Rate limiting
                else:
                    break
            
            if not all_results:
                print("No data found for the specified parameters")
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = self._process_raw_data(all_results)
            
            print(f"\nData collection complete!")
            print(f"Total bars retrieved: {len(df)}")
            print(f"Date range in data: {df['datetime'].min()} to {df['datetime'].max()}")
            
            return df
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data: {e}")
            return pd.DataFrame()
    
    def _process_raw_data(self, raw_results: List[Dict]) -> pd.DataFrame:
        """
        Process raw API results into a clean DataFrame.
        
        Args:
            raw_results: List of raw result dictionaries from API
            
        Returns:
            Processed DataFrame with proper column names and datetime index
        """
        # Convert to DataFrame
        df = pd.DataFrame(raw_results)
        
        # Rename columns to standard OHLCV format
        df = df.rename(columns={
            'o': 'open',
            'h': 'high',
            'l': 'low',
            'c': 'close',
            'v': 'volume',
            'vw': 'vwap',  # Volume Weighted Average Price
            't': 'timestamp'
        })
        
        # Convert timestamp to datetime
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Add additional useful columns
        df['date'] = df['datetime'].dt.date
        df['time'] = df['datetime'].dt.time
        df['hour'] = df['datetime'].dt.hour
        df['minute'] = df['datetime'].dt.minute
        df['day_of_week'] = df['datetime'].dt.day_name()
        
        # Add ticker column
        df['ticker'] = self.config.ticker
        
        # Reorder columns for better readability
        columns_order = [
            'ticker', 'datetime', 'date', 'time', 'hour', 'minute', 'day_of_week',
            'open', 'high', 'low', 'close', 'volume', 'vwap', 'timestamp'
        ]
        
        # Only include columns that exist in the DataFrame
        available_columns = [col for col in columns_order if col in df.columns]
        df = df[available_columns]
        
        # Sort by datetime
        df = df.sort_values('datetime').reset_index(drop=True)
        
        return df
    
    def save_data(self, df: pd.DataFrame) -> List[str]:
        """
        Save the DataFrame to multiple CSV files - one for each variable.
        Creates pivoted tables where rows are days and columns are time intervals.
        
        Args:
            df: DataFrame to save
            
        Returns:
            List of filenames of the saved files
        """
        if df.empty:
            print("No data to save")
            return []
        
        print(f"\nCreating pivoted data tables...")
        
        # Variables to create separate files for
        variables = ['open', 'high', 'low', 'close', 'volume', 'vwap']
        
        # Filter to only variables that exist in the DataFrame
        available_variables = [var for var in variables if var in df.columns]
        
        saved_files = []
        
        for variable in available_variables:
            print(f"Processing {variable}...")
            
            # Create pivot table: rows = dates, columns = times
            pivot_df = self._create_pivot_table(df, variable)
            
            if not pivot_df.empty:
                # Generate filename
                if self.config.output_filename:
                    base_name = self.config.output_filename.replace('.csv', '')
                    filename = f"{base_name}_{variable}.csv"
                else:
                    filename = f"{self.config.ticker}_{self.config.interval_minutes}min_{variable}_{self.config.start_date}_to_{self.config.end_date}.csv"
                
                # Save to CSV
                pivot_df.to_csv(filename)  # Keep index (dates) as first column
                saved_files.append(filename)
                print(f"  Saved {variable} data to: {filename}")
                print(f"  Dimensions: {pivot_df.shape[0]} days x {pivot_df.shape[1]} time intervals")
        
        print(f"\nTotal files created: {len(saved_files)}")
        return saved_files
    
    def _create_pivot_table(self, df: pd.DataFrame, variable: str) -> pd.DataFrame:
        """
        Create a pivot table for a specific variable.
        Rows = dates, Columns = time intervals, Values = variable values
        
        Args:
            df: Source DataFrame
            variable: Variable name to pivot (e.g., 'close', 'volume')
            
        Returns:
            Pivoted DataFrame
        """
        # Create time string for column headers (HH:MM format)
        df_copy = df.copy()
        df_copy['time_str'] = df_copy['datetime'].dt.strftime('%H:%M')
        
        # Create pivot table
        pivot_df = df_copy.pivot_table(
            index='date',           # Rows: dates
            columns='time_str',     # Columns: time intervals  
            values=variable,        # Values: the variable we're interested in
            aggfunc='first'         # In case of duplicates, take first value
        )
        
        # Sort columns chronologically
        pivot_df = pivot_df.reindex(sorted(pivot_df.columns), axis=1)
        
        # Fill NaN values with empty string or 0 depending on variable
        if variable in ['volume']:
            pivot_df = pivot_df.fillna(0)
        else:
            pivot_df = pivot_df.fillna('')
        
        return pivot_df
    
    def preview_pivot_structure(self, df: pd.DataFrame):
        """
        Show a preview of how the pivoted data will look.
        
        Args:
            df: DataFrame to preview
        """
        if df.empty:
            print("No data to preview")
            return
        
        print("\n" + "="*50)
        print("PIVOT TABLE STRUCTURE PREVIEW")
        print("="*50)
        
        # Get unique dates and times
        unique_dates = sorted(df['date'].unique())
        unique_times = sorted(df['datetime'].dt.strftime('%H:%M').unique())
        
        print(f"Number of trading days: {len(unique_dates)}")
        print(f"First day: {unique_dates[0]}")
        print(f"Last day: {unique_dates[-1]}")
        
        print(f"\nNumber of time intervals per day: {len(unique_times)}")
        print(f"First time interval: {unique_times[0]}")
        print(f"Last time interval: {unique_times[-1]}")
        
        print(f"\nTime intervals (first 10):")
        for i, time_str in enumerate(unique_times[:10]):
            print(f"  Column {i+2}: {time_str}")  # +2 because date is column 1
        
        if len(unique_times) > 10:
            print(f"  ... and {len(unique_times) - 10} more time intervals")
        
        # Show sample of what close price table would look like
        print(f"\nSample of 'close' price table structure:")
        sample_pivot = self._create_pivot_table(df.head(50), 'close')  # Small sample
        print(f"Rows (dates): {list(sample_pivot.index)}")
        print(f"Columns (times): {list(sample_pivot.columns[:5])}...")  # First 5 columns
        
        print("="*50)
    
    def get_data_summary(self, df: pd.DataFrame):
        """
        Print summary statistics of the collected data.
        
        Args:
            df: DataFrame to summarize
        """
        if df.empty:
            print("No data to summarize")
            return
        
        print("\n" + "="*50)
        print("DATA SUMMARY")
        print("="*50)
        
        print(f"Ticker: {self.config.ticker}")
        print(f"Interval: {self.config.interval_minutes} minutes")
        print(f"Total bars: {len(df):,}")
        print(f"Date range: {df['date'].min()} to {df['date'].max()}")
        print(f"Time range: {df['time'].min()} to {df['time'].max()}")
        print(f"Trading days: {df['date'].nunique()}")
        
        # Price statistics
        print(f"\nPrice Statistics:")
        print(f"Highest price: ${df['high'].max():.2f}")
        print(f"Lowest price: ${df['low'].min():.2f}")
        print(f"Average close: ${df['close'].mean():.2f}")
        print(f"Average volume: {df['volume'].mean():,.0f}")
        
        # Trading hours analysis
        print(f"\nTrading Hours Distribution:")
        hourly_counts = df.groupby('hour').size().sort_index()
        for hour, count in hourly_counts.items():
            time_str = f"{hour:02d}:00-{hour:02d}:59"
            print(f"  {time_str}: {count:,} bars")
        
        # Weekly distribution
        print(f"\nWeekly Distribution:")
        daily_counts = df.groupby('day_of_week').size()
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        for day in day_order:
            if day in daily_counts:
                print(f"  {day}: {daily_counts[day]:,} bars")
        
        print("="*50)

# Convenience functions for common use cases

def fetch_5min_data(ticker: str, api_key: str, start_date: str, end_date: str, 
                   **kwargs) -> pd.DataFrame:
    """
    Simple function to fetch 5-minute data.
    
    Args:
        ticker: Stock ticker symbol
        api_key: Polygon.io API key
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        **kwargs: Additional configuration options
        
    Returns:
        DataFrame with 5-minute OHLCV data
    """
    config = IntradayConfig(
        ticker=ticker.upper(),
        api_key=api_key,
        start_date=start_date,
        end_date=end_date,
        interval_minutes=5,
        **kwargs
    )
    
    fetcher = PolygonIntradayFetcher(config)
    return fetcher.fetch_intraday_data()

def fetch_custom_interval_data(ticker: str, api_key: str, start_date: str, end_date: str,
                              interval_minutes: int, **kwargs) -> pd.DataFrame:
    """
    Fetch data with custom interval.
    
    Args:
        ticker: Stock ticker symbol
        api_key: Polygon.io API key
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        interval_minutes: Interval in minutes (1, 5, 15, 30, 60, etc.)
        **kwargs: Additional configuration options
        
    Returns:
        DataFrame with intraday OHLCV data
    """
    config = IntradayConfig(
        ticker=ticker.upper(),
        api_key=api_key,
        start_date=start_date,
        end_date=end_date,
        interval_minutes=interval_minutes,
        **kwargs
    )
    
    fetcher = PolygonIntradayFetcher(config)
    return fetcher.fetch_intraday_data()

def main():
    """Example usage with different configurations."""
    
    # Your API key
    API_KEY = "Z_ENWpm0RRrvXvLOY65uMH8RB93B4gBN"
    

    print("\n=== Example 2: SPY 15-Minute Data ===")
    config2 = IntradayConfig(
        ticker="SPY",
        api_key=API_KEY,
        start_date="2024-09-01",
        end_date="2025-08-30",
        interval_minutes=5,
        output_filename="spy_15min_data"
    )
    
    fetcher2 = PolygonIntradayFetcher(config2)
    df2 = fetcher2.fetch_intraday_data()
    
    if not df2.empty:
        saved_files = fetcher2.save_data(df2)
        fetcher2.get_data_summary(df2)
    
    # Example 3: TSLA with 1-minute intervals (higher resolution)
    # print("\n=== Example 3: TSLA 1-Minute Data ===")
    # df3 = fetch_custom_interval_data(
    #     ticker="TSLA",
    #     api_key=API_KEY,
    #     start_date="2024-08-30",
    #     end_date="2024-08-30",  # Single day for 1-minute data
    #     interval_minutes=1,
    #     limit=50000
    # )
    
    # if not df3.empty:
    #     config3 = IntradayConfig(
    #         ticker="TSLA",
    #         api_key=API_KEY,
    #         start_date="2024-08-30",
    #         end_date="2024-08-30",
    #         interval_minutes=1
    #     )
    #     fetcher3 = PolygonIntradayFetcher(config3)
    #     saved_files = fetcher3.save_data(df3)
    #     fetcher3.get_data_summary(df3)

if __name__ == "__main__":
    main()

# Quick usage examples:

"""
# Simple 5-minute data - creates 6 separate CSV files (open, high, low, close, volume, vwap)
config = IntradayConfig(
    ticker="AAPL",
    api_key="your_api_key",
    start_date="2024-08-01",
    end_date="2024-08-31",
    interval_minutes=5
)
fetcher = PolygonIntradayFetcher(config)
df = fetcher.fetch_intraday_data()
saved_files = fetcher.save_data(df)  # Returns list of created files

# This will create files like:
# AAPL_5min_open_2024-08-01_to_2024-08-31.csv
# AAPL_5min_high_2024-08-01_to_2024-08-31.csv
# AAPL_5min_low_2024-08-01_to_2024-08-31.csv
# AAPL_5min_close_2024-08-01_to_2024-08-31.csv
# AAPL_5min_volume_2024-08-01_to_2024-08-31.csv  
# AAPL_5min_vwap_2024-08-01_to_2024-08-31.csv

# Each CSV structure:
# Row 1: Date column header, then time intervals (09:30, 09:35, 09:40, ...)
# Row 2+: Each trading day with values for each time interval

# Example CSV content for 'close' prices:
# date,09:30,09:35,09:40,09:45,10:00,...,15:55
# 2024-08-01,150.25,150.30,150.45,150.60,...,151.20
# 2024-08-02,151.00,151.15,151.25,151.40,...,152.10
# ...
"""