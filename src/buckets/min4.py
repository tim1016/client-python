import requests
import json
from datetime import datetime, timedelta
from collections import defaultdict
import csv
import os
import numpy as np
import pandas as pd

class EnhancedPatternAnalyzer:
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
        csv_dir = f"enhanced_analysis_{symbol}_{start_date}_to_{end_date}"
        os.makedirs(csv_dir, exist_ok=True)
        
        csv_filename = os.path.join(csv_dir, f"raw_{symbol}_{start_date}_to_{end_date}.csv")
        
        with open(csv_filename, 'w', newline='') as csvfile:
            fieldnames = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'vwap', 'trades'
                          , 'symbol']
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
        
        # 2. Remove zero volume bars (except during market hours gaps)
        zero_volume = df['v'] == 0
        cleanup_summary['zero_volume_bars'] = zero_volume.sum()
        df = df[~zero_volume]
        
        # 3. Detect and log time gaps (more than 1 minute between consecutive bars)
        df['time_diff'] = df['timestamp'].diff()
        gaps = df[df['time_diff'] > pd.Timedelta(minutes=1)]
        cleanup_summary['gap_minutes'] = len(gaps)
        
        # 4. Remove outliers (prices more than 10% from rolling mean)
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
            f.write(f"Outliers removed: {cleanup_summary['outliers_removed']}\n")
            f.write(f"Time gaps detected (>1min): {cleanup_summary['gap_minutes']}\n")
            f.write(f"Total bars removed: {cleanup_summary['removed_bars']}\n")
            f.write(f"Final cleaned bars: {cleanup_summary['cleaned_bars']}\n")
            f.write(f"Data quality score: {(cleanup_summary['cleaned_bars']/cleanup_summary['total_bars']*100):.2f}%\n")
            
            if cleanup_summary['gap_minutes'] > 0:
                f.write("\nTime Gap Details:\n")
                f.write("-"*30 + "\n")
                for _, gap_row in gaps.iterrows():
                    f.write(f"Gap at {gap_row['timestamp']}: {gap_row['time_diff'].total_seconds()/60:.1f} minutes\n")
        
        print(f"✓ Cleanup summary saved to: {summary_file}")
        
        # Print summary to console
        print("\nCleanup Results:")
        print("-"*30)
        print(f"Original bars: {cleanup_summary['total_bars']}")
        print(f"Cleaned bars: {cleanup_summary['cleaned_bars']}")
        print(f"Removed: {cleanup_summary['removed_bars']} ({cleanup_summary['removed_bars']/cleanup_summary['total_bars']*100:.2f}%)")
        print(f"Data quality score: {(cleanup_summary['cleaned_bars']/cleanup_summary['total_bars']*100):.2f}%")
        
        # Save cleaned data
        cleaned_file = os.path.join(csv_dir, f"cleaned_{symbol}.csv")
        df_clean = pd.DataFrame(cleaned_bars)
        df_clean['timestamp'] = pd.to_datetime(df_clean['t'], unit='ms')
        df_clean[['timestamp', 'o', 'h', 'l', 'c', 'v']].to_csv(cleaned_file, index=False)
        print(f"✓ Cleaned data saved to: {cleaned_file}")
        
        return cleaned_bars, cleanup_summary
    
    def classify_candle_enhanced(self, current_bar, next_bar):
        """
        Classify candle based on open-to-open price change
        P: Positive (next open > current open)
        N: Negative (next open < current open)  
        O: Zero (next open = current open)
        """
        if next_bar is None:
            return 'O'  # Default to O for last candle
            
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
    
    def process_patterns_enhanced(self, bars):
        """
        Process data in 5-minute chunks with enhanced 3-type classification
        """
        pattern_buckets = defaultdict(lambda: {
            'occurrences': [],
            'total_change': 0.0,
            'count': 0,
            'total_volume': 0,
            'individual_changes': []
        })
        
        chunk_size = 5
        total_possible_patterns = 3 ** chunk_size  # 243 patterns
        
        print(f"\nProcessing {total_possible_patterns} possible patterns (3^5)...")
        
        i = 0
        while i + chunk_size <= len(bars):
            chunk_bars = bars[i:i + chunk_size]
            
            # Build pattern string using new classification
            pattern_chars = []
            individual_changes = []
            
            for j in range(chunk_size):
                current_bar = chunk_bars[j]
                next_bar = chunk_bars[j + 1] if j + 1 < chunk_size else (
                    bars[i + chunk_size] if i + chunk_size < len(bars) else None
                )
                
                classification = self.classify_candle_enhanced(current_bar, next_bar)
                pattern_chars.append(classification)
                
                if next_bar:
                    change = next_bar['o'] - current_bar['o']
                    individual_changes.append(change)
                else:
                    individual_changes.append(0)
            
            pattern_string = ''.join(pattern_chars)
            
            # Calculate total change for pattern (first open to last+1 open)
            first_open = chunk_bars[0]['o']
            if i + chunk_size < len(bars):
                last_next_open = bars[i + chunk_size]['o']
                total_change = last_next_open - first_open
            else:
                # For last chunk, use close of last bar
                total_change = chunk_bars[-1]['c'] - first_open
            
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
            
            i += chunk_size
        
        return pattern_buckets, total_possible_patterns
    
    def calculate_enhanced_statistics(self, pattern_buckets):
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
                    
                    # Sharpe-like ratio (return/risk)
                    if bucket['std_dev'] > 0:
                        bucket['return_risk_ratio'] = bucket['avg_total_change'] / bucket['std_dev']
                    else:
                        bucket['return_risk_ratio'] = float('inf') if bucket['avg_total_change'] > 0 else 0
                    
                    # Win rate (percentage of positive outcomes)
                    positive_outcomes = sum(1 for c in changes if c > 0)
                    bucket['win_rate'] = positive_outcomes / len(changes)
                else:
                    bucket['std_dev'] = 0
                    bucket['min_change'] = bucket['max_change'] = changes[0] if changes else 0
                    bucket['range'] = 0
                    bucket['return_risk_ratio'] = float('inf') if bucket['avg_total_change'] > 0 else 0
                    bucket['win_rate'] = 1 if bucket['avg_total_change'] > 0 else 0
    
    def export_enhanced_results(self, pattern_buckets, symbol, start_date, end_date, csv_dir):
        """
        Export comprehensive analysis results
        """
        # 1. Export detailed pattern summary
        summary_file = os.path.join(csv_dir, "pattern_analysis_summary.csv")
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
        
        print(f"✓ Pattern summary exported to: {summary_file}")
        
        # 2. Export top patterns analysis
        top_patterns_file = os.path.join(csv_dir, "top_patterns.csv")
        with open(top_patterns_file, 'w', newline='') as csvfile:
            # Get top 20 by different metrics
            by_profit = sorted(pattern_buckets.items(), 
                             key=lambda x: x[1].get('avg_total_change', 0), reverse=True)[:20]
            by_frequency = sorted(pattern_buckets.items(), 
                                key=lambda x: x[1]['count'], reverse=True)[:20]
            by_consistency = sorted(pattern_buckets.items(), 
                                  key=lambda x: x[1].get('return_risk_ratio', 0), reverse=True)[:20]
            
            fieldnames = ['rank', 'by_profit', 'profit_avg', 'by_frequency', 'freq_count', 
                         'by_consistency', 'consistency_ratio']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for i in range(20):
                row = {'rank': i + 1}
                
                if i < len(by_profit) and by_profit[i][1]['count'] > 0:
                    row['by_profit'] = by_profit[i][0]
                    row['profit_avg'] = f"{by_profit[i][1].get('avg_total_change', 0):.4f}"
                
                if i < len(by_frequency) and by_frequency[i][1]['count'] > 0:
                    row['by_frequency'] = by_frequency[i][0]
                    row['freq_count'] = by_frequency[i][1]['count']
                
                if i < len(by_consistency) and by_consistency[i][1]['count'] > 0:
                    row['by_consistency'] = by_consistency[i][0]
                    row['consistency_ratio'] = f"{by_consistency[i][1].get('return_risk_ratio', 0):.4f}"
                
                writer.writerow(row)
        
        print(f"✓ Top patterns exported to: {top_patterns_file}")
        
        # 3. Export individual pattern files for top performers
        top_10_patterns = sorted(pattern_buckets.items(), 
                                key=lambda x: x[1].get('avg_total_change', 0), reverse=True)[:10]
        
        for pattern, bucket in top_10_patterns:
            if bucket['count'] > 0:
                pattern_file = os.path.join(csv_dir, f"pattern_{pattern}_details.csv")
                with open(pattern_file, 'w', newline='') as csvfile:
                    fieldnames = ['timestamp', 'total_change', 'candle_1', 'candle_2', 
                                'candle_3', 'candle_4', 'candle_5', 'volume']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    
                    for occ in bucket['occurrences']:
                        row = {
                            'timestamp': occ['start_time'].strftime('%Y-%m-%d %H:%M:%S'),
                            'total_change': f"{occ['total_change']:.4f}",
                            'volume': occ['volume']
                        }
                        
                        for j, change in enumerate(occ['individual_changes'][:5]):
                            row[f'candle_{j+1}'] = f"{change:.4f}"
                        
                        writer.writerow(row)
        
        print(f"✓ Detailed pattern files exported for top 10 patterns")
    
    def print_enhanced_analysis(self, pattern_buckets, total_possible):
        """
        Print comprehensive analysis results
        """
        print("\n" + "="*120)
        print("ENHANCED 5-MINUTE PATTERN ANALYSIS (3-TYPE CLASSIFICATION)")
        print("="*120)
        print("Pattern Classification: P=Positive, N=Negative, O=Zero (based on open-to-open changes)")
        print("-"*120)
        
        # Summary statistics
        found_patterns = len([p for p in pattern_buckets.values() if p['count'] > 0])
        total_occurrences = sum(b['count'] for b in pattern_buckets.values())
        
        print(f"\n📊 SUMMARY STATISTICS")
        print("-"*50)
        print(f"Total possible patterns: {total_possible}")
        print(f"Patterns found in data: {found_patterns} ({found_patterns/total_possible*100:.1f}%)")
        print(f"Total pattern occurrences: {total_occurrences}")
        print(f"Patterns never seen: {total_possible - found_patterns}")
        
        # Top performers
        sorted_by_avg = sorted(pattern_buckets.items(), 
                              key=lambda x: x[1].get('avg_total_change', 0), reverse=True)
        
        print(f"\n🏆 TOP 10 MOST PROFITABLE PATTERNS")
        print("-"*80)
        print(f"{'Pattern':<10} {'Count':<8} {'Avg Change':<12} {'Total':<12} {'Win Rate':<10} {'Risk/Return':<12}")
        print("-"*80)
        
        for pattern, bucket in sorted_by_avg[:10]:
            if bucket['count'] > 0:
                print(f"{pattern:<10} {bucket['count']:<8} "
                      f"${bucket.get('avg_total_change', 0):<11.4f} "
                      f"${bucket['total_change']:<11.4f} "
                      f"{bucket.get('win_rate', 0):<9.1%} "
                      f"{bucket.get('return_risk_ratio', 0):<11.4f}")
        
        # Worst performers
        print(f"\n📉 TOP 10 LEAST PROFITABLE PATTERNS")
        print("-"*80)
        print(f"{'Pattern':<10} {'Count':<8} {'Avg Change':<12} {'Total':<12} {'Win Rate':<10} {'Risk/Return':<12}")
        print("-"*80)
        
        for pattern, bucket in sorted_by_avg[-10:]:
            if bucket['count'] > 0:
                print(f"{pattern:<10} {bucket['count']:<8} "
                      f"${bucket.get('avg_total_change', 0):<11.4f} "
                      f"${bucket['total_change']:<11.4f} "
                      f"{bucket.get('win_rate', 0):<9.1%} "
                      f"{bucket.get('return_risk_ratio', 0):<11.4f}")
        
        # Most frequent patterns
        sorted_by_freq = sorted(pattern_buckets.items(), 
                               key=lambda x: x[1]['count'], reverse=True)
        
        print(f"\n📈 TOP 10 MOST FREQUENT PATTERNS")
        print("-"*80)
        print(f"{'Pattern':<10} {'Count':<8} {'Frequency':<12} {'Avg Change':<12} {'Total Volume':<15}")
        print("-"*80)
        
        for pattern, bucket in sorted_by_freq[:10]:
            if bucket['count'] > 0:
                freq_pct = bucket['count'] / total_occurrences * 100
                print(f"{pattern:<10} {bucket['count']:<8} "
                      f"{freq_pct:<11.2f}% "
                      f"${bucket.get('avg_total_change', 0):<11.4f} "
                      f"{bucket['total_volume']:<15,}")
        
        # Pattern type distribution
        print(f"\n🔍 PATTERN COMPOSITION ANALYSIS")
        print("-"*50)
        
        # Count P, N, O occurrences
        p_heavy = sum(b['count'] for p, b in pattern_buckets.items() if p.count('P') >= 3)
        n_heavy = sum(b['count'] for p, b in pattern_buckets.items() if p.count('N') >= 3)
        o_heavy = sum(b['count'] for p, b in pattern_buckets.items() if p.count('O') >= 3)
        mixed = total_occurrences - p_heavy - n_heavy - o_heavy
        
        print(f"Positive-heavy patterns (≥3 P): {p_heavy} ({p_heavy/total_occurrences*100:.1f}%)")
        print(f"Negative-heavy patterns (≥3 N): {n_heavy} ({n_heavy/total_occurrences*100:.1f}%)")
        print(f"Zero-heavy patterns (≥3 O): {o_heavy} ({o_heavy/total_occurrences*100:.1f}%)")
        print(f"Mixed patterns: {mixed} ({mixed/total_occurrences*100:.1f}%)")
        
        print("\n" + "="*120)
        print("ANALYSIS COMPLETE")
        print("="*120)
    
    def run_enhanced_analysis(self, symbol, start_date, end_date):
        """
        Main method to run the enhanced pattern analysis
        """
        print(f"\n🚀 Starting Enhanced Pattern Analysis for {symbol}")
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
        
        # Step 4: Process patterns with enhanced classification
        print("\n🔄 STEP 4: Processing patterns with 3-type classification...")
        pattern_buckets, total_possible_patterns = self.process_patterns_enhanced(cleaned_bars)
        
        # Step 5: Calculate statistics
        print("\n📊 STEP 5: Calculating comprehensive statistics...")
        self.calculate_enhanced_statistics(pattern_buckets)
        
        # Step 6: Export results
        print("\n📤 STEP 6: Exporting results...")
        self.export_enhanced_results(pattern_buckets, symbol, start_date, end_date, csv_dir)
        
        # Step 7: Print analysis
        print("\n📋 STEP 7: Generating analysis report...")
        self.print_enhanced_analysis(pattern_buckets, total_possible_patterns)

        # Step 8: Run offset analysis
        print("\n🔄 STEP 8: Running offset analysis...")
        offset_results = self.run_offset_analysis(cleaned_bars, symbol, csv_dir)
        
        print(f"\n✅ All files saved to: {csv_dir}/")
        
        return pattern_buckets
    
    def run_offset_analysis(self, cleaned_bars: list, symbol: str, csv_dir: str):
        """Run analysis with different offsets and compare results."""
        print("\n📊 STEP 8: Running Offset Analysis...")
        
        offset_results = []
        
        # Run analysis for each offset (0-4)
        for offset in range(5):
            print(f"\nAnalyzing with offset {offset}...")
            
            # Skip 'offset' number of bars
            offset_bars = cleaned_bars[offset:]
            
            # Process patterns for this offset
            pattern_buckets, _ = self.process_patterns_enhanced(offset_bars)
            
            # Calculate statistics
            self.calculate_enhanced_statistics(pattern_buckets)
            
            # Export results for this offset
            summary_file = os.path.join(csv_dir, f"summary_{offset}_offset.csv")
            self.export_offset_summary(pattern_buckets, summary_file)
            
            # Collect metrics for comparison
            total_patterns = sum(b['count'] for b in pattern_buckets.values())
            total_change = sum(b['total_change'] for b in pattern_buckets.values())
            unique_patterns = len([b for b in pattern_buckets.values() if b['count'] > 0])
            
            offset_results.append({
                'offset': offset,
                'bars_processed': len(offset_bars),
                'chunks_formed': total_patterns,
                'unique_patterns': unique_patterns,
                'actual_total_change': total_change,
                'pattern_sum': sum(b.get('total_change', 0) for b in pattern_buckets.values()),
                'verification_diff': abs(total_change - sum(b.get('total_change', 0) 
                                                          for b in pattern_buckets.values()))
            })
        
        # Export offset comparison
        self.export_offset_comparison(offset_results, csv_dir)
        
        return offset_results

    def export_offset_summary(self, pattern_buckets: dict, filename: str):
        """Export summary for a specific offset."""
        with open(filename, 'w', newline='') as csvfile:
            fieldnames = ['pattern', 'occurrences', 'total_change', 'avg_change']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for pattern, bucket in pattern_buckets.items():
                if bucket['count'] > 0:
                    writer.writerow({
                        'pattern': pattern,
                        'occurrences': bucket['count'],
                        'total_change': f"{bucket['total_change']:.4f}",
                        'avg_change': f"{bucket.get('avg_total_change', 0):.4f}"
                    })

    def export_offset_comparison(self, offset_results: list, csv_dir: str):
        """Export comparison of different offsets."""
        comparison_file = os.path.join(csv_dir, "offset_comparison.csv")
        
        with open(comparison_file, 'w', newline='') as csvfile:
            fieldnames = ['offset', 'bars_processed', 'chunks_formed', 'unique_patterns',
                         'actual_total_change', 'pattern_sum', 'verification_diff']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in offset_results:
                writer.writerow(result)
        
        print(f"\n✓ Offset comparison saved to: {comparison_file}")
        
        # Print summary to console
        print("\nOffset Analysis Summary:")
        print("-"*80)
        print(f"{'Offset':<8} {'Bars':<8} {'Chunks':<8} {'Patterns':<10} {'Total Δ':>12} {'Verify Δ':>12}")
        print("-"*80)
        
        for r in offset_results:
            print(f"{r['offset']:<8} {r['bars_processed']:<8} {r['chunks_formed']:<8} "
                  f"{r['unique_patterns']:<10} {r['actual_total_change']:>12.4f} "
                  f"{r['verification_diff']:>12.4f}")
    
def main():
    # Configuration
    API_KEY = "Z_ENWpm0RRrvXvLOY65uMH8RB93B4gBN"
    SYMBOL = "SPY"
    
    # Use historical dates
    end_date = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=700)).strftime("%Y-%m-%d")
    
    print("="*120)
    print("ENHANCED STOCK PATTERN ANALYZER v2.0 - 4-MINUTE PATTERNS")
    print("="*120)
    print("Features:")
    print("• 3-type candle classification (Positive/Negative/Zero)")
    print("• Open-to-open price change calculation")
    print("• 81 possible pattern combinations (3^4)")
    print("• Comprehensive data cleaning")
    print("• Advanced statistical metrics")
    print("="*120)
    
    # Create analyzer instance
    analyzer = EnhancedPatternAnalyzer(API_KEY)
    
    # Run the enhanced analysis
    analyzer.run_enhanced_analysis(SYMBOL, start_date, end_date)

if __name__ == "__main__":
    main()