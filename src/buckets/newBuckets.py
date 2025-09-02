import requests
import json
from datetime import datetime, timedelta
from collections import defaultdict

class PolygonPatternAnalyzer:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.polygon.io"
        
        # Initialize lookup table for all possible patterns (2-5 minutes)
        self.pattern_table = self.create_pattern_lookup_table()
        
        # Initialize CSV tracking for each pattern
        self.pattern_records = {pattern: [] for pattern in self.pattern_table.keys()}
        
    def create_pattern_lookup_table(self):
        """
        Create a lookup table for all possible patterns of length 2-5
        Each pattern has: total_change, occurrences
        """
        patterns = {}
        
        # Generate all possible patterns for lengths 2-5
        for length in range(2, 6):
            # Generate all binary combinations for this length
            for i in range(2 ** length):
                binary = format(i, f'0{length}b')
                pattern = binary.replace('0', 'N').replace('1', 'P')
                patterns[pattern] = {'total_change': 0.0, 'occurrences': 0}
        
        return patterns
    
    def get_aggs(self, symbol, start_date, end_date):
        """
        Fetch minute-level aggregated data from Polygon.io
        """
        url = f"{self.base_url}/v2/aggs/ticker/{symbol}/range/1/minute/{start_date}/{end_date}"
        params = {
            'adjusted': 'true',
            'sort': 'asc',
            'limit': 50000,
            'apikey': self.api_key
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if response.status_code != 200:
                print(f"Error: API returned status code {response.status_code}")
                print(f"Response: {data}")
                return []
                
            if data.get('status') == 'OK' and 'results' in data:
                print(f"Successfully retrieved {len(data['results'])} bars")
                return data['results']
            elif data.get('status') == 'DELAYED':
                print("Note: You're using a free API key with delayed data access.")
                print("Try using historical dates from several days ago, or upgrade to a paid plan.")
                print("Attempting to retrieve available data...")
                return data.get('results', [])
            else:
                print(f"API Status: {data.get('status')}")
                if data.get('error'):
                    print(f"API Error: {data.get('error')}")
                if data.get('message'):
                    print(f"API Message: {data.get('message')}")
                print(f"Request URL: {url}")
                print(f"Parameters: {params}")
                
                if 'results' in data and data['results']:
                    print(f"Found {len(data['results'])} bars despite API status")
                    return data['results']
                return []
                    
        except requests.exceptions.RequestException as e:
            print(f"Network Error: {str(e)}")
            return []
    
    def classify_bar(self, bar):
        """
        Classify a minute bar as Positive (P) or Negative (N)
        Based on close vs open price
        """
        if bar['c'] >= bar['o']:  # close >= open
            return 'P'
        else:
            return 'N'
    
    def get_subpatterns(self, pattern):
        """
        Get all subpatterns of a given pattern
        For example, 'NNN' has subpatterns: 'NN' (positions 0-1), 'NN' (positions 1-2)
        """
        subpatterns = []
        pattern_length = len(pattern)
        
        for sub_length in range(2, pattern_length):  # All lengths shorter than main pattern
            for start_pos in range(pattern_length - sub_length + 1):
                subpattern = pattern[start_pos:start_pos + sub_length]
                subpatterns.append(subpattern)
        
        return subpatterns
    
    def process_pattern_and_subtract(self, pattern, price_change, start_timestamp, end_timestamp):
        """
        Add pattern to lookup table and subtract from all embedded subpatterns
        Also record the timestamp and price change for CSV export
        """
        # Add to the main pattern
        self.pattern_table[pattern]['total_change'] += price_change
        self.pattern_table[pattern]['occurrences'] += 1
        
        # Record for CSV export
        self.pattern_records[pattern].append({
            'start_timestamp': start_timestamp,
            'end_timestamp': end_timestamp,
            'price_change': price_change
        })
        
        # Subtract from all subpatterns to avoid double counting
        subpatterns = self.get_subpatterns(pattern)
        for subpattern in subpatterns:
            self.pattern_table[subpattern]['total_change'] -= price_change
            self.pattern_table[subpattern]['occurrences'] -= 1
            
            # Record negative entries for subpatterns (showing they were part of larger pattern)
            self.pattern_records[subpattern].append({
                'start_timestamp': start_timestamp,
                'end_timestamp': end_timestamp,
                'price_change': -price_change,
                'note': f'Subtracted as part of {pattern} pattern'
            })
    
    def analyze_patterns(self, bars):
        """
        Analyze patterns using the lookup table approach with subtraction logic
        """
        # Reset the lookup table and records
        for pattern_data in self.pattern_table.values():
            pattern_data['total_change'] = 0.0
            pattern_data['occurrences'] = 0
        
        for pattern in self.pattern_records:
            self.pattern_records[pattern] = []
        
        # Process bars one by one, looking for patterns of all lengths
        for i in range(len(bars)):
            # Check for patterns of different lengths starting at position i
            for pattern_length in range(5, 1, -1):  # Start with longest patterns first
                if i + pattern_length <= len(bars):
                    # Extract pattern
                    pattern_bars = bars[i:i + pattern_length]
                    pattern_string = ''.join([self.classify_bar(bar) for bar in pattern_bars])
                    
                    # Calculate price change for this pattern
                    first_open = pattern_bars[0]['o']
                    last_close = pattern_bars[-1]['c']
                    price_change = last_close - first_open
                    
                    # Get timestamps (convert from milliseconds)
                    start_timestamp = datetime.fromtimestamp(pattern_bars[0]['t'] / 1000)
                    end_timestamp = datetime.fromtimestamp(pattern_bars[-1]['t'] / 1000)
                    
                    # Add to pattern and subtract from subpatterns
                    self.process_pattern_and_subtract(pattern_string, price_change, 
                                                    start_timestamp, end_timestamp)
        
        return self.pattern_table
    
    def verify_total_change(self, bars, pattern_table):
        """
        Verify that the sum of all pattern changes equals the total price change
        """
        if not bars:
            return
            
        # Calculate actual total price change from data
        actual_total_change = bars[-1]['c'] - bars[0]['o']  # last close - first open
        
        # Calculate sum of all pattern changes
        pattern_total_change = sum(stats['total_change'] for stats in pattern_table.values())
        
        print(f"\n" + "="*80)
        print("VERIFICATION OF TOTAL PRICE CHANGE")
        print("="*80)
        print(f"Actual total price change (Last Close - First Open): {actual_total_change:.4f}")
        print(f"Sum of all pattern changes: {pattern_total_change:.4f}")
        print(f"Difference: {abs(actual_total_change - pattern_total_change):.4f}")
        
        if abs(actual_total_change - pattern_total_change) < 0.001:
            print("✓ VERIFICATION PASSED: Pattern changes sum correctly!")
        else:
            print("✗ VERIFICATION FAILED: There's a discrepancy in the calculations")
            print("This might indicate overlapping patterns or calculation errors.")
        
        # Additional verification - show first and last bar details
        print(f"\nFirst bar: Open={bars[0]['o']:.4f}, Close={bars[0]['c']:.4f}, "
              f"Time={datetime.fromtimestamp(bars[0]['t']/1000)}")
        print(f"Last bar:  Open={bars[-1]['o']:.4f}, Close={bars[-1]['c']:.4f}, "
              f"Time={datetime.fromtimestamp(bars[-1]['t']/1000)}")
    
    def export_raw_data_csv(self, bars, symbol, start_date, end_date):
        """
        Export raw minute-by-minute data to CSV
        """
        import csv
        import os
        
        # Create directory for CSV files
        csv_dir = f"pattern_analysis_{symbol}_{start_date}_to_{end_date}"
        os.makedirs(csv_dir, exist_ok=True)
        
        csv_filename = os.path.join(csv_dir, f"raw_{symbol}_{start_date}_to_{end_date}.csv")
        
        with open(csv_filename, 'w', newline='') as csvfile:
            fieldnames = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'vwap', 'classification']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            # Write header
            writer.writeheader()
            
            # Write all raw data
            for bar in bars:
                timestamp = datetime.fromtimestamp(bar['t'] / 1000)
                classification = self.classify_bar(bar)
                
                row = {
                    'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'open': f"{bar['o']:.4f}",
                    'high': f"{bar['h']:.4f}",
                    'low': f"{bar['l']:.4f}",
                    'close': f"{bar['c']:.4f}",
                    'volume': bar['v'],
                    'vwap': f"{bar.get('vw', 0):.4f}",
                    'classification': classification
                }
                writer.writerow(row)
        
        print(f"Exported raw data to: {csv_filename}")
        return csv_filename
    
    def export_pattern_csvs(self, symbol, start_date, end_date):
        """
        Export CSV files for each pattern with timestamp and total price change data
        Format: timestamp, total_price_change
        """
        import csv
        import os
        
        # Create directory for CSV files
        csv_dir = f"pattern_analysis_{symbol}_{start_date}_to_{end_date}"
        os.makedirs(csv_dir, exist_ok=True)
        
        exported_count = 0
        
        for pattern, records in self.pattern_records.items():
            # Only export patterns that have positive occurrences (actual patterns, not subtractions)
            positive_records = [r for r in records if r['price_change'] > 0 or 'note' not in r]
            
            if positive_records:  # Only export patterns that have actual data
                csv_filename = os.path.join(csv_dir, f"pattern_{pattern}.csv")
                
                with open(csv_filename, 'w', newline='') as csvfile:
                    fieldnames = ['timestamp', 'total_price_change']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    
                    # Write header
                    writer.writeheader()
                    
                    # Filter and sort records by timestamp
                    actual_records = [r for r in positive_records if 'note' not in r]
                    actual_records.sort(key=lambda x: x['start_timestamp'])
                    
                    # Write records for this pattern (sorted by timestamp)
                    for record in actual_records:
                        row = {
                            'timestamp': record['start_timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                            'total_price_change': f"{record['price_change']:.4f}"
                        }
                        writer.writerow(row)
                
                exported_count += 1
        
        print(f"Exported {exported_count} pattern CSV files to directory: {csv_dir}")
        return csv_dir
    
    def print_results(self, pattern_table):
        """
        Print the final results with total price changes from lookup table
        """
        print("\n" + "="*100)
        print("STOCK PATTERN ANALYSIS RESULTS - LOOKUP TABLE WITH SUBTRACTION METHOD")
        print("="*100)
        print(f"{'Pattern':<10} {'CSV Rows':<10} {'Total Price Change':<20} {'Avg Change/Pattern':<20} {'Avg Change/Minute':<18}")
        print("-" * 100)
        print("Note: 'CSV Rows' = Number of occurrences (each row in pattern CSV = one occurrence)")
        print("-" * 100)
        
        # Filter and sort patterns that have occurrences
        active_patterns = {k: v for k, v in pattern_table.items() if v['occurrences'] > 0}
        sorted_patterns = sorted(active_patterns.keys(), key=lambda x: (len(x), x))
        
        total_patterns = 0
        total_price_change = 0
        
        for pattern in sorted_patterns:
            stats = pattern_table[pattern]
            count = stats['occurrences']
            total_change = stats['total_change']
            
            if count > 0:
                avg_change_per_pattern = total_change / count
                pattern_length = len(pattern)
                avg_change_per_minute = avg_change_per_pattern / pattern_length
                
                print(f"{pattern:<10} {count:<10} {total_change:<20.4f} {avg_change_per_pattern:<20.4f} {avg_change_per_minute:<18.4f}")
                total_patterns += count
                total_price_change += total_change
        
        print("-" * 100)
        print(f"Total unique patterns: {total_patterns}")
        print(f"Total cumulative price change: {total_price_change:.4f}")
        print("Note: To see exact timestamps for each pattern occurrence, check the individual CSV files")
        
        # Print summary by pattern length
        print("\nSUMMARY BY PATTERN LENGTH:")
        print("-" * 60)
        for length in range(2, 6):
            length_patterns = [p for p in sorted_patterns if len(p) == length]
            length_count = sum(pattern_table[p]['occurrences'] for p in length_patterns)
            length_total_change = sum(pattern_table[p]['total_change'] for p in length_patterns)
            unique_patterns_found = len(length_patterns)
            max_possible = 2 ** length
            
            if length_count > 0:
                avg_change = length_total_change / length_count if length_count > 0 else 0
                print(f"{length}-minute patterns: {length_count} net occurrences (CSV rows), "
                      f"{unique_patterns_found}/{max_possible} unique patterns found, "
                      f"total change: {length_total_change:.4f}, "
                      f"avg change: {avg_change:.4f}")
            else:
                print(f"{length}-minute patterns: 0 net occurrences")
        
        # Show most and least profitable patterns (by total change)
        if active_patterns:
            print("\nTOP PERFORMING PATTERNS BY TOTAL CHANGE:")
            print("-" * 50)
            by_total_change = sorted(active_patterns.items(), 
                                   key=lambda x: x[1]['total_change'], reverse=True)
            
            print("Most Profitable (by total change):")
            for pattern, stats in by_total_change[:5]:
                avg_change = stats['total_change'] / stats['occurrences']
                print(f"  {pattern}: {stats['occurrences']} occurrences, "
                      f"total: {stats['total_change']:.4f}, "
                      f"avg: {avg_change:.4f}")
            
            print("\nLeast Profitable (by total change):")
            for pattern, stats in by_total_change[-5:]:
                avg_change = stats['total_change'] / stats['occurrences']
                print(f"  {pattern}: {stats['occurrences']} occurrences, "
                      f"total: {stats['total_change']:.4f}, "
                      f"avg: {avg_change:.4f}")
            
            # Show by average change per pattern
            print("\nTOP PERFORMING PATTERNS BY AVERAGE CHANGE:")
            print("-" * 50)
            by_avg_change = sorted(active_patterns.items(), 
                                 key=lambda x: x[1]['total_change'] / x[1]['occurrences'], reverse=True)
            
            print("Highest Average Change:")
            for pattern, stats in by_avg_change[:5]:
                avg_change = stats['total_change'] / stats['occurrences']
                print(f"  {pattern}: {stats['occurrences']} occurrences, "
                      f"avg: {avg_change:.4f}, "
                      f"total: {stats['total_change']:.4f}")
    
    def run_analysis(self, symbol, start_date, end_date):
        """
        Main method to run the complete analysis
        """
        print(f"Fetching data for {symbol} from {start_date} to {end_date}...")
        
        # Get the minute-level data
        bars = self.get_aggs(symbol, start_date, end_date)
        
        # If no data found, try with older dates
        if not bars:
            print("No data found with current date range. Trying older dates...")
            older_end = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            older_start = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
            print(f"Trying date range: {older_start} to {older_end}")
            bars = self.get_aggs(symbol, older_start, older_end)
        
        if not bars:
            print("Still no data. Trying much older dates...")
            much_older_end = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            much_older_start = (datetime.now() - timedelta(days=37)).strftime("%Y-%m-%d")
            print(f"Trying date range: {much_older_start} to {much_older_end}")
            bars = self.get_aggs(symbol, much_older_start, much_older_end)
        
        if not bars:
            print("No data available for analysis after trying multiple date ranges.")
            print("This might be due to:")
            print("1. Free API tier limitations")
            print("2. Weekend/holiday dates with no trading data") 
            print("3. Network issues")
            print("Try running the script on a weekday or with a paid API key.")
            return
        
        print(f"Retrieved {len(bars)} minute bars")
        print(f"Initialized lookup table with {len(self.pattern_table)} possible patterns")
        
        # Export raw data CSV first
        raw_csv = self.export_raw_data_csv(bars, symbol, start_date, end_date)
        
        # Analyze the patterns using lookup table approach
        pattern_table = self.analyze_patterns(bars)
        
        # Verify that total changes add up correctly
        self.verify_total_change(bars, pattern_table)
        
        # Print results
        self.print_results(pattern_table)
        
        # Export CSV files for each pattern
        csv_dir = self.export_pattern_csvs(symbol, start_date, end_date)

def main():
    # Configuration
    API_KEY = "Z_ENWpm0RRrvXvLOY65uMH8RB93B4gBN"  # Replace with your actual API key
    SYMBOL = "GLD"  # Stock symbol to analyze
    
    # Use historical dates to avoid future date issues and API limitations
    end_date = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    
    print(f"Using date range: {start_date} to {end_date}")
    
    # Create analyzer instance
    analyzer = PolygonPatternAnalyzer(API_KEY)
    
    # Run the analysis
    analyzer.run_analysis(SYMBOL, start_date, end_date)

if __name__ == "__main__":
    main()