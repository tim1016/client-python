import requests
import json
from datetime import datetime, timedelta
from collections import defaultdict
import csv
import os
import numpy as np
import pandas as pd

class ThreeMinutePatternAnalyzer:
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
                print("Note: Using delayed data access.")
                print("Attempting to retrieve available data...")
                return data.get('results', [])
            else:
                print(f"API Status: {data.get('status')}")
                if data.get('error'):
                    print(f"API Error: {data.get('error')}")
                if data.get('message'):
                    print(f"API Message: {data.get('message')}")
                
                if 'results' in data and data['results']:
                    print(f"Found {len(data['results'])} bars despite API status")
                    return data['results']
                return []
                    
        except requests.exceptions.RequestException as e:
            print(f"Network Error: {str(e)}")
            return []
    
    def save_raw_data(self, bars, symbol, start_date, end_date):
        """
        Save raw data to CSV
        """
        csv_dir = f"3min_analysis_{symbol}_{start_date}_to_{end_date}"
        os.makedirs(csv_dir, exist_ok=True)
        
        csv_filename = os.path.join(csv_dir, f"raw_{symbol}_{start_date}_to_{end_date}.csv")
        
        with open(csv_filename, 'w', newline='') as csvfile:
            fieldnames = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'vwap', 'trades', 'symbol']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            
            for bar in bars:
                timestamp = datetime.fromtimestamp(bar['t'] / 1000)
                
                row = {
                    'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'open': f"{bar['o']:.4f}",
                    'high': f"{bar['h']:.4f}",
                    'low': f"{bar['l']:.4f}",
                    'close': f"{bar['c']:.4f}",
                    'volume': bar['v'],
                    'vwap': f"{bar.get('vw', 0):.4f}",
                    'trades': bar.get('n', 0),
                    'symbol': symbol
                }
                writer.writerow(row)
        
        print(f"\n✓ Saved raw data to: {csv_filename}")
        return csv_filename, csv_dir
    
    def clean_data(self, bars, symbol, csv_dir):
        """
        Clean data and generate cleanup summary
        """
        print("\n" + "="*80)
        print("DATA CLEANING PROCESS")
        print("="*80)
        
        cleanup_summary = {
            'total_bars': len(bars),
            'removed_bars': 0,
            'gap_minutes': 0,
            'outliers_removed': 0,
            'zero_volume_bars': 0,
            'duplicate_timestamps': 0,
            'pre_post_market_removed': 0,
            'cleaned_bars': 0
        }
        
        if not bars:
            return [], cleanup_summary
        
        # Convert to DataFrame for easier manipulation
        df_data = []
        for bar in bars:
            df_data.append({
                't': bar['t'],
                'o': bar['o'],
                'h': bar['h'],
                'l': bar['l'],
                'c': bar['c'],
                'v': bar['v'],
                'vw': bar.get('vw', 0),
                'n': bar.get('n', 0)
            })
        
        df = pd.DataFrame(df_data)
        df['timestamp'] = pd.to_datetime(df['t'], unit='ms')
        df = df.sort_values('timestamp')
        
        original_count = len(df)
        
        # 1. Remove duplicate timestamps
        duplicates = df.duplicated(subset=['timestamp'])
        cleanup_summary['duplicate_timestamps'] = duplicates.sum()
        df = df[~duplicates]
        
        # 2. Remove zero volume bars
        zero_volume = df['v'] == 0
        cleanup_summary['zero_volume_bars'] = zero_volume.sum()
        df = df[~zero_volume]
        
        # 3. Detect and log time gaps
        df['time_diff'] = df['timestamp'].diff()
        gaps = df[df['time_diff'] > pd.Timedelta(minutes=1)]
        cleanup_summary['gap_minutes'] = len(gaps)
        
        # 4. Remove outliers
        window_size = min(60, len(df) // 10) if len(df) > 10 else len(df)
        if window_size > 1:
            df['rolling_mean'] = df['c'].rolling(window=window_size, center=True).mean()
            df['rolling_mean'] = df['rolling_mean'].fillna(df['c'])
            df['price_deviation'] = abs(df['c'] - df['rolling_mean']) / df['rolling_mean']
            outliers = df['price_deviation'] > 0.1
            cleanup_summary['outliers_removed'] = outliers.sum()
            df = df[~outliers]
            df = df.drop(['rolling_mean', 'price_deviation'], axis=1)
        
        # Convert back to list of dicts
        cleaned_bars = df.to_dict('records')
        cleanup_summary['cleaned_bars'] = len(cleaned_bars)
        cleanup_summary['removed_bars'] = original_count - len(cleaned_bars)
        
        # Save cleanup summary
        summary_file = os.path.join(csv_dir, "cleanup_summary.txt")
        with open(summary_file, 'w') as f:
            f.write("DATA CLEANUP SUMMARY\n")
            f.write("="*50 + "\n")
            f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Symbol: {symbol}\n\n")
            f.write("Cleanup Statistics:\n")
            f.write("-"*30 + "\n")
            f.write(f"Original bars: {cleanup_summary['total_bars']}\n")
            f.write(f"Duplicate timestamps removed: {cleanup_summary['duplicate_timestamps']}\n")
            f.write(f"Zero volume bars removed: {cleanup_summary['zero_volume_bars']}\n")
            f.write(f"Pre/Post market bars removed: {cleanup_summary['pre_post_market_removed']}\n")
            f.write(f"Outliers removed: {cleanup_summary['outliers_removed']}\n")
            f.write(f"Time gaps detected (>1min) in market hours: {cleanup_summary['gap_minutes']}\n")
            f.write(f"Total bars removed: {cleanup_summary['removed_bars']}\n")
            f.write(f"Final cleaned bars: {cleanup_summary['cleaned_bars']}\n")
            f.write(f"Data quality score: {(cleanup_summary['cleaned_bars']/cleanup_summary['total_bars']*100):.2f}%\n")
            
            if cleanup_summary['gap_minutes'] > 0:
                f.write("\nRemaining Time Gaps (in market hours):\n")
                f.write("-"*30 + "\n")
                for _, gap_row in gaps.iterrows():
                    f.write(f"Gap at {gap_row['timestamp']}: {gap_row['time_diff'].total_seconds()/60:.1f} minutes\n")
        
        print(f"✓ Cleanup summary saved to: {summary_file}")
        
        # Print summary to console
        print("\nCleanup Results:")
        print("-"*30)
        print(f"Original bars: {cleanup_summary['total_bars']}")
        print(f"Pre/Post market removed: {cleanup_summary['pre_post_market_removed']}")
        print(f"Cleaned bars: {cleanup_summary['cleaned_bars']}")
        print(f"Removed: {cleanup_summary['removed_bars']} ({cleanup_summary['removed_bars']/cleanup_summary['total_bars']*100:.2f}%)")
        print(f"Remaining gaps in market hours: {cleanup_summary['gap_minutes']}")
        
        # Save cleaned data
        cleaned_file = os.path.join(csv_dir, f"cleaned_{symbol}.csv")
        df_clean = pd.DataFrame(cleaned_bars)
        df_clean['timestamp'] = pd.to_datetime(df_clean['t'], unit='ms')
        df_clean[['timestamp', 'o', 'h', 'l', 'c', 'v']].to_csv(cleaned_file, index=False)
        print(f"✓ Cleaned data saved to: {cleaned_file}")
        
        return cleaned_bars, cleanup_summary
    
    def classify_candle(self, current_bar, next_bar):
        """
        Classify candle based on open-to-open price change
        P: Positive (next open > current open)
        N: Negative (next open < current open)  
        O: Zero (next open = current open)
        """
        if next_bar is None:
            return 'O'
            
        current_open = current_bar['o']
        next_open = next_bar['o']
        
        price_change = next_open - current_open
        
        # Use small threshold for floating point comparison
        threshold = 0.0001
        
        if price_change > threshold:
            return 'P'
        elif price_change < -threshold:
            return 'N'
        else:
            return 'O'
    
    def process_patterns_3min(self, bars, offset=0, csv_dir=None, symbol=None):
        """
        Process data in 3-minute chunks with specified offset
        """
        pattern_buckets = defaultdict(lambda: {
            'occurrences': [],
            'total_change': 0.0,
            'count': 0,
            'total_volume': 0,
            'individual_changes': []
        })
        
        chunk_size = 3
        total_possible_patterns = 3 ** chunk_size  # 27 patterns
        
        print(f"\nProcessing 3-minute patterns with offset {offset}...")
        print(f"Total possible patterns: {total_possible_patterns} (3^3)")
        
        # Create pattern occurrences CSV file for this offset
        if csv_dir:
            occurrences_file = os.path.join(csv_dir, f"pattern_occurrences_offset_{offset}.csv")
            occ_file = open(occurrences_file, 'w', newline='')
            occ_writer = csv.DictWriter(occ_file, fieldnames=[
                'pattern', 'timestamp', 'minute_1_time', 'minute_2_time', 'minute_3_time',
                'first_open', 'last_next_open', 'total_change', 
                'change_1', 'change_2', 'change_3', 'volume'
            ])
            occ_writer.writeheader()
        
        # Apply offset
        bars_to_process = bars[offset:] if offset > 0 else bars
        
        i = 0
        while i + chunk_size <= len(bars_to_process):
            chunk_bars = bars_to_process[i:i + chunk_size]
            
            # Build pattern string
            pattern_chars = []
            individual_changes = []
            minute_timestamps = []
            
            for j in range(chunk_size):
                current_bar = chunk_bars[j]
                next_bar = chunk_bars[j + 1] if j + 1 < chunk_size else (
                    bars_to_process[i + chunk_size] if i + chunk_size < len(bars_to_process) else None
                )
                
                classification = self.classify_candle(current_bar, next_bar)
                pattern_chars.append(classification)
                minute_timestamps.append(datetime.fromtimestamp(current_bar['t'] / 1000))
                
                if next_bar:
                    change = next_bar['o'] - current_bar['o']
                    individual_changes.append(change)
                else:
                    individual_changes.append(0)
            
            pattern_string = ''.join(pattern_chars)
            
            # Calculate total change
            first_open = chunk_bars[0]['o']
            if i + chunk_size < len(bars_to_process):
                last_next_open = bars_to_process[i + chunk_size]['o']
                total_change = last_next_open - first_open
            else:
                total_change = chunk_bars[-1]['c'] - first_open
                last_next_open = chunk_bars[-1]['c']
            
            # Calculate volume
            total_volume = sum(bar['v'] for bar in chunk_bars)
            
            # Store pattern occurrence
            start_timestamp = datetime.fromtimestamp(chunk_bars[0]['t'] / 1000)
            end_timestamp = datetime.fromtimestamp(chunk_bars[-1]['t'] / 1000)
            
            bucket = pattern_buckets[pattern_string]
            bucket['count'] += 1
            bucket['total_change'] += total_change
            bucket['total_volume'] += total_volume
            bucket['individual_changes'].append(individual_changes)
            bucket['occurrences'].append({
                'start_time': start_timestamp,
                'end_time': end_timestamp,
                'first_open': first_open,
                'total_change': total_change,
                'individual_changes': individual_changes,
                'volume': total_volume
            })
            
            # Write to occurrences CSV
            if csv_dir:
                occ_row = {
                    'pattern': pattern_string,
                    'timestamp': start_timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'minute_1_time': minute_timestamps[0].strftime('%H:%M:%S'),
                    'minute_2_time': minute_timestamps[1].strftime('%H:%M:%S'),
                    'minute_3_time': minute_timestamps[2].strftime('%H:%M:%S'),
                    'first_open': f"{first_open:.4f}",
                    'last_next_open': f"{last_next_open:.4f}",
                    'total_change': f"{total_change:.4f}",
                    'change_1': f"{individual_changes[0]:.4f}" if len(individual_changes) > 0 else "0",
                    'change_2': f"{individual_changes[1]:.4f}" if len(individual_changes) > 1 else "0",
                    'change_3': f"{individual_changes[2]:.4f}" if len(individual_changes) > 2 else "0",
                    'volume': total_volume
                }
                occ_writer.writerow(occ_row)
            
            i += chunk_size
        
        if csv_dir:
            occ_file.close()
            print(f"✓ Pattern occurrences saved to: {occurrences_file}")
        
        return pattern_buckets, total_possible_patterns
    
    def calculate_statistics(self, pattern_buckets):
        """
        Calculate comprehensive statistics for each pattern
        """
        for pattern, bucket in pattern_buckets.items():
            if bucket['count'] > 0:
                # Basic averages
                bucket['avg_total_change'] = bucket['total_change'] / bucket['count']
                bucket['avg_volume'] = bucket['total_volume'] / bucket['count']
                
                # Calculate consistency metrics
                changes = [occ['total_change'] for occ in bucket['occurrences']]
                if len(changes) > 1:
                    bucket['std_dev'] = np.std(changes)
                    bucket['min_change'] = min(changes)
                    bucket['max_change'] = max(changes)
                    bucket['range'] = bucket['max_change'] - bucket['min_change']
                    
                    # Sharpe-like ratio
                    if bucket['std_dev'] > 0:
                        bucket['return_risk_ratio'] = bucket['avg_total_change'] / bucket['std_dev']
                    else:
                        bucket['return_risk_ratio'] = float('inf') if bucket['avg_total_change'] > 0 else 0
                    
                    # Win rate
                    positive_outcomes = sum(1 for c in changes if c > 0)
                    bucket['win_rate'] = positive_outcomes / len(changes)
                else:
                    bucket['std_dev'] = 0
                    bucket['min_change'] = bucket['max_change'] = changes[0] if changes else 0
                    bucket['range'] = 0
                    bucket['return_risk_ratio'] = float('inf') if bucket['avg_total_change'] > 0 else 0
                    bucket['win_rate'] = 1 if bucket['avg_total_change'] > 0 else 0
    
    def export_pattern_details(self, pattern_buckets, offset, csv_dir):
        """
        Export detailed CSV files for each pattern with timestamps
        """
        pattern_dir = os.path.join(csv_dir, f"pattern_details_offset_{offset}")
        os.makedirs(pattern_dir, exist_ok=True)
        
        for pattern, bucket in pattern_buckets.items():
            if bucket['count'] > 0:
                pattern_file = os.path.join(pattern_dir, f"pattern_{pattern}.csv")
                with open(pattern_file, 'w', newline='') as csvfile:
                    fieldnames = ['occurrence_num', 'timestamp', 'first_open', 'total_change', 
                                 'minute_1_change', 'minute_2_change', 'minute_3_change', 'volume']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    
                    for idx, occ in enumerate(bucket['occurrences'], 1):
                        row = {
                            'occurrence_num': idx,
                            'timestamp': occ['start_time'].strftime('%Y-%m-%d %H:%M:%S'),
                            'first_open': f"{occ['first_open']:.4f}",
                            'total_change': f"{occ['total_change']:.4f}",
                            'minute_1_change': f"{occ['individual_changes'][0]:.4f}" if len(occ['individual_changes']) > 0 else "0",
                            'minute_2_change': f"{occ['individual_changes'][1]:.4f}" if len(occ['individual_changes']) > 1 else "0",
                            'minute_3_change': f"{occ['individual_changes'][2]:.4f}" if len(occ['individual_changes']) > 2 else "0",
                            'volume': occ['volume']
                        }
                        writer.writerow(row)
        
        print(f"✓ Individual pattern details saved to: {pattern_dir}/")
    
    def export_results(self, pattern_buckets, offset, csv_dir):
        """
        Export comprehensive analysis results for specific offset
        """
        # Summary file for this offset
        summary_file = os.path.join(csv_dir, f"pattern_summary_offset_{offset}.csv")
        with open(summary_file, 'w', newline='') as csvfile:
            fieldnames = ['pattern', 'count', 'frequency_%', 'total_change', 'avg_change', 
                         'std_dev', 'min_change', 'max_change', 'win_rate', 
                         'return_risk_ratio', 'avg_volume']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            total_patterns = sum(b['count'] for b in pattern_buckets.values())
            
            for pattern, bucket in sorted(pattern_buckets.items(), 
                                         key=lambda x: x[1]['avg_total_change'], reverse=True):
                if bucket['count'] > 0:
                    row = {
                        'pattern': pattern,
                        'count': bucket['count'],
                        'frequency_%': f"{(bucket['count']/total_patterns*100):.2f}",
                        'total_change': f"{bucket['total_change']:.4f}",
                        'avg_change': f"{bucket.get('avg_total_change', 0):.4f}",
                        'std_dev': f"{bucket.get('std_dev', 0):.4f}",
                        'min_change': f"{bucket.get('min_change', 0):.4f}",
                        'max_change': f"{bucket.get('max_change', 0):.4f}",
                        'win_rate': f"{bucket.get('win_rate', 0):.2%}",
                        'return_risk_ratio': f"{bucket.get('return_risk_ratio', 0):.4f}",
                        'avg_volume': f"{bucket.get('avg_volume', 0):.0f}"
                    }
                    writer.writerow(row)
        
        print(f"✓ Pattern summary for offset {offset} saved to: {summary_file}")
        
        # Export individual pattern details
        self.export_pattern_details(pattern_buckets, offset, csv_dir)
    
    def run_offset_comparison(self, cleaned_bars, symbol, csv_dir):
        """
        Run analysis with offsets of 0, 1, and 2 minutes
        """
        print("\n" + "="*80)
        print("3-MINUTE PATTERN ANALYSIS WITH OFFSET STUDIES")
        print("="*80)
        
        offset_results = []
        all_offset_patterns = {}
        
        # Run analysis for each offset (0, 1, 2)
        for offset in range(3):
            print(f"\n{'='*60}")
            print(f"ANALYZING WITH OFFSET: {offset} MINUTE(S)")
            print(f"{'='*60}")
            
            # Process patterns for this offset
            pattern_buckets, total_possible = self.process_patterns_3min(
                cleaned_bars, offset, csv_dir, symbol
            )
            
            # Calculate statistics
            self.calculate_statistics(pattern_buckets)
            
            # Export results for this offset
            self.export_results(pattern_buckets, offset, csv_dir)
            
            # Store results for comparison
            all_offset_patterns[offset] = pattern_buckets
            
            # Collect metrics
            total_chunks = sum(b['count'] for b in pattern_buckets.values())
            total_change = sum(b['total_change'] for b in pattern_buckets.values())
            unique_patterns = len([b for b in pattern_buckets.values() if b['count'] > 0])
            
            offset_results.append({
                'offset': offset,
                'bars_processed': len(cleaned_bars) - offset,
                'chunks_formed': total_chunks,
                'unique_patterns': unique_patterns,
                'total_change': total_change,
                'avg_change_per_chunk': total_change / total_chunks if total_chunks > 0 else 0
            })
            
            # Print top patterns for this offset
            print(f"\nTop 5 patterns for offset {offset}:")
            print("-"*60)
            sorted_patterns = sorted(pattern_buckets.items(), 
                                   key=lambda x: x[1].get('avg_total_change', 0), 
                                   reverse=True)
            for pattern, bucket in sorted_patterns[:5]:
                if bucket['count'] > 0:
                    print(f"  {pattern}: Count={bucket['count']}, "
                          f"Avg Change=${bucket.get('avg_total_change', 0):.4f}, "
                          f"Win Rate={bucket.get('win_rate', 0):.1%}")
        
        # Export offset comparison
        self.export_offset_comparison_summary(offset_results, all_offset_patterns, csv_dir)
        
        return offset_results
    
    def export_offset_comparison_summary(self, offset_results, all_patterns, csv_dir):
        """
        Export comprehensive comparison across all offsets
        """
        # Overall comparison
        comparison_file = os.path.join(csv_dir, "offset_comparison_summary.csv")
        with open(comparison_file, 'w', newline='') as csvfile:
            fieldnames = ['offset', 'bars_processed', 'chunks_formed', 'unique_patterns',
                         'total_change', 'avg_change_per_chunk']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in offset_results:
                writer.writerow(result)
        
        print(f"\n✓ Offset comparison summary saved to: {comparison_file}")
        
        # Pattern consistency across offsets
        consistency_file = os.path.join(csv_dir, "pattern_consistency_across_offsets.csv")
        
        # Get all unique patterns across all offsets
        all_unique_patterns = set()
        for offset_patterns in all_patterns.values():
            all_unique_patterns.update(p for p, b in offset_patterns.items() if b['count'] > 0)
        
        with open(consistency_file, 'w', newline='') as csvfile:
            fieldnames = ['pattern', 'offset_0_count', 'offset_0_avg', 
                         'offset_1_count', 'offset_1_avg',
                         'offset_2_count', 'offset_2_avg', 'total_occurrences']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for pattern in sorted(all_unique_patterns):
                row = {'pattern': pattern}
                total_count = 0
                
                for offset in range(3):
                    if pattern in all_patterns[offset]:
                        bucket = all_patterns[offset][pattern]
                        row[f'offset_{offset}_count'] = bucket['count']
                        row[f'offset_{offset}_avg'] = f"{bucket.get('avg_total_change', 0):.4f}"
                        total_count += bucket['count']
                    else:
                        row[f'offset_{offset}_count'] = 0
                        row[f'offset_{offset}_avg'] = "0.0000"
                
                row['total_occurrences'] = total_count
                writer.writerow(row)
        
        print(f"✓ Pattern consistency analysis saved to: {consistency_file}")
        
        # Print summary
        print("\n" + "="*80)
        print("OFFSET COMPARISON SUMMARY")
        print("="*80)
        print(f"{'Offset':<10} {'Bars':<10} {'Chunks':<10} {'Patterns':<12} {'Total Δ':>12} {'Avg Δ/Chunk':>12}")
        print("-"*80)
        
        for r in offset_results:
            print(f"{r['offset']:<10} {r['bars_processed']:<10} {r['chunks_formed']:<10} "
                  f"{r['unique_patterns']:<12} {r['total_change']:>12.4f} "
                  f"{r['avg_change_per_chunk']:>12.4f}")
    
    def run_analysis(self, symbol, start_date, end_date):
        """
        Main method to run the 3-minute pattern analysis with offsets
        """
        print(f"\n🚀 Starting 3-Minute Pattern Analysis for {symbol}")
        print(f"Date range: {start_date} to {end_date}")
        print("="*80)
        
        # Step 1: Fetch data
        print("\n📥 STEP 1: Fetching data from Polygon.io...")
        bars = self.get_aggs(symbol, start_date, end_date)
        
        if not bars:
            print("No data found. Trying older dates...")
            older_end = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            older_start = (datetime.now() - timedelta(days=707)).strftime("%Y-%m-%d")
            print(f"Trying date range: {older_start} to {older_end}")
            bars = self.get_aggs(symbol, older_start, older_end)
            
            if bars:
                start_date = older_start
                end_date = older_end
        
        if not bars:
            print("❌ No data available for analysis.")
            return None
        
        # Step 2: Save raw data
        print("\n💾 STEP 2: Saving raw data...")
        csv_filename, csv_dir = self.save_raw_data(bars, symbol, start_date, end_date)
        
        # Step 3: Clean data
        print("\n🧹 STEP 3: Cleaning data...")
        cleaned_bars, cleanup_summary = self.clean_data(bars, symbol, csv_dir)
        
        if not cleaned_bars:
            print("❌ No data remaining after cleanup.")
            return None
        
        # Step 4: Run offset comparison analysis
        print("\n📊 STEP 4: Running 3-minute pattern analysis with offsets...")
        offset_results = self.run_offset_comparison(cleaned_bars, symbol, csv_dir)
        
        print(f"\n✅ All analysis complete! Files saved to: {csv_dir}/")
        print("="*80)
        
        return offset_results

def main():
    # Configuration
    API_KEY = "Z_ENWpm0RRrvXvLOY65uMH8RB93B4gBN"
    SYMBOL = "SPY"
    
    # Use historical dates
    end_date = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=700)).strftime("%Y-%m-%d")
    
    print("="*120)
    print("3-MINUTE STOCK PATTERN ANALYZER WITH OFFSET STUDIES")
    print("="*120)
    print("Features:")
    print("• 3-minute pattern analysis (3^3 = 27 possible patterns)")
    print("• Offset studies: 0, 1, and 2 minute offsets")
    print("• Pattern classification: Positive/Negative/Zero")
    print("• Detailed timestamps and changes for each pattern occurrence")
    print("• Comprehensive statistics: averages, std dev, win rates, return/risk ratios")
    print("• Data cleaning: removes duplicates, zero volume, outliers, and logs gaps")
    print("• CSV exports for raw data, cleaned data, pattern summaries, and individual patterns")
    print("• Handles API errors and delayed data access")
    print("="*120)  
    print(f"Analyzing symbol: {SYMBOL}")
    print(f"Date range: {start_date} to {end_date}")
    print("="*120)

    analyzer = ThreeMinutePatternAnalyzer(API_KEY)  
    analyzer.run_analysis(SYMBOL, start_date, end_date)

if __name__ == "__main__":
    main()