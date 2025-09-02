import requests
import pandas as pd
from datetime import date, datetime, timedelta
import time
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass

@dataclass
class OptionsConfig:
    """Configuration for options data collection"""
    ticker: str = "SPY"
    api_key: str = "Z_ENWpm0RRrvXvLOY65uMH8RB93B4gBN"
    start_date: str = "2023-09-01"
    end_date: str = "2025-08-30"
    same_day_expiry: bool = True
    strike_strategy: str = "symmetric"  # "symmetric", "calls_only", "puts_only", "custom"
    strike_spacing: int = 1  # Distance between strikes
    num_strikes_above: int = 3  # Number of strikes above ATM
    num_strikes_below: int = 2  # Number of strikes below ATM
    custom_strike_offsets: Optional[List[int]] = None  # e.g., [-5, -2, -1, 0, 1, 2, 5]
    rate_limit_delay: float = 0.1  # Delay between API calls
    output_prefix: str = ""  # Prefix for output files

class PolygonOptionsDataFetcher:
    def __init__(self, config: OptionsConfig):
        """
        Initialize the Polygon.io API client with configuration.
        
        Args:
            config: OptionsConfig object with all parameters
        """
        self.config = config
        self.base_url = "https://api.polygon.io"
        
        # Validate required fields
        if not config.api_key:
            raise ValueError("API key is required")
        if not config.start_date or not config.end_date:
            raise ValueError("Start date and end date are required")
    
    def get_stock_data(self) -> pd.DataFrame:
        """
        Get stock OHLC data for the configured ticker and date range.
        
        Returns:
            DataFrame with stock data and calculated strike prices
        """
        url = f"{self.base_url}/v2/aggs/ticker/{self.config.ticker}/range/1/day/{self.config.start_date}/{self.config.end_date}"
        params = {
            'adjusted': 'true',
            'sort': 'asc',
            'apikey': self.config.api_key
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if 'results' not in data:
                print(f"No stock data found for {self.config.ticker}")
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

            # Add previous day's close
            df['prev_close'] = df['close'].shift(1)

            # Calculate strike prices based on strategy
            df = self._calculate_strikes(df)

            # Drop rows without previous close data
            df = df.dropna(subset=['prev_close'])

            return df[['date', 'open', 'high', 'low', 'close', 'prev_close', 'volume'] + 
                     [col for col in df.columns if 'strike' in col]]
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching stock data: {e}")
            return pd.DataFrame()
    
    def _calculate_strikes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate strike prices based on the configured strategy."""
        # Create a copy to avoid SettingWithCopyWarning
        df = df.copy()
        
        atm_base = df['close'].shift(1).round(0)
        
        if self.config.strike_strategy == "custom" and self.config.custom_strike_offsets:
            # Use custom strike offsets
            for i, offset in enumerate(self.config.custom_strike_offsets):
                if offset == 0:
                    df[f'strike_atm'] = atm_base
                elif offset > 0:
                    df[f'strike_plus_{offset}'] = atm_base + (offset * self.config.strike_spacing)
                else:
                    df[f'strike_minus_{abs(offset)}'] = atm_base + (offset * self.config.strike_spacing)
        else:
            # Standard strategies
            df['atm_strike'] = atm_base
            
            # Add strikes above ATM
            if self.config.strike_strategy in ["symmetric", "calls_only"]:
                for i in range(1, self.config.num_strikes_above + 1):
                    df[f'strike_plus_{i}'] = atm_base + (i * self.config.strike_spacing)
            
            # Add strikes below ATM
            if self.config.strike_strategy in ["symmetric", "puts_only"]:
                for i in range(1, self.config.num_strikes_below + 1):
                    df[f'strike_minus_{i}'] = atm_base - (i * self.config.strike_spacing)
        
        # First drop rows with NaN in the ATM strike (no previous close available)
        primary_strike_col = 'atm_strike' if 'atm_strike' in df.columns else [col for col in df.columns if 'strike' in col][0]
        df = df.dropna(subset=[primary_strike_col])
        
        # Now convert all strike columns to int (no more NaN values)
        strike_columns = [col for col in df.columns if 'strike' in col]
        for col in strike_columns:
            # Additional safety check - use .loc to avoid warnings
            if df[col].isna().any():
                print(f"Warning: Found NaN values in {col}, filling with ATM strike")
                df.loc[:, col] = df[col].fillna(df[primary_strike_col])
            df.loc[:, col] = df[col].astype(int)
        
        return df
    
    def get_options_data_for_strikes(self, strikes_dict: Dict[str, int], 
                                   expiration_date: str, trade_date: str) -> Dict:
        """
        Get call and put options data for multiple strikes.
        
        Args:
            strikes_dict: Dictionary with strike labels and values
            expiration_date: Expiration date in YYYY-MM-DD format
            trade_date: Trading date in YYYY-MM-DD format
            
        Returns:
            Dictionary containing options data for all strikes
        """
        results = {}
        
        for strike_label, strike_price in strikes_dict.items():
            print(f"  Fetching {strike_label}: {strike_price}")
            
            # Get both call and put data
            call_data = self._fetch_option_data(
                strike_price, expiration_date, trade_date, option_type='C'
            )
            put_data = self._fetch_option_data(
                strike_price, expiration_date, trade_date, option_type='P'
            )
            
            results[strike_label] = {
                'call_data': call_data,
                'put_data': put_data,
                'strike_price': strike_price
            }
            
            time.sleep(self.config.rate_limit_delay)
        
        return results
    
    def _fetch_option_data(self, strike_price: int, expiration_date: str, 
                          trade_date: str, option_type: str) -> Optional[Dict]:
        """
        Fetch data for a single option including current and previous day data.
        
        Args:
            strike_price: Strike price
            expiration_date: Expiration date in YYYY-MM-DD format
            trade_date: Trading date in YYYY-MM-DD format
            option_type: 'C' for call, 'P' for put
            
        Returns:
            Dictionary with option data including previous day data, or None if not found
        """
        # Format strike price and expiration for ticker
        formatted_strike = str(strike_price * 1000).zfill(8)
        exp_date_obj = datetime.strptime(expiration_date, '%Y-%m-%d')
        formatted_exp = exp_date_obj.strftime('%y%m%d')
        
        # Construct options ticker
        ticker = f"O:{self.config.ticker}{formatted_exp}{option_type}{formatted_strike}"
        
        # Get current day data
        current_data = self._fetch_single_day_option(ticker, trade_date)
        
        # Get previous trading day data
        prev_day_data = self._fetch_previous_day_option(ticker, trade_date)
        
        if current_data:
            # Combine current and previous day data
            combined_data = current_data.copy()
            
            if prev_day_data:
                combined_data.update({
                    'prev_open': prev_day_data.get('open'),
                    'prev_close': prev_day_data.get('close'),
                    'prev_volume': prev_day_data.get('volume'),
                    'prev_vwap': prev_day_data.get('vwap')
                })
            else:
                # If no previous day data, set to None
                combined_data.update({
                    'prev_open': None,
                    'prev_close': None,
                    'prev_volume': None,
                    'prev_vwap': None
                })
            
            return combined_data
        else:
            return None
    
    def _fetch_single_day_option(self, ticker: str, trade_date: str) -> Optional[Dict]:
        """Fetch option data for a single day."""
        url = f"{self.base_url}/v2/aggs/ticker/{ticker}/range/1/day/{trade_date}/{trade_date}"
        params = {
            'adjusted': 'true',
            'apikey': self.config.api_key
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
                    'vwap': result.get('vw')
                }
            else:
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"    Error fetching {ticker}: {e}")
            return None
    
    def _fetch_previous_day_option(self, ticker: str, current_date: str) -> Optional[Dict]:
        """
        Fetch option data for the previous trading day.
        
        Args:
            ticker: Options ticker
            current_date: Current trading date in YYYY-MM-DD format
            
        Returns:
            Dictionary with previous day option data or None
        """
        # Calculate previous trading day (accounting for weekends)
        current_dt = datetime.strptime(current_date, '%Y-%m-%d')
        
        # Try up to 5 days back to find previous trading day
        for days_back in range(1, 6):
            prev_date = current_dt - timedelta(days=days_back)
            
            # Skip weekends (Saturday = 5, Sunday = 6)
            if prev_date.weekday() >= 5:
                continue
                
            prev_date_str = prev_date.strftime('%Y-%m-%d')
            
            # Try to fetch data for this date
            data = self._fetch_single_day_option(ticker, prev_date_str)
            if data:
                return data
        
        # If no data found in the last 5 days, return None
        return None
    
    def collect_options_data(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Main function to collect stock and options data.
        
        Returns:
            Tuple of (ordered_df, default_df)
        """
        # Get stock data
        print(f"Fetching {self.config.ticker} stock data from {self.config.start_date} to {self.config.end_date}...")
        stock_data = self.get_stock_data()
        
        if stock_data.empty:
            print("No stock data available")
            return pd.DataFrame(), pd.DataFrame()
        
        print(f"Found {len(stock_data)} days of stock data")
        
        # Collect options data for each day
        all_data = []
        
        for idx, row in stock_data.iterrows():
            trade_date = row['date'].strftime('%Y-%m-%d')
            expiration_date = trade_date if self.config.same_day_expiry else trade_date
            
            # Get strike prices for this day
            strikes_dict = self._get_strikes_for_row(row)
            
            print(f"Processing {trade_date}, Strikes: {list(strikes_dict.values())}, Expiry: {expiration_date}")
            
            # Get options data
            options_data = self.get_options_data_for_strikes(strikes_dict, expiration_date, trade_date)
            
            # Combine stock and options data
            combined_row = self._combine_data(row, options_data, expiration_date)
            all_data.append(combined_row)
            
            time.sleep(0.5)  # Additional delay between days
        
        # Create DataFrames
        default_df = pd.DataFrame(all_data)
        ordered_df = self._reorder_columns(pd.DataFrame(all_data)) if all_data else pd.DataFrame()
        
        return ordered_df, default_df
    
    def _get_strikes_for_row(self, row: pd.Series) -> Dict[str, int]:
        """Get strike prices for a given row based on strategy."""
        strikes = {}
        
        if self.config.strike_strategy == "custom" and self.config.custom_strike_offsets:
            # Use round() function instead of .round() method since row['prev_close'] is a scalar
            atm = int(round(row['prev_close'], 0))
            for offset in self.config.custom_strike_offsets:
                if offset == 0:
                    strikes['atm'] = atm
                elif offset > 0:
                    strikes[f'plus_{offset}'] = atm + (offset * self.config.strike_spacing)
                else:
                    strikes[f'minus_{abs(offset)}'] = atm + (offset * self.config.strike_spacing)
        else:
            # Use the calculated strike columns from the DataFrame
            strike_columns = [col for col in row.index if 'strike' in col]
            for col in strike_columns:
                if pd.notna(row[col]):
                    # Extract label from column name (e.g., 'atm_strike' -> 'atm')
                    label = col.replace('_strike', '').replace('strike_', '')
                    strikes[label] = int(row[col])
        
        return strikes
    
    def _combine_data(self, stock_row: pd.Series, options_data: Dict, expiration_date: str) -> Dict:
        """Combine stock data with options data for a single day."""
        combined_row = {
            'date': stock_row['date'].strftime('%Y-%m-%d'),
            f'{self.config.ticker.lower()}_open': stock_row['open'],
            f'{self.config.ticker.lower()}_high': stock_row['high'],
            f'{self.config.ticker.lower()}_low': stock_row['low'],
            f'{self.config.ticker.lower()}_close': stock_row['close'],
            f'{self.config.ticker.lower()}_close_prev_day': stock_row['prev_close'],
            f'{self.config.ticker.lower()}_volume': stock_row['volume'],
            'expiration_date': expiration_date
        }
        
        # Add options data for each strike
        for strike_label, strike_data in options_data.items():
            strike_price = strike_data['strike_price']
            combined_row[f'{strike_label}_strike'] = strike_price
            
            # Add call data
            if strike_data['call_data']:
                call_data = strike_data['call_data']
                combined_row.update({
                    f'{strike_label}_call_ticker': call_data['ticker'],
                    f'{strike_label}_call_open': call_data['open'],
                    f'{strike_label}_call_high': call_data['high'],
                    f'{strike_label}_call_low': call_data['low'],
                    f'{strike_label}_call_close': call_data['close'],
                    f'{strike_label}_call_volume': call_data['volume'],
                    f'{strike_label}_call_vwap': call_data['vwap'],
                    f'{strike_label}_call_prev_open': call_data['prev_open'],
                    f'{strike_label}_call_prev_close': call_data['prev_close'],
                    f'{strike_label}_call_prev_volume': call_data['prev_volume'],
                    f'{strike_label}_call_prev_vwap': call_data['prev_vwap']
                })
            
            # Add put data
            if strike_data['put_data']:
                put_data = strike_data['put_data']
                combined_row.update({
                    f'{strike_label}_put_ticker': put_data['ticker'],
                    f'{strike_label}_put_open': put_data['open'],
                    f'{strike_label}_put_high': put_data['high'],
                    f'{strike_label}_put_low': put_data['low'],
                    f'{strike_label}_put_close': put_data['close'],
                    f'{strike_label}_put_volume': put_data['volume'],
                    f'{strike_label}_put_vwap': put_data['vwap'],
                    f'{strike_label}_put_prev_open': put_data['prev_open'],
                    f'{strike_label}_put_prev_close': put_data['prev_close'],
                    f'{strike_label}_put_prev_volume': put_data['prev_volume'],
                    f'{strike_label}_put_prev_vwap': put_data['prev_vwap']
                })
        
        return combined_row
    
    def _reorder_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Reorder columns for better organization."""
        if df.empty:
            return df
            
        # Base columns
        base_columns = [
            'date', 
            f'{self.config.ticker.lower()}_open', 
            f'{self.config.ticker.lower()}_high', 
            f'{self.config.ticker.lower()}_low', 
            f'{self.config.ticker.lower()}_close',
            f'{self.config.ticker.lower()}_close_prev_day', 
            f'{self.config.ticker.lower()}_volume', 
            'expiration_date'
        ]
        
        # Get all strike labels and sort them
        strike_labels = []
        for col in df.columns:
            if '_strike' in col and col.endswith('_strike'):
                label = col.replace('_strike', '')
                if label not in strike_labels:
                    strike_labels.append(label)
        
        # Sort strike labels logically
        strike_labels = self._sort_strike_labels(strike_labels)
        
        ordered_columns = base_columns.copy()
        
        # Add strike prices
        for label in strike_labels:
            if f'{label}_strike' in df.columns:
                ordered_columns.append(f'{label}_strike')
        
        # Add call tickers and data
        for label in strike_labels:
            if f'{label}_call_ticker' in df.columns:
                ordered_columns.append(f'{label}_call_ticker')
        
        for data_type in ['open', 'high', 'low', 'close', 'volume', 'vwap', 'prev_open', 'prev_close', 'prev_volume', 'prev_vwap']:
            for label in strike_labels:
                col_name = f'{label}_call_{data_type}'
                if col_name in df.columns:
                    ordered_columns.append(col_name)
        
        # Add put tickers and data
        for label in strike_labels:
            if f'{label}_put_ticker' in df.columns:
                ordered_columns.append(f'{label}_put_ticker')
        
        for data_type in ['open', 'high', 'low', 'close', 'volume', 'vwap', 'prev_open', 'prev_close', 'prev_volume', 'prev_vwap']:
            for label in strike_labels:
                col_name = f'{label}_put_{data_type}'
                if col_name in df.columns:
                    ordered_columns.append(col_name)
        
        # Add any remaining columns
        remaining = [col for col in df.columns if col not in ordered_columns]
        ordered_columns.extend(remaining)
        
        return df[ordered_columns]
    
    def _sort_strike_labels(self, labels: List[str]) -> List[str]:
        """Sort strike labels in logical order (minus_X, atm, plus_X)."""
        minus_labels = []
        plus_labels = []
        atm_labels = []
        
        for label in labels:
            if 'minus_' in label:
                # Extract number and sort by descending order (minus_2, minus_1)
                num = int(label.split('_')[1]) if '_' in label else 0
                minus_labels.append((num, label))
            elif 'plus_' in label:
                # Extract number and sort by ascending order (plus_1, plus_2)
                num = int(label.split('_')[1]) if '_' in label else 0
                plus_labels.append((num, label))
            else:
                atm_labels.append(label)
        
        # Sort and combine
        minus_labels.sort(key=lambda x: x[0], reverse=True)  # minus_2, minus_1
        plus_labels.sort(key=lambda x: x[0])  # plus_1, plus_2
        
        result = [label for _, label in minus_labels]
        result.extend(atm_labels)
        result.extend([label for _, label in plus_labels])
        
        return result
    
    def save_results(self, ordered_df: pd.DataFrame, default_df: pd.DataFrame) -> Tuple[str, str]:
        """Save results to CSV files and create corresponding schema files."""
        prefix = self.config.output_prefix or f"{self.config.ticker.lower()}_options"
        
        ordered_file = f"{prefix}_ordered_{self.config.start_date}_to_{self.config.end_date}.csv"
        default_file = f"{prefix}_default_{self.config.start_date}_to_{self.config.end_date}.csv"
        
        # Create schema for ordered DataFrame
        def create_schema(df: pd.DataFrame, output_file: str):
            schema_data = []
            for column in df.columns:
                dtype = str(df[column].dtype)
                description = self._get_column_description(column)
                schema_data.append([column, dtype, description])
            
            schema_df = pd.DataFrame(schema_data, columns=['Column', 'Type', 'Description'])
            schema_file = output_file.replace('.csv', '_schema.csv')
            schema_df.to_csv(schema_file, index=False)
            print(f"Schema saved to {schema_file}")
        
        if not ordered_df.empty:
            ordered_df.to_csv(ordered_file, index=False)
            create_schema(ordered_df, ordered_file)
            print(f"Ordered data saved to {ordered_file}")
        
        if not default_df.empty:
            default_df.to_csv(default_file, index=False)
            create_schema(default_df, default_file)
            print(f"Default data saved to {default_file}")
        
        return ordered_file, default_file

    def _get_column_description(self, column: str) -> str:
        """Generate description for each column."""
        descriptions = {
            'date': 'Trading date in YYYY-MM-DD format',
            'expiration_date': 'Option expiration date',
            'spy_open': 'SPY opening price for the day',
            'spy_high': 'SPY highest price for the day',
            'spy_low': 'SPY lowest price for the day',
            'spy_close': 'SPY closing price for the day',
            'spy_close_prev_day': 'SPY previous day closing price',
            'spy_volume': 'SPY trading volume for the day'
        }
        
        # Handle strike price columns
        if '_strike' in column:
            return f'Strike price for {column.replace("_strike", "")}'
        
        # Handle option data columns
        for option_type in ['call', 'put']:
            if f'_{option_type}_' in column:
                parts = column.split(f'_{option_type}_')
                strike_label = parts[0]
                data_type = parts[1]
                
                if data_type == 'ticker':
                    return f'Option ticker symbol for {strike_label} {option_type}'
                elif data_type == 'volume':
                    return f'Trading volume for {strike_label} {option_type} option'
                elif data_type == 'vwap':
                    return f'Volume-weighted average price for {strike_label} {option_type} option'
                elif 'prev_' in data_type:
                    metric = data_type.replace('prev_', '')
                    return f'Previous day {metric} for {strike_label} {option_type} option'
                else:
                    return f'{data_type.capitalize()} price for {strike_label} {option_type} option'
        
        return descriptions.get(column, f'Data for {column}')
    
    def print_summary(self, ordered_df: pd.DataFrame):
        """Print summary statistics."""
        if ordered_df.empty:
            print("No data to summarize")
            return
            
        print(f"\nSummary for {self.config.ticker}:")
        print(f"Trading days collected: {len(ordered_df)}")
        print(f"Date range: {ordered_df['date'].min()} to {ordered_df['date'].max()}")
        print(f"Total columns: {len(ordered_df.columns)}")
        
        # Count data availability by strike
        strike_labels = set()
        for col in ordered_df.columns:
            if '_call_close' in col or '_put_close' in col:
                label = col.split('_')[0] + '_' + col.split('_')[1] if 'minus_' in col or 'plus_' in col else col.split('_')[0]
                strike_labels.add(label)
        
        print("\nData availability:")
        for label in sorted(strike_labels):
            call_col = f'{label}_call_close'
            put_col = f'{label}_put_close'
            call_prev_col = f'{label}_call_prev_close'
            put_prev_col = f'{label}_put_prev_close'
            
            call_count = ordered_df[call_col].notna().sum() if call_col in ordered_df.columns else 0
            put_count = ordered_df[put_col].notna().sum() if put_col in ordered_df.columns else 0
            call_prev_count = ordered_df[call_prev_col].notna().sum() if call_prev_col in ordered_df.columns else 0
            put_prev_count = ordered_df[put_prev_col].notna().sum() if put_prev_col in ordered_df.columns else 0
            
            print(f"  {label}: {call_count} call days ({call_prev_count} w/ prev), {put_count} put days ({put_prev_count} w/ prev)")

# Convenience functions for common use cases

def fetch_spy_options(api_key: str, start_date: str, end_date: str, 
                     same_day_expiry: bool = True, **kwargs) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Convenience function to fetch SPY options with default settings.
    
    Args:
        api_key: Polygon.io API key
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        same_day_expiry: Whether to use same-day expiring options
        **kwargs: Additional configuration options
        
    Returns:
        Tuple of (ordered_df, default_df)
    """
    config = OptionsConfig(
        ticker="SPY",
        api_key=api_key,
        start_date=start_date,
        end_date=end_date,
        same_day_expiry=same_day_expiry,
        **kwargs
    )
    
    fetcher = PolygonOptionsDataFetcher(config)
    return fetcher.collect_options_data()

def fetch_custom_options(ticker: str, api_key: str, start_date: str, end_date: str,
                        strike_offsets: List[int], **kwargs) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Convenience function to fetch options with custom strike configuration.
    
    Args:
        ticker: Underlying ticker symbol
        api_key: Polygon.io API key
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        strike_offsets: List of strike offsets from ATM (e.g., [-2, -1, 0, 1, 2])
        **kwargs: Additional configuration options
        
    Returns:
        Tuple of (ordered_df, default_df)
    """
    config = OptionsConfig(
        ticker=ticker.upper(),
        api_key=api_key,
        start_date=start_date,
        end_date=end_date,
        strike_strategy="custom",
        custom_strike_offsets=strike_offsets,
        **kwargs
    )
    
    fetcher = PolygonOptionsDataFetcher(config)
    return fetcher.collect_options_data()

# Example usage and main function
def main():
    """Example usage with different configurations."""
    
    # Your API key
    API_KEY = "Z_ENWpm0RRrvXvLOY65uMH8RB93B4gBN"
    
    # Example 1: Default SPY options (simple)
    print("=== Example 1: Default SPY Options ===")
    ordered_df, default_df = fetch_spy_options(
        api_key=API_KEY,
        start_date="2023-09-01",
        end_date="2025-08-30"
    )
    
    # Example 2: SPY with wider strikes and more above ATM
    print("\n=== Example 2: SPY with Wide Strikes ===")
    config2 = OptionsConfig(
        ticker="SPY",
        api_key=API_KEY,
        start_date="2023-09-01",
        end_date="2025-08-30",
        strike_strategy="symmetric",
        strike_spacing=2,  # 2-point spacing
        num_strikes_above=5,
        num_strikes_below=3,
        output_prefix="spy_wide_strikes"
    )
    
    fetcher2 = PolygonOptionsDataFetcher(config2)
    ordered_df2, default_df2 = fetcher2.collect_options_data()
    
    # Save and summarize results
    for i, (ordered, default, fetcher_obj) in enumerate([
        (ordered_df, default_df, None),
        (ordered_df2, default_df2, fetcher2)
    ], 1):
        if not ordered.empty and fetcher_obj:
            files = fetcher_obj.save_results(ordered, default)
            fetcher_obj.print_summary(ordered)

if __name__ == "__main__":
    main()

# Quick usage examples:

"""
# Simple SPY options for a date range
ordered_df, default_df = fetch_spy_options(
    api_key="your_api_key",
    start_date="2024-12-01", 
    end_date="2024-12-31"
)

# Custom ticker with specific strikes
ordered_df, default_df = fetch_custom_options(
    ticker="AAPL",
    api_key="your_api_key", 
    start_date="2024-12-01",
    end_date="2024-12-31",
    strike_offsets=[-10, -5, -2, -1, 0, 1, 2, 5, 10]
)

# Advanced configuration
config = OptionsConfig(
    ticker="TSLA",
    api_key="your_api_key",
    start_date="2024-12-01",
    end_date="2024-12-31", 
    strike_strategy="calls_only",
    num_strikes_above=10,
    strike_spacing=5,
    rate_limit_delay=0.2
)
fetcher = PolygonOptionsDataFetcher(config)
ordered_df, default_df = fetcher.collect_options_data()
"""