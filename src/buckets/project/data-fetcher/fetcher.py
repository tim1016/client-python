"""
Standalone Data Fetcher for Stock Market Data
Fetches and stores raw minute-level data from Polygon.io API
Configuration-driven approach using config.json
"""

import requests
import json
import csv
import os
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import logging
import argparse
from pathlib import Path

class StockDataFetcher:
    """Handles all data fetching operations from Polygon.io API."""
    
    def __init__(self, config_path: str = "config.json"):
        """Initialize fetcher with configuration file."""
        self.config = self.load_config(config_path)
        self.api_key = self.config['api']['key']
        self.base_url = self.config['api']['base_url']
        self.output_dir = self.config['storage']['output_dir']
        self.setup_logging()
        self.ensure_output_directory()
        
    def load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON file."""
        if not os.path.exists(config_path):
            # Create default config if it doesn't exist
            self.create_default_config(config_path)
            print(f"Created default config at {config_path}. Please edit it with your settings.")
            raise FileNotFoundError(f"Please configure {config_path} with your API key and settings.")
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Validate required fields
        required_fields = ['api', 'storage', 'fetch_settings']
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Missing required config section: {field}")
        
        return config
    
    def create_default_config(self, config_path: str):
        """Create a default configuration file template."""
        default_config = {
            "api": {
                "key": "YOUR_POLYGON_API_KEY_HERE",
                "base_url": "https://api.polygon.io",
                "rate_limit_delay": 0.5,
                "retry_count": 3,
                "timeout": 30
            },
            "storage": {
                "output_dir": "market_data",
                "create_subdirs": True,
                "raw_data_dir": "raw",
                "metadata_dir": "metadata",
                "log_dir": "logs"
            },
            "fetch_settings": {
                "symbols": ["SPY", "QQQ", "AAPL"],
                "start_date": "2023-01-01",
                "end_date": "2024-01-01",
                "chunk_days": 30,
                "timeframe": "minute",
                "multiplier": 1,
                "adjusted": True,
                "sort": "asc",
                "limit": 50000
            },
            "data_quality": {
                "remove_duplicates": True,
                "validate_timestamps": True,
                "check_gaps": True,
                "log_anomalies": True
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(levelname)s - %(message)s",
                "file_logging": True,
                "console_logging": True
            }
        }
        
        with open(config_path, 'w') as f:
            json.dump(default_config, f, indent=2)
    
    def setup_logging(self):
        """Configure logging based on config settings."""
        log_config = self.config.get('logging', {})
        log_level = getattr(logging, log_config.get('level', 'INFO'))
        log_format = log_config.get('format', '%(asctime)s - %(levelname)s - %(message)s')
        
        handlers = []
        
        # File handler
        if log_config.get('file_logging', True):
            log_dir = os.path.join(self.output_dir, self.config['storage'].get('log_dir', 'logs'))
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, f"fetch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
            handlers.append(logging.FileHandler(log_file))
        
        # Console handler
        if log_config.get('console_logging', True):
            handlers.append(logging.StreamHandler())
        
        logging.basicConfig(
            level=log_level,
            format=log_format,
            handlers=handlers
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Logging initialized with config: {log_config}")
        
    def ensure_output_directory(self):
        """Create output directory structure based on config."""
        storage_config = self.config['storage']
        
        # Create main output directory
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Create subdirectories if configured
        if storage_config.get('create_subdirs', True):
            subdirs = ['raw_data_dir', 'metadata_dir', 'log_dir']
            for subdir_key in subdirs:
                if subdir_key in storage_config:
                    subdir_path = os.path.join(self.output_dir, storage_config[subdir_key])
                    os.makedirs(subdir_path, exist_ok=True)
                    self.logger.info(f"Created directory: {subdir_path}")
        
    def validate_api_key(self) -> bool:
        """Validate the API key by making a test request."""
        if self.api_key == "YOUR_POLYGON_API_KEY_HERE":
            self.logger.error("API key not configured. Please update config.json")
            return False
            
        test_url = f"{self.base_url}/v2/aggs/ticker/AAPL/range/1/day/2024-01-01/2024-01-01"
        params = {'apikey': self.api_key}
        
        try:
            timeout = self.config['api'].get('timeout', 30)
            response = requests.get(test_url, params=params, timeout=timeout)
            if response.status_code == 200:
                self.logger.info("API key validated successfully")
                return True
            else:
                self.logger.error(f"API key validation failed: {response.status_code}")
                return False
        except Exception as e:
            self.logger.error(f"API key validation error: {str(e)}")
            return False
    
    def fetch_minute_data(self, symbol: str, start_date: str, end_date: str) -> Optional[List[Dict]]:
        """
        Fetch minute-level data with retry logic and error handling.
        
        Args:
            symbol: Stock ticker symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            List of minute bars or None if failed
        """
        fetch_settings = self.config['fetch_settings']
        api_config = self.config['api']
        
        timeframe = fetch_settings.get('timeframe', 'minute')
        multiplier = fetch_settings.get('multiplier', 1)
        
        url = f"{self.base_url}/v2/aggs/ticker/{symbol}/range/{multiplier}/{timeframe}/{start_date}/{end_date}"
        
        params = {
            'adjusted': str(fetch_settings.get('adjusted', True)).lower(),
            'sort': fetch_settings.get('sort', 'asc'),
            'limit': fetch_settings.get('limit', 50000),
            'apikey': self.api_key
        }
        
        retry_count = api_config.get('retry_count', 3)
        timeout = api_config.get('timeout', 30)
        
        for attempt in range(retry_count):
            try:
                self.logger.info(f"Fetching {symbol} data: {start_date} to {end_date} (Attempt {attempt + 1})")
                
                response = requests.get(url, params=params, timeout=timeout)
                response.raise_for_status()
                data = response.json()
                
                if data.get('status') == 'OK' and 'results' in data:
                    bars = data['results']
                    self.logger.info(f"Successfully fetched {len(bars)} bars for {symbol}")
                    
                    # Data quality checks if configured
                    if self.config.get('data_quality', {}).get('validate_timestamps', True):
                        bars = self.validate_timestamps(bars, symbol)
                    
                    return bars
                    
                elif data.get('status') == 'DELAYED':
                    self.logger.warning("Using delayed data (free tier limitation)")
                    return data.get('results', [])
                    
                else:
                    self.logger.warning(f"Unexpected API response: {data.get('status')}")
                    if attempt < retry_count - 1:
                        time.sleep(2 ** attempt)  # Exponential backoff
                        
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Request error (attempt {attempt + 1}): {str(e)}")
                if attempt < retry_count - 1:
                    time.sleep(2 ** attempt)
                    
            except json.JSONDecodeError as e:
                self.logger.error(f"JSON decode error: {str(e)}")
                if attempt < retry_count - 1:
                    time.sleep(2 ** attempt)
                    
        self.logger.error(f"Failed to fetch data after {retry_count} attempts")
        return None
    
    def validate_timestamps(self, bars: List[Dict], symbol: str) -> List[Dict]:
        """Validate and log timestamp issues."""
        if not bars:
            return bars
        
        quality_config = self.config.get('data_quality', {})
        
        # Check for gaps
        if quality_config.get('check_gaps', True):
            gaps = []
            for i in range(1, len(bars)):
                time_diff = (bars[i]['t'] - bars[i-1]['t']) / 60000  # Convert to minutes
                if time_diff > 1.5:  # More than 1.5 minutes gap
                    gaps.append({
                        'index': i,
                        'gap_minutes': time_diff,
                        'timestamp': datetime.fromtimestamp(bars[i]['t'] / 1000)
                    })
            
            if gaps and quality_config.get('log_anomalies', True):
                self.logger.warning(f"Found {len(gaps)} time gaps in {symbol} data")
                for gap in gaps[:5]:  # Log first 5 gaps
                    self.logger.debug(f"Gap at index {gap['index']}: {gap['gap_minutes']:.1f} minutes")
        
        # Remove duplicates
        if quality_config.get('remove_duplicates', True):
            seen = set()
            unique_bars = []
            duplicates = 0
            
            for bar in bars:
                if bar['t'] not in seen:
                    seen.add(bar['t'])
                    unique_bars.append(bar)
                else:
                    duplicates += 1
            
            if duplicates > 0:
                self.logger.info(f"Removed {duplicates} duplicate bars from {symbol}")
            
            return unique_bars
        
        return bars
    
    def fetch_data_in_chunks(self, symbol: str, start_date: str, end_date: str) -> List[Dict]:
        """
        Fetch data in smaller chunks to handle API limitations.
        
        Args:
            symbol: Stock ticker symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            Combined list of all bars
        """
        chunk_days = self.config['fetch_settings'].get('chunk_days', 30)
        rate_limit_delay = self.config['api'].get('rate_limit_delay', 0.5)
        
        all_bars = []
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        
        current_start = start
        while current_start < end:
            current_end = min(current_start + timedelta(days=chunk_days), end)
            
            chunk_start = current_start.strftime('%Y-%m-%d')
            chunk_end = current_end.strftime('%Y-%m-%d')
            
            bars = self.fetch_minute_data(symbol, chunk_start, chunk_end)
            if bars:
                all_bars.extend(bars)
                self.logger.info(f"Chunk complete: {chunk_start} to {chunk_end} ({len(bars)} bars)")
            else:
                self.logger.warning(f"No data for chunk: {chunk_start} to {chunk_end}")
            
            # Rate limiting
            time.sleep(rate_limit_delay)
            current_start = current_end + timedelta(days=1)
        
        # Final deduplication
        if self.config.get('data_quality', {}).get('remove_duplicates', True):
            seen = set()
            unique_bars = []
            for bar in all_bars:
                if bar['t'] not in seen:
                    seen.add(bar['t'])
                    unique_bars.append(bar)
            
            self.logger.info(f"Total bars fetched: {len(unique_bars)} (removed {len(all_bars) - len(unique_bars)} duplicates)")
            return unique_bars
        
        return all_bars
    
    def save_raw_data(self, bars: List[Dict], symbol: str, start_date: str, end_date: str) -> str:
        """Save raw data to CSV file."""
        raw_dir = os.path.join(self.output_dir, self.config['storage'].get('raw_data_dir', 'raw'))
        filename = f"{symbol}_{start_date}_to_{end_date}_raw.csv"
        filepath = os.path.join(raw_dir, filename)
        
        with open(filepath, 'w', newline='') as csvfile:
            fieldnames = ['timestamp', 'unix_ms', 'open', 'high', 'low', 'close', 
                         'volume', 'vwap', 'trades']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for bar in bars:
                timestamp = datetime.fromtimestamp(bar['t'] / 1000)
                row = {
                    'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'unix_ms': bar['t'],
                    'open': bar['o'],
                    'high': bar['h'],
                    'low': bar['l'],
                    'close': bar['c'],
                    'volume': bar['v'],
                    'vwap': bar.get('vw', 0),
                    'trades': bar.get('n', 0)
                }
                writer.writerow(row)
        
        self.logger.info(f"Raw data saved to: {filepath}")
        return filepath
    
    def save_metadata(self, symbol: str, start_date: str, end_date: str, 
                     bars_count: int, filepath: str) -> str:
        """Save metadata about the fetched data."""
        metadata_dir = os.path.join(self.output_dir, self.config['storage'].get('metadata_dir', 'metadata'))
        
        metadata = {
            'symbol': symbol,
            'start_date': start_date,
            'end_date': end_date,
            'fetch_timestamp': datetime.now().isoformat(),
            'bars_count': bars_count,
            'data_file': filepath,
            'api_source': 'polygon.io',
            'timeframe': f"{self.config['fetch_settings'].get('multiplier', 1)}{self.config['fetch_settings'].get('timeframe', 'minute')}",
            'config_used': {
                'chunk_days': self.config['fetch_settings'].get('chunk_days', 30),
                'adjusted': self.config['fetch_settings'].get('adjusted', True),
                'data_quality': self.config.get('data_quality', {})
            }
        }
        
        metadata_file = f"{symbol}_{start_date}_to_{end_date}_metadata.json"
        metadata_path = os.path.join(metadata_dir, metadata_file)
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        self.logger.info(f"Metadata saved to: {metadata_path}")
        return metadata_path
    
    def fetch_from_config(self):
        """Fetch data using settings from config file."""
        fetch_settings = self.config['fetch_settings']
        symbols = fetch_settings.get('symbols', [])
        start_date = fetch_settings.get('start_date')
        end_date = fetch_settings.get('end_date')
        
        if not symbols:
            self.logger.error("No symbols specified in config")
            return {}
        
        self.logger.info(f"Starting fetch for {len(symbols)} symbols from {start_date} to {end_date}")
        
        results = {}
        
        for symbol in symbols:
            self.logger.info(f"\n{'='*60}")
            self.logger.info(f"Processing {symbol}")
            self.logger.info(f"{'='*60}")
            
            bars = self.fetch_data_in_chunks(symbol, start_date, end_date)
            
            if bars:
                filepath = self.save_raw_data(bars, symbol, start_date, end_date)
                metadata_path = self.save_metadata(symbol, start_date, end_date, len(bars), filepath)
                
                results[symbol] = {
                    'success': True,
                    'bars_count': len(bars),
                    'data_file': filepath,
                    'metadata_file': metadata_path
                }
            else:
                results[symbol] = {
                    'success': False,
                    'error': 'Failed to fetch data'
                }
            
            # Rate limiting between symbols
            time.sleep(self.config['api'].get('rate_limit_delay', 0.5))
        
        # Save summary
        summary_file = os.path.join(self.output_dir, f"fetch_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(summary_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        self.logger.info(f"\n{'='*60}")
        self.logger.info("FETCH SUMMARY")
        self.logger.info(f"{'='*60}")
        for symbol, result in results.items():
            status = "✓" if result['success'] else "✗"
            bars_info = f"{result.get('bars_count', 'Failed')} bars" if result['success'] else result.get('error', 'Unknown error')
            self.logger.info(f"{status} {symbol}: {bars_info}")
        
        self.logger.info(f"\nSummary saved to: {summary_file}")
        
        return results


def main():
    """Main entry point for the data fetcher."""
    parser = argparse.ArgumentParser(description='Fetch stock market minute data from Polygon.io')
    parser.add_argument('--config', default='config.json', help='Path to configuration file')
    parser.add_argument('--validate-only', action='store_true', help='Only validate API key and exit')
    
    args = parser.parse_args()
    
    try:
        # Initialize fetcher with config
        fetcher = StockDataFetcher(args.config)
        
        # Validate API key
        if not fetcher.validate_api_key():
            print("Invalid API key. Please check your configuration.")
            return 1
        
        if args.validate_only:
            print("API key validation successful!")
            return 0
        
        # Fetch data using config settings
        results = fetcher.fetch_from_config()
        
        # Return status
        return 0 if all(r['success'] for r in results.values()) else 1
        
    except FileNotFoundError as e:
        print(f"Configuration error: {e}")
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())