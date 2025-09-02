import requests
import json
from datetime import datetime, timedelta
from collections import defaultdict
import csv
import os

class PolygonPatternAnalyzer:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.polygon.io"
        
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
    
    def identify_all_patterns(self, bars, durations):
        """
        Step 1: Universal Pattern Identification
        Identifies all possible patterns of specified durations
        Returns list of pattern dictionaries with metadata
        """
        all_patterns = []
        
        for i in range(len(bars)):
            for duration in durations:
                # Find the end index for this duration
                end_index = i + duration - 1
                
                if end_index < len(bars):
                    pattern_bars = bars[i:end_index + 1]
                    
                    # Build pattern string
                    pattern_string = ''.join([self.classify_bar(bar) for bar in pattern_bars])
                    
                    # Calculate metrics
                    start_price = pattern_bars[0]['o']
                    end_price = pattern_bars[-1]['c']
                    price_change = end_price - start_price
                    
                    # Get timestamps
                    start_timestamp = datetime.fromtimestamp(pattern_bars[0]['t'] / 1000)
                    end_timestamp = datetime.fromtimestamp(pattern_bars[-1]['t'] / 1000)
                    
                    # Calculate total volume
                    total_volume = sum(bar['v'] for bar in pattern_bars)
                    
                    pattern_info = {
                        'pattern': pattern_string,
                        'duration': duration,
                        'start_time': start_timestamp,
                        'end_time': end_timestamp,
                        'start_index': i,
                        'end_index': end_index,
                        'price_change': price_change,
                        'volume': total_volume,
                        'start_price': start_price,
                        'end_price': end_price
                    }
                    
                    all_patterns.append(pattern_info)
        
        return all_patterns
    
    def resolve_overlaps(self, patterns):
        """
        Step 2 & 3: Hierarchical Sorting and Temporal Interval Marking
        Implements the corrected methodology from the document
        Prioritizes longer patterns over shorter ones
        """
        # Step 2: Hierarchical Sorting (duration descending, then start_time ascending)
        sorted_patterns = sorted(patterns, 
                               key=lambda x: (-x['duration'], x['start_time']))
        
        resolved_patterns = []
        claimed_indices = set()  # Track which bar indices have been claimed
        
        # Step 3: Temporal Interval Marking
        for pattern in sorted_patterns:
            # Check if this pattern's indices overlap with any claimed indices
            pattern_indices = set(range(pattern['start_index'], pattern['end_index'] + 1))
            
            if not pattern_indices.intersection(claimed_indices):
                # No overlap - this pattern is valid
                resolved_patterns.append(pattern)
                claimed_indices.update(pattern_indices)
        
        return resolved_patterns
    
    def aggregate_patterns(self, unique_patterns):
        """
        Step 4: Final Aggregation
        Aggregates the non-overlapping patterns into summary statistics
        """
        pattern_summary = defaultdict(lambda: {
            'count': 0, 
            'total_profit': 0.0, 
            'total_volume': 0,
            'occurrences': []
        })
        
        for pattern in unique_patterns:
            pattern_str = pattern['pattern']
            summary = pattern_summary[pattern_str]
            
            summary['count'] += 1
            summary['total_profit'] += pattern['price_change']
            summary['total_volume'] += pattern['volume']
            summary['occurrences'].append({
                'start_time': pattern['start_time'],
                'end_time': pattern['end_time'],
                'price_change': pattern['price_change'],
                'volume': pattern['volume']
            })
        
        return pattern_summary
    
    def verify_total_change(self, bars, unique_patterns):
        """
        Verify that the sum of non-overlapping pattern changes is valid
        Note: Won't equal total change since not all minutes may be in patterns
        """
        if not bars:
            return
            
        # Calculate actual total price change from data
        actual_total_change = bars[-1]['c'] - bars[0]['o']
        
        # Calculate sum of unique pattern changes
        pattern_total_change = sum(p['price_change'] for p in unique_patterns)
        
        # Count how many minutes are covered by patterns
        covered_indices = set()
        for pattern in unique_patterns:
            covered_indices.update(range(pattern['start_index'], pattern['end_index'] + 1))
        
        coverage_percent = (len(covered_indices) / len(bars)) * 100
        
        print(f"\n" + "="*80)
        print("VERIFICATION OF HIERARCHICAL PATTERN RESOLUTION")
        print("="*80)
        print(f"Total bars in dataset: {len(bars)}")
        print(f"Bars covered by patterns: {len(covered_indices)} ({coverage_percent:.1f}%)")
        print(f"Number of non-overlapping patterns: {len(unique_patterns)}")
        print(f"Actual total price change (Last Close - First Open): {actual_total_change:.4f}")
        print(f"Sum of non-overlapping pattern changes: {pattern_total_change:.4f}")
        print("\nNote: Pattern sum won't equal total change since:")
        print("1. Not all time periods may form valid patterns")
        print("2. Gaps between patterns are not counted")
        print("3. This is the corrected methodology that prevents double-counting")
    
    def export_raw_data_csv(self, bars, symbol, start_date, end_date):
        """
        Export raw minute-by-minute data to CSV
        """
        csv_dir = f"pattern_analysis_{symbol}_{start_date}_to_{end_date}"
        os.makedirs(csv_dir, exist_ok=True)
        
        csv_filename = os.path.join(csv_dir, f"raw_{symbol}_{start_date}_to_{end_date}.csv")
        
        with open(csv_filename, 'w', newline='') as csvfile:
            fieldnames = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'vwap', 'classification']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            
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
    
    def export_pattern_csvs(self, pattern_summary, symbol, start_date, end_date):
        """
        Export CSV files for each pattern with corrected methodology
        """
        csv_dir = f"pattern_analysis_{symbol}_{start_date}_to_{end_date}"
        os.makedirs(csv_dir, exist_ok=True)
        
        exported_count = 0
        
        for pattern_str, summary in pattern_summary.items():
            if summary['count'] > 0:
                csv_filename = os.path.join(csv_dir, f"pattern_{pattern_str}_hierarchical.csv")
                
                with open(csv_filename, 'w', newline='') as csvfile:
                    fieldnames = ['start_timestamp', 'end_timestamp', 'price_change', 'volume']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    
                    writer.writeheader()
                    
                    # Sort occurrences by timestamp
                    sorted_occurrences = sorted(summary['occurrences'], 
                                               key=lambda x: x['start_time'])
                    
                    for occurrence in sorted_occurrences:
                        row = {
                            'start_timestamp': occurrence['start_time'].strftime('%Y-%m-%d %H:%M:%S'),
                            'end_timestamp': occurrence['end_time'].strftime('%Y-%m-%d %H:%M:%S'),
                            'price_change': f"{occurrence['price_change']:.4f}",
                            'volume': occurrence['volume']
                        }
                        writer.writerow(row)
                
                exported_count += 1
        
        print(f"Exported {exported_count} pattern CSV files to directory: {csv_dir}")
        return csv_dir
    
    def print_results(self, pattern_summary, unique_patterns):
        """
        Print analysis results using the corrected methodology
        """
        print("\n" + "="*100)
        print("HIERARCHICAL PATTERN ANALYSIS RESULTS (CORRECTED METHODOLOGY)")
        print("="*100)
        print("Longer patterns prioritized over shorter, overlapping ones")
        print("-" * 100)
        
        # Sort patterns for display
        sorted_patterns = sorted(pattern_summary.items(), 
                               key=lambda x: x[1]['total_profit'], reverse=True)
        
        print(f"{'Pattern':<15} {'Count':<10} {'Total Profit':<15} {'Avg Profit':<15} {'Avg Volume':<15}")
        print("-" * 75)
        
        for pattern_str, summary in sorted_patterns:
            if summary['count'] > 0:
                avg_profit = summary['total_profit'] / summary['count']
                avg_volume = summary['total_volume'] / summary['count']
                
                print(f"{pattern_str:<15} {summary['count']:<10} "
                      f"{summary['total_profit']:<15.4f} {avg_profit:<15.4f} "
                      f"{avg_volume:<15.0f}")
        
        # Summary by pattern length
        print("\n" + "="*60)
        print("SUMMARY BY PATTERN DURATION (Non-overlapping patterns only)")
        print("-" * 60)
        
        duration_stats = defaultdict(lambda: {'count': 0, 'total_profit': 0.0})
        
        for pattern in unique_patterns:
            duration = pattern['duration']
            duration_stats[duration]['count'] += 1
            duration_stats[duration]['total_profit'] += pattern['price_change']
        
        for duration in sorted(duration_stats.keys()):
            stats = duration_stats[duration]
            avg_profit = stats['total_profit'] / stats['count'] if stats['count'] > 0 else 0
            print(f"{duration}-minute patterns: {stats['count']} occurrences, "
                  f"Total profit: {stats['total_profit']:.4f}, "
                  f"Avg profit: {avg_profit:.4f}")
        
        # Most and least profitable patterns
        if sorted_patterns:
            print("\n" + "="*60)
            print("TOP 5 MOST PROFITABLE PATTERNS (By Total Profit)")
            print("-" * 60)
            
            for pattern_str, summary in sorted_patterns[:5]:
                avg_profit = summary['total_profit'] / summary['count']
                print(f"{pattern_str}: {summary['count']} occurrences, "
                      f"Total: {summary['total_profit']:.4f}, "
                      f"Avg: {avg_profit:.4f}")
            
            print("\n" + "="*60)
            print("TOP 5 LEAST PROFITABLE PATTERNS (By Total Profit)")
            print("-" * 60)
            
            # Filter for patterns with negative profits
            negative_patterns = [(p, s) for p, s in sorted_patterns if s['total_profit'] < 0]
            
            if negative_patterns:
                for pattern_str, summary in negative_patterns[-5:]:
                    avg_profit = summary['total_profit'] / summary['count']
                    print(f"{pattern_str}: {summary['count']} occurrences, "
                          f"Total: {summary['total_profit']:.4f}, "
                          f"Avg: {avg_profit:.4f}")
            else:
                print("No patterns with negative total profit found.")
    
    def run_analysis(self, symbol, start_date, end_date, durations=[5, 10, 15]):
        """
        Main method implementing the corrected hierarchical pattern resolution
        """
        print(f"Fetching data for {symbol} from {start_date} to {end_date}...")
        print(f"Using hierarchical pattern resolution with durations: {durations} minutes")
        
        # Get the minute-level data
        bars = self.get_aggs(symbol, start_date, end_date)
        
        if not bars:
            print("No data found. Trying older dates...")
            older_end = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            older_start = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
            print(f"Trying date range: {older_start} to {older_end}")
            bars = self.get_aggs(symbol, older_start, older_end)
            
            if bars:
                start_date = older_start
                end_date = older_end
        
        if not bars:
            print("No data available for analysis.")
            return
        
        print(f"Retrieved {len(bars)} minute bars")
        
        # Export raw data
        self.export_raw_data_csv(bars, symbol, start_date, end_date)
        
        # Step 1: Identify all possible patterns
        print("\nStep 1: Identifying all possible patterns...")
        all_patterns = self.identify_all_patterns(bars, durations)
        print(f"Found {len(all_patterns)} total patterns (with overlaps)")
        
        # Steps 2 & 3: Resolve overlaps using hierarchical method
        print("\nSteps 2 & 3: Applying hierarchical resolution...")
        unique_patterns = self.resolve_overlaps(all_patterns)
        print(f"Resolved to {len(unique_patterns)} non-overlapping patterns")
        
        # Step 4: Aggregate results
        print("\nStep 4: Aggregating pattern statistics...")
        pattern_summary = self.aggregate_patterns(unique_patterns)
        
        # Verify the results
        self.verify_total_change(bars, unique_patterns)
        
        # Print results
        self.print_results(pattern_summary, unique_patterns)
        
        # Export pattern CSVs
        self.export_pattern_csvs(pattern_summary, symbol, start_date, end_date)
        
        print("\n" + "="*80)
        print("ANALYSIS COMPLETE - Using Corrected Hierarchical Methodology")
        print("="*80)
        
        return pattern_summary, unique_patterns

def main():
    # Configuration
    API_KEY = "Z_ENWpm0RRrvXvLOY65uMH8RB93B4gBN"  # Your API key
    SYMBOL = "GLD"  # Stock symbol to analyze
    
    # Pattern durations to analyze (as per document recommendation)
    DURATIONS = [5, 10, 15]  # minutes
    
    # Use historical dates
    end_date = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    
    print(f"Using date range: {start_date} to {end_date}")
    print(f"Analyzing patterns of durations: {DURATIONS} minutes")
    print("="*80)
    
    # Create analyzer instance
    analyzer = PolygonPatternAnalyzer(API_KEY)
    
    # Run the corrected analysis
    analyzer.run_analysis(SYMBOL, start_date, end_date, DURATIONS)

if __name__ == "__main__":
    main()