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
    
    def chunk_and_bucket_patterns(self, bars):
        """
        Process data in non-overlapping 5-minute chunks with gap adjusters
        Each chunk's total change = (close - open) + gap_adjuster
        Where gap_adjuster = (next_chunk_open - current_chunk_close)
        """
        pattern_buckets = defaultdict(lambda: {
            'occurrences': [],
            'total_change': 0.0,
            'total_internal_change': 0.0,  # Close - Open within bucket
            'total_gap_adjustment': 0.0,   # Gap adjustments
            'count': 0,
            'total_volume': 0
        })
        
        # Track all processed chunks for verification
        all_chunks = []
        
        # Process in chunks of 5
        chunk_size = 5
        i = 0
        
        while i + chunk_size <= len(bars):
            # Extract exactly 5 consecutive bars
            chunk_bars = bars[i:i + chunk_size]
            
            # Build pattern string for this chunk
            pattern_string = ''.join([self.classify_bar(bar) for bar in chunk_bars])
            
            # Calculate internal price change for this chunk
            chunk_open = chunk_bars[0]['o']
            chunk_close = chunk_bars[-1]['c']
            internal_change = chunk_close - chunk_open
            
            # Calculate gap adjuster (if there's a next chunk)
            gap_adjuster = 0.0
            next_chunk_open = None
            if i + chunk_size < len(bars):
                next_chunk_open = bars[i + chunk_size]['o']
                gap_adjuster = next_chunk_open - chunk_close
            
            # Total change for this chunk
            total_chunk_change = internal_change + gap_adjuster
            
            # Get timestamps
            start_timestamp = datetime.fromtimestamp(chunk_bars[0]['t'] / 1000)
            end_timestamp = datetime.fromtimestamp(chunk_bars[-1]['t'] / 1000)
            
            # Calculate total volume for the chunk
            total_volume = sum(bar['v'] for bar in chunk_bars)
            
            # Add to the appropriate bucket
            bucket = pattern_buckets[pattern_string]
            bucket['count'] += 1
            bucket['total_change'] += total_chunk_change
            bucket['total_internal_change'] += internal_change
            bucket['total_gap_adjustment'] += gap_adjuster
            bucket['total_volume'] += total_volume
            bucket['occurrences'].append({
                'start_time': start_timestamp,
                'end_time': end_timestamp,
                'chunk_open': chunk_open,
                'chunk_close': chunk_close,
                'internal_change': internal_change,
                'gap_adjuster': gap_adjuster,
                'total_change': total_chunk_change,
                'next_chunk_open': next_chunk_open,
                'volume': total_volume,
                'chunk_index': i // chunk_size
            })
            
            # Track this chunk for verification
            all_chunks.append({
                'pattern': pattern_string,
                'start_index': i,
                'end_index': i + chunk_size - 1,
                'internal_change': internal_change,
                'gap_adjuster': gap_adjuster,
                'total_change': total_chunk_change
            })
            
            # Move to next non-overlapping chunk
            i += chunk_size
        
        # Handle remaining bars (if any)
        remaining_bars = len(bars) - i
        if remaining_bars > 0:
            print(f"\nNote: {remaining_bars} bars at the end not included (need exactly 5 bars for a pattern)")
        
        return pattern_buckets, all_chunks
    
    def verify_cumulative_change(self, bars, pattern_buckets, all_chunks):
        """
        Verify that sum of all pattern changes (including gap adjusters) 
        equals actual price change for the processed portion
        """
        if not bars or not all_chunks:
            return
        
        # Calculate the actual price change
        last_processed_index = all_chunks[-1]['end_index']
        first_processed_index = all_chunks[0]['start_index']
        
        actual_start_price = bars[first_processed_index]['o']
        actual_end_price = bars[last_processed_index]['c']
        
        # If there's another bar after the last chunk, include the gap to it
        if last_processed_index + 1 < len(bars):
            next_bar_open = bars[last_processed_index + 1]['o']
            actual_total_change = (actual_end_price - actual_start_price) + (next_bar_open - actual_end_price)
        else:
            actual_total_change = actual_end_price - actual_start_price
        
        # Sum all pattern bucket changes (includes gap adjusters)
        pattern_sum = sum(bucket['total_change'] for bucket in pattern_buckets.values())
        
        # Break down the components
        internal_sum = sum(bucket['total_internal_change'] for bucket in pattern_buckets.values())
        gap_sum = sum(bucket['total_gap_adjustment'] for bucket in pattern_buckets.values())
        
        print("\n" + "="*80)
        print("VERIFICATION OF CUMULATIVE PRICE CHANGES (WITH GAP ADJUSTERS)")
        print("="*80)
        print(f"Processed bars: {first_processed_index} to {last_processed_index}")
        print(f"Total complete 5-minute chunks: {len(all_chunks)}")
        print(f"Bars processed: {len(all_chunks) * 5} out of {len(bars)} total bars")
        print("-" * 80)
        print(f"First processed bar: Open = ${actual_start_price:.4f}")
        print(f"Last processed bar:  Close = ${actual_end_price:.4f}")
        print(f"Basic price change (Last Close - First Open): ${actual_end_price - actual_start_price:.4f}")
        print("-" * 80)
        print("COMPONENT BREAKDOWN:")
        print(f"Sum of internal changes (close - open within chunks): ${internal_sum:.4f}")
        print(f"Sum of gap adjustments (between chunks): ${gap_sum:.4f}")
        print(f"Total (internal + gaps): ${pattern_sum:.4f}")
        print("-" * 80)
        print(f"Actual total change to account for: ${actual_total_change:.4f}")
        print(f"Sum of all pattern bucket changes: ${pattern_sum:.4f}")
        print(f"Difference: ${abs(actual_total_change - pattern_sum):.6f}")
        
        if abs(actual_total_change - pattern_sum) < 0.0001:
            print("✓ VERIFICATION PASSED: Cumulative changes match perfectly!")
        else:
            print("✗ VERIFICATION WARNING: Small discrepancy (likely from last chunk having no gap)")
        
        # Show pattern breakdown with gap adjustments
        print("\n" + "="*80)
        print("PATTERN CONTRIBUTION TO TOTAL CHANGE (INCLUDING GAPS)")
        print("-" * 80)
        for pattern, bucket in sorted(pattern_buckets.items(), 
                                     key=lambda x: x[1]['total_change'], reverse=True):
            if actual_total_change != 0:
                percentage = (bucket['total_change'] / actual_total_change * 100)
            else:
                percentage = 0
            
            avg_internal = bucket['total_internal_change'] / bucket['count'] if bucket['count'] > 0 else 0
            avg_gap = bucket['total_gap_adjustment'] / bucket['count'] if bucket['count'] > 0 else 0
            avg_total = bucket['total_change'] / bucket['count'] if bucket['count'] > 0 else 0
            
            print(f"{pattern}: {bucket['count']:3d} chunks")
            print(f"  Internal: ${avg_internal:7.4f} × {bucket['count']} = ${bucket['total_internal_change']:8.4f}")
            print(f"  Gaps:     ${avg_gap:7.4f} × {bucket['count']} = ${bucket['total_gap_adjustment']:8.4f}")
            print(f"  Total:    ${avg_total:7.4f} × {bucket['count']} = ${bucket['total_change']:8.4f} ({percentage:6.2f}%)")
            print()
    
    def calculate_statistics(self, pattern_buckets):
        """
        Calculate statistics for each pattern bucket
        """
        for pattern, bucket in pattern_buckets.items():
            if bucket['count'] > 0:
                bucket['avg_total_change'] = bucket['total_change'] / bucket['count']
                bucket['avg_internal_change'] = bucket['total_internal_change'] / bucket['count']
                bucket['avg_gap_adjustment'] = bucket['total_gap_adjustment'] / bucket['count']
                bucket['avg_volume'] = bucket['total_volume'] / bucket['count']
                
                # Calculate consistency based on total changes
                total_changes = [occ['total_change'] for occ in bucket['occurrences']]
                if len(total_changes) > 1:
                    mean_change = sum(total_changes) / len(total_changes)
                    variance = sum((c - mean_change) ** 2 for c in total_changes) / len(total_changes)
                    bucket['std_dev'] = variance ** 0.5
                    bucket['consistency'] = 1 / (1 + bucket['std_dev']) if bucket['std_dev'] > 0 else 1
                else:
                    bucket['std_dev'] = 0
                    bucket['consistency'] = 1
    
    def export_raw_data_csv(self, bars, symbol, start_date, end_date):
        """
        Export raw minute-by-minute data to CSV
        """
        csv_dir = f"bucket_gap_analysis_{symbol}_{start_date}_to_{end_date}"
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
        
        print(f"\nExported raw data to: {csv_filename}")
        return csv_filename
    
    def export_pattern_files(self, pattern_buckets, symbol, start_date, end_date):
        """
        Export individual CSV files for each pattern bucket with gap adjusters
        """
        csv_dir = f"bucket_gap_analysis_{symbol}_{start_date}_to_{end_date}"
        os.makedirs(csv_dir, exist_ok=True)
        
        exported_count = 0
        
        # Export individual pattern files
        for pattern, bucket in pattern_buckets.items():
            if bucket['count'] > 0:
                csv_filename = os.path.join(csv_dir, f"pattern_{pattern}.csv")
                
                with open(csv_filename, 'w', newline='') as csvfile:
                    fieldnames = ['timestamp', 'total_price_change']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    
                    writer.writeheader()
                    
                    # Sort by timestamp
                    sorted_occurrences = sorted(bucket['occurrences'], 
                                               key=lambda x: x['start_time'])
                    
                    for occurrence in sorted_occurrences:
                        row = {
                            'timestamp': occurrence['start_time'].strftime('%Y-%m-%d %H:%M:%S'),
                            'total_price_change': f"{occurrence['total_change']:.4f}"
                        }
                        writer.writerow(row)
                
                # Also export detailed file with breakdown
                detailed_filename = os.path.join(csv_dir, f"pattern_{pattern}_detailed.csv")
                with open(detailed_filename, 'w', newline='') as csvfile:
                    fieldnames = ['timestamp', 'chunk_open', 'chunk_close', 'internal_change', 
                                'gap_adjuster', 'total_change', 'volume']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    
                    writer.writeheader()
                    
                    for occurrence in sorted_occurrences:
                        row = {
                            'timestamp': occurrence['start_time'].strftime('%Y-%m-%d %H:%M:%S'),
                            'chunk_open': f"{occurrence['chunk_open']:.4f}",
                            'chunk_close': f"{occurrence['chunk_close']:.4f}",
                            'internal_change': f"{occurrence['internal_change']:.4f}",
                            'gap_adjuster': f"{occurrence['gap_adjuster']:.4f}",
                            'total_change': f"{occurrence['total_change']:.4f}",
                            'volume': occurrence['volume']
                        }
                        writer.writerow(row)
                
                exported_count += 1
        
        # Export summary file
        summary_filename = os.path.join(csv_dir, "pattern_summary.csv")
        with open(summary_filename, 'w', newline='') as csvfile:
            fieldnames = ['pattern', 'occurrences', 'total_change', 'avg_total_change', 
                         'avg_internal_change', 'avg_gap_adjustment', 'avg_volume', 
                         'std_dev', 'consistency']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            
            for pattern, bucket in sorted(pattern_buckets.items(), 
                                         key=lambda x: x[1]['total_change'], reverse=True):
                row = {
                    'pattern': pattern,
                    'occurrences': bucket['count'],
                    'total_change': f"{bucket['total_change']:.4f}",
                    'avg_total_change': f"{bucket.get('avg_total_change', 0):.4f}",
                    'avg_internal_change': f"{bucket.get('avg_internal_change', 0):.4f}",
                    'avg_gap_adjustment': f"{bucket.get('avg_gap_adjustment', 0):.4f}",
                    'avg_volume': f"{bucket.get('avg_volume', 0):.0f}",
                    'std_dev': f"{bucket.get('std_dev', 0):.4f}",
                    'consistency': f"{bucket.get('consistency', 0):.4f}"
                }
                writer.writerow(row)
        
        print(f"Exported {exported_count} pattern CSV files (with detailed breakdowns) to: {csv_dir}")
        print(f"Exported summary to: {summary_filename}")
        return csv_dir
    
    def print_results(self, pattern_buckets):
        """
        Print analysis results with gap adjusters
        """
        print("\n" + "="*130)
        print("5-MINUTE BUCKET ANALYSIS WITH GAP ADJUSTERS")
        print("="*130)
        print("Total Change = (Close - Open) within bucket + Gap to next bucket")
        print("-" * 130)
        
        # Sort by total change
        sorted_patterns = sorted(pattern_buckets.items(), 
                               key=lambda x: x[1]['total_change'], reverse=True)
        
        print(f"{'Pattern':<10} {'Count':<8} {'Total Change':<14} {'Avg Total':<12} "
              f"{'Avg Internal':<14} {'Avg Gap':<10} {'Consistency':<12}")
        print("-" * 110)
        
        for pattern, bucket in sorted_patterns:
            if bucket['count'] > 0:
                print(f"{pattern:<10} {bucket['count']:<8} ${bucket['total_change']:<13.4f} "
                      f"${bucket.get('avg_total_change', 0):<11.4f} "
                      f"${bucket.get('avg_internal_change', 0):<13.4f} "
                      f"${bucket.get('avg_gap_adjustment', 0):<9.4f} "
                      f"{bucket.get('consistency', 0):<12.4f}")
        
        # Summary statistics
        total_chunks = sum(b['count'] for b in pattern_buckets.values())
        total_change = sum(b['total_change'] for b in pattern_buckets.values())
        total_internal = sum(b['total_internal_change'] for b in pattern_buckets.values())
        total_gaps = sum(b['total_gap_adjustment'] for b in pattern_buckets.values())
        patterns_found = len([p for p in pattern_buckets.values() if p['count'] > 0])
        
        print("-" * 110)
        print(f"Total 5-minute chunks analyzed: {total_chunks}")
        print(f"Unique patterns found: {patterns_found} out of 32 possible")
        print(f"Total internal change (within buckets): ${total_internal:.4f}")
        print(f"Total gap adjustments (between buckets): ${total_gaps:.4f}")
        print(f"Total cumulative price change: ${total_change:.4f}")
        
        # Best and worst patterns
        if sorted_patterns:
            print("\n" + "="*60)
            print("TOP 5 MOST PROFITABLE PATTERNS (INCLUDING GAPS)")
            print("-" * 60)
            
            for pattern, bucket in sorted_patterns[:5]:
                if bucket['count'] > 0:
                    print(f"{pattern}: {bucket['count']} occurrences")
                    print(f"  Total: ${bucket['total_change']:.4f}")
                    print(f"  Avg Total: ${bucket.get('avg_total_change', 0):.4f} "
                          f"(Internal: ${bucket.get('avg_internal_change', 0):.4f}, "
                          f"Gap: ${bucket.get('avg_gap_adjustment', 0):.4f})")
            
            print("\n" + "="*60)
            print("PATTERNS WITH LARGEST GAP ADJUSTMENTS")
            print("-" * 60)
            
            by_gap = sorted(pattern_buckets.items(), 
                          key=lambda x: abs(x[1].get('avg_gap_adjustment', 0)), reverse=True)
            
            for pattern, bucket in by_gap[:5]:
                if bucket['count'] > 0:
                    print(f"{pattern}: Avg gap adjustment: ${bucket.get('avg_gap_adjustment', 0):.4f} "
                          f"({bucket['count']} occurrences)")
    
    def run_analysis(self, symbol, start_date, end_date):
        """
        Main method to run bucket-based pattern analysis with gap adjusters
        """
        print(f"Fetching data for {symbol} from {start_date} to {end_date}...")
        print("Using non-overlapping 5-minute chunks with gap adjusters")
        
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
        
        # Process data in non-overlapping chunks with gap adjusters
        print("\nProcessing data in non-overlapping 5-minute chunks with gap adjusters...")
        pattern_buckets, all_chunks = self.chunk_and_bucket_patterns(bars)
        
        # Calculate statistics
        self.calculate_statistics(pattern_buckets)
        
        # Verify cumulative changes
        self.verify_cumulative_change(bars, pattern_buckets, all_chunks)
        
        # Print results
        self.print_results(pattern_buckets)
        
        # Export pattern files
        self.export_pattern_files(pattern_buckets, symbol, start_date, end_date)
        
        print("\n" + "="*80)
        print("ANALYSIS COMPLETE - With gap adjusters")
        print("Each chunk accounts for internal change + gap to next chunk")
        print("="*80)
        
        return pattern_buckets

def main():
    # Configuration
    API_KEY = "Z_ENWpm0RRrvXvLOY65uMH8RB93B4gBN"  # Your API key
    SYMBOL = "GLD"  # Stock symbol to analyze
    
    # Use historical dates
    end_date = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    
    print("="*80)
    print("5-MINUTE BUCKET PATTERN ANALYSIS WITH GAP ADJUSTERS")
    print("="*80)
    print(f"Symbol: {SYMBOL}")
    print(f"Date range: {start_date} to {end_date}")
    print("Method: Non-overlapping chunks with gap accounting")
    print("="*80)
    
    # Create analyzer instance
    analyzer = PolygonPatternAnalyzer(API_KEY)
    
    # Run the analysis
    analyzer.run_analysis(SYMBOL, start_date, end_date)

if __name__ == "__main__":
    main()