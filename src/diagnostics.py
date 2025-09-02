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
    
    def chunk_and_bucket_patterns(self, bars, offset=0):
        """
        Process data in non-overlapping 5-minute chunks with gap adjusters
        offset: number of bars to skip at the beginning
        """
        pattern_buckets = defaultdict(lambda: {
            'occurrences': [],
            'total_change': 0.0,
            'total_internal_change': 0.0,
            'total_gap_adjustment': 0.0,
            'count': 0,
            'total_volume': 0
        })
        
        # Track all processed chunks for verification
        all_chunks = []
        
        # Start from offset
        bars_to_process = bars[offset:]
        
        # Process in chunks of 5
        chunk_size = 5
        i = 0
        
        while i + chunk_size <= len(bars_to_process):
            # Extract exactly 5 consecutive bars
            chunk_bars = bars_to_process[i:i + chunk_size]
            
            # Build pattern string for this chunk
            pattern_string = ''.join([self.classify_bar(bar) for bar in chunk_bars])
            
            # Calculate internal price change for this chunk
            chunk_open = chunk_bars[0]['o']
            chunk_close = chunk_bars[-1]['c']
            internal_change = chunk_close - chunk_open
            
            # Calculate gap adjuster (if there's a next chunk)
            gap_adjuster = 0.0
            next_chunk_open = None
            if i + chunk_size < len(bars_to_process):
                next_chunk_open = bars_to_process[i + chunk_size]['o']
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
        
        # Calculate actual total change for processed data
        if bars_to_process:
            first_open = bars_to_process[0]['o']
            last_close = bars_to_process[-1]['c']
            actual_total_change = last_close - first_open
        else:
            actual_total_change = 0.0
        
        return pattern_buckets, all_chunks, actual_total_change
    
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
    
    def export_diagnostic_summary(self, pattern_buckets, actual_total_change, offset, 
                                 symbol, start_date, end_date, csv_dir):
        """
        Export summary file for a specific offset in diagnostic mode
        """
        summary_filename = os.path.join(csv_dir, f"summary_{offset}_offset.csv")
        
        with open(summary_filename, 'w', newline='') as csvfile:
            fieldnames = ['pattern', 'occurrences', 'total_change', 'avg_total_change', 
                         'avg_internal_change', 'avg_gap_adjustment', 'avg_volume', 
                         'std_dev', 'consistency', 'actual_data_total_change']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            
            for pattern, bucket in sorted(pattern_buckets.items(), 
                                         key=lambda x: x[1]['total_change'], reverse=True):
                if bucket['count'] > 0:
                    row = {
                        'pattern': pattern,
                        'occurrences': bucket['count'],
                        'total_change': f"{bucket['total_change']:.4f}",
                        'avg_total_change': f"{bucket.get('avg_total_change', 0):.4f}",
                        'avg_internal_change': f"{bucket.get('avg_internal_change', 0):.4f}",
                        'avg_gap_adjustment': f"{bucket.get('avg_gap_adjustment', 0):.4f}",
                        'avg_volume': f"{bucket.get('avg_volume', 0):.0f}",
                        'std_dev': f"{bucket.get('std_dev', 0):.4f}",
                        'consistency': f"{bucket.get('consistency', 0):.4f}",
                        'actual_data_total_change': f"{actual_total_change:.4f}"
                    }
                    writer.writerow(row)
        
        print(f"  Exported: {summary_filename}")
        return summary_filename
    
    def export_raw_data_csv(self, bars, symbol, start_date, end_date):
        """
        Export raw minute-by-minute data to CSV
        """
        csv_dir = f"diagnostic_{symbol}_{start_date}_to_{end_date}"
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
        return csv_dir
    
    def print_diagnostic_results(self, all_results):
        """
        Print comparison of results across different offsets
        """
        print("\n" + "="*120)
        print("DIAGNOSTIC ANALYSIS SUMMARY - COMPARING 5 DIFFERENT STARTING OFFSETS")
        print("="*120)
        
        # Collect all unique patterns across all offsets
        all_patterns = set()
        for offset_data in all_results:
            all_patterns.update(offset_data['buckets'].keys())
        
        # Print pattern occurrence comparison
        print("\nPATTERN OCCURRENCE COMPARISON ACROSS OFFSETS:")
        print("-" * 80)
        print(f"{'Pattern':<10}", end="")
        for i in range(5):
            print(f"{'Offset ' + str(i):<12}", end="")
        print(f"{'Avg':<10} {'StdDev':<10}")
        print("-" * 80)
        
        for pattern in sorted(all_patterns):
            print(f"{pattern:<10}", end="")
            counts = []
            for offset_data in all_results:
                count = offset_data['buckets'].get(pattern, {}).get('count', 0)
                counts.append(count)
                print(f"{count:<12}", end="")
            
            # Calculate average and std dev
            if counts:
                avg = sum(counts) / len(counts)
                if len(counts) > 1:
                    variance = sum((c - avg) ** 2 for c in counts) / len(counts)
                    std_dev = variance ** 0.5
                else:
                    std_dev = 0
                print(f"{avg:<10.1f} {std_dev:<10.2f}")
            else:
                print()
        
        # Print total change comparison
        print("\n" + "="*80)
        print("ACTUAL TOTAL CHANGE BY OFFSET:")
        print("-" * 80)
        for i, offset_data in enumerate(all_results):
            bars_analyzed = offset_data['bars_count']
            chunks_formed = sum(b['count'] for b in offset_data['buckets'].values())
            print(f"Offset {i}: ${offset_data['actual_total']:.4f} "
                  f"({bars_analyzed} bars, {chunks_formed} chunks)")
        
        # Print pattern profitability stability
        print("\n" + "="*80)
        print("PATTERN AVERAGE PROFITABILITY STABILITY:")
        print("-" * 80)
        print(f"{'Pattern':<10} {'Min Avg':<12} {'Max Avg':<12} {'Range':<10} {'Stable?':<10}")
        print("-" * 80)
        
        for pattern in sorted(all_patterns):
            avg_changes = []
            for offset_data in all_results:
                bucket = offset_data['buckets'].get(pattern, {})
                if bucket.get('count', 0) > 0:
                    avg_changes.append(bucket.get('avg_total_change', 0))
            
            if avg_changes:
                min_avg = min(avg_changes)
                max_avg = max(avg_changes)
                range_val = max_avg - min_avg
                stable = "Yes" if range_val < 0.1 else "No"
                print(f"{pattern:<10} ${min_avg:<11.4f} ${max_avg:<11.4f} "
                      f"${range_val:<9.4f} {stable:<10}")
    
    def run_diagnostic_analysis(self, symbol, start_date, end_date):
        """
        Run diagnostic mode - analyze with 5 different offsets (0-4 bars removed)
        """
        print(f"DIAGNOSTIC MODE - Analyzing {symbol} from {start_date} to {end_date}")
        print("Will create 5 summary files with different starting offsets (0-4 bars removed)")
        print("="*80)
        
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
        
        # Export raw data and create directory
        csv_dir = self.export_raw_data_csv(bars, symbol, start_date, end_date)
        
        # Store results from all offsets for comparison
        all_results = []
        
        # Run analysis with 5 different offsets
        print("\nRunning diagnostic analysis with 5 offsets:")
        print("-" * 50)
        
        for offset in range(5):
            print(f"\nOffset {offset}: Removing first {offset} bars...")
            
            # Process with current offset
            pattern_buckets, all_chunks, actual_total_change = self.chunk_and_bucket_patterns(bars, offset)
            
            # Calculate statistics
            self.calculate_statistics(pattern_buckets)
            
            # Export summary for this offset
            self.export_diagnostic_summary(pattern_buckets, actual_total_change, 
                                          offset, symbol, start_date, end_date, csv_dir)
            
            # Store results for comparison
            all_results.append({
                'offset': offset,
                'buckets': pattern_buckets,
                'chunks': all_chunks,
                'actual_total': actual_total_change,
                'bars_count': len(bars) - offset
            })
            
            # Print quick stats
            total_chunks = sum(b['count'] for b in pattern_buckets.values())
            pattern_sum = sum(b['total_change'] for b in pattern_buckets.values())
            patterns_found = len([p for p in pattern_buckets.values() if p['count'] > 0])
            
            print(f"  Bars processed: {len(bars) - offset}")
            print(f"  Chunks formed: {total_chunks}")
            print(f"  Unique patterns: {patterns_found}")
            print(f"  Actual total change: ${actual_total_change:.4f}")
            print(f"  Sum of pattern changes: ${pattern_sum:.4f}")
            
            diff = abs(actual_total_change - pattern_sum)
            if diff < 0.0001:
                print(f"  ✓ Verification PASSED")
            else:
                print(f"  ⚠ Verification difference: ${diff:.6f}")
        
        # Print comparative analysis
        self.print_diagnostic_results(all_results)
        
        # Export comparison summary
        comparison_filename = os.path.join(csv_dir, "diagnostic_comparison.csv")
        with open(comparison_filename, 'w', newline='') as csvfile:
            fieldnames = ['offset', 'bars_processed', 'chunks_formed', 'unique_patterns', 
                         'actual_total_change', 'pattern_sum', 'verification_diff']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            
            for result in all_results:
                total_chunks = sum(b['count'] for b in result['buckets'].values())
                pattern_sum = sum(b['total_change'] for b in result['buckets'].values())
                patterns_found = len([p for p in result['buckets'].values() if p['count'] > 0])
                
                row = {
                    'offset': result['offset'],
                    'bars_processed': result['bars_count'],
                    'chunks_formed': total_chunks,
                    'unique_patterns': patterns_found,
                    'actual_total_change': f"{result['actual_total']:.4f}",
                    'pattern_sum': f"{pattern_sum:.4f}",
                    'verification_diff': f"{abs(result['actual_total'] - pattern_sum):.6f}"
                }
                writer.writerow(row)
        
        print(f"\nExported comparison summary to: {comparison_filename}")
        
        print("\n" + "="*80)
        print("DIAGNOSTIC ANALYSIS COMPLETE")
        print(f"All files saved to: {csv_dir}")
        print("="*80)
        
        return all_results

def main():
    # Configuration
    API_KEY = "Z_ENWpm0RRrvXvLOY65uMH8RB93B4gBN"  # Your API key
    SYMBOL = "SPY"  # Stock symbol to analyze
    
    # Use historical dates
    end_date = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=93)).strftime("%Y-%m-%d")
    
    print("="*80)
    print("DIAGNOSTIC MODE - 5-MINUTE BUCKET PATTERN ANALYSIS")
    print("="*80)
    print(f"Symbol: {SYMBOL}")
    print(f"Date range: {start_date} to {end_date}")
    print("Creating 5 summary files with offsets 0-4")
    print("="*80)
    
    # Create analyzer instance
    analyzer = PolygonPatternAnalyzer(API_KEY)
    
    # Run diagnostic analysis
    analyzer.run_diagnostic_analysis(SYMBOL, start_date, end_date)

if __name__ == "__main__":
    main()