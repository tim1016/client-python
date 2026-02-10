"""
Three-Minute Pattern Analyzer - Modified to work with fetched data
Analyzes pre-fetched minute-level stock data for 3-minute patterns
Enhanced with contiguous basket analysis and validation
"""

import pandas as pd
import numpy as np
import csv
import os
import json
from datetime import datetime
from collections import defaultdict
import argparse

class ThreeMinutePatternAnalyzer:
    def __init__(self, data_file: str, output_dir: str = None):
        """
        Initialize analyzer with pre-fetched data file.
        
        Args:
            data_file: Path to the fetched CSV data file
            output_dir: Directory for analysis output (auto-generated if None)
        """
        self.data_file = data_file
        self.symbol = self.extract_symbol_from_filename(data_file)
        self.output_dir = output_dir or self.create_output_directory()
        
    def extract_symbol_from_filename(self, filepath: str) -> str:
        """Extract symbol from the data file name."""
        filename = os.path.basename(filepath)
        # Format: SYMBOL_startdate_to_enddate_raw.csv
        symbol = filename.split('_')[0]
        return symbol
    
    def create_output_directory(self) -> str:
        """Create output directory for analysis results."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_dir = f"analysis_results/{self.symbol}_{timestamp}"
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(f"{output_dir}/pattern_details", exist_ok=True)
        os.makedirs(f"{output_dir}/visualizations", exist_ok=True)
        return output_dir
    
    def load_fetched_data(self) -> pd.DataFrame:
        """Load the pre-fetched data from CSV file."""
        print(f"\n📂 Loading data from: {self.data_file}")
        
        df = pd.read_csv(self.data_file)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Rename columns to match expected format
        column_mapping = {
            'open': 'o',
            'high': 'h', 
            'low': 'l',
            'close': 'c',
            'volume': 'v',
            'vwap': 'vw',
            'trades': 'n',
            'unix_ms': 't'
        }
        
        df = df.rename(columns=column_mapping)
        
        print(f"✅ Loaded {len(df)} bars")
        print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        
        return df
    
    def clean_data(self, df: pd.DataFrame) -> tuple:
        """Clean and prepare data for analysis."""
        print("\n🧹 Cleaning data...")
        
        cleanup_summary = {
            'total_bars': len(df),
            'removed_bars': 0,
            'gap_minutes': 0,
            'outliers_removed': 0,
            'zero_volume_bars': 0,
            'duplicate_timestamps': 0,
            'cleaned_bars': 0
        }
        
        original_count = len(df)
        
        # Sort by timestamp
        df = df.sort_values('timestamp')
        
        # Remove duplicates
        duplicates = df.duplicated(subset=['timestamp'])
        cleanup_summary['duplicate_timestamps'] = duplicates.sum()
        df = df[~duplicates]
        
        # Remove zero volume bars
        zero_volume = df['v'] == 0
        cleanup_summary['zero_volume_bars'] = zero_volume.sum()
        df = df[~zero_volume]
        
        # Detect time gaps
        df['time_diff'] = df['timestamp'].diff()
        gaps = df[df['time_diff'] > pd.Timedelta(minutes=1)]
        cleanup_summary['gap_minutes'] = len(gaps)
        
        # Remove outliers (optional, conservative approach)
        window_size = min(60, len(df) // 10) if len(df) > 10 else len(df)
        if window_size > 1:
            df['rolling_mean'] = df['c'].rolling(window=window_size, center=True).mean()
            df['rolling_mean'] = df['rolling_mean'].fillna(df['c'])
            df['price_deviation'] = abs(df['c'] - df['rolling_mean']) / df['rolling_mean']
            outliers = df['price_deviation'] > 0.1  # 10% deviation threshold
            cleanup_summary['outliers_removed'] = outliers.sum()
            df = df[~outliers]
            df = df.drop(['rolling_mean', 'price_deviation'], axis=1)
        
        # Final count
        cleanup_summary['cleaned_bars'] = len(df)
        cleanup_summary['removed_bars'] = original_count - len(df)
        
        # Convert numpy types to Python native types for JSON serialization
        cleanup_summary_json = {}
        for key, value in cleanup_summary.items():
            if isinstance(value, (np.int64, np.int32)):
                cleanup_summary_json[key] = int(value)
            elif isinstance(value, (np.float64, np.float32)):
                cleanup_summary_json[key] = float(value)
            else:
                cleanup_summary_json[key] = value
        
        # Save cleanup summary
        summary_file = os.path.join(self.output_dir, "cleanup_summary.json")
        with open(summary_file, 'w') as f:
            json.dump(cleanup_summary_json, f, indent=2)
        
        print(f"  Original bars: {cleanup_summary['total_bars']}")
        print(f"  Cleaned bars: {cleanup_summary['cleaned_bars']}")
        print(f"  Removed: {cleanup_summary['removed_bars']} ({cleanup_summary['removed_bars']/cleanup_summary['total_bars']*100:.2f}%)")
        print(f"✅ Cleanup summary saved to: {summary_file}")
        
        # Save cleaned data
        cleaned_file = os.path.join(self.output_dir, f"cleaned_{self.symbol}.csv")
        df.to_csv(cleaned_file, index=False)
        print(f"✅ Cleaned data saved to: {cleaned_file}")
        
        return df, cleanup_summary
    
    def classify_candle(self, current_open: float, next_open: float) -> str:
        """
        Classify candle based on open-to-open price change.
        P: Positive (next open > current open)
        N: Negative (next open < current open)
        O: Zero (next open = current open)
        """
        threshold = 0.0001
        price_change = next_open - current_open
        
        if price_change > threshold:
            return 'P'
        elif price_change < -threshold:
            return 'N'
        else:
            return 'O'
    
    def create_contiguous_basket_summary(self, df: pd.DataFrame, offset: int = 0) -> dict:
        """
        Create summary of contiguous 3-candle baskets with comprehensive statistics.
        Each basket represents a 3-minute pattern with start/end times, pattern type, 
        price change, and duration.
        """
        chunk_size = 3
        df_offset = df.iloc[offset:].reset_index(drop=True)
        
        baskets = []
        total_contiguous_change = 0
        total_contiguous_time = 0
        
        i = 0
        basket_id = 0
        
        while i + chunk_size <= len(df_offset):
            chunk_bars = df_offset.iloc[i:i + chunk_size]
            
            # Basket timing
            start_time = chunk_bars.iloc[0]['timestamp']
            end_time = chunk_bars.iloc[-1]['timestamp']
            basket_duration = (end_time - start_time).total_seconds() / 60  # minutes
            
            # Pattern classification
            pattern_chars = []
            for j in range(chunk_size):
                current_open = chunk_bars.iloc[j]['o']
                if j < chunk_size - 1:
                    next_open = chunk_bars.iloc[j + 1]['o']
                else:
                    # For last candle in basket, compare to next basket's first open
                    if i + chunk_size < len(df_offset):
                        next_open = df_offset.iloc[i + chunk_size]['o']
                    else:
                        # If no next basket, use close of last candle
                        next_open = chunk_bars.iloc[j]['c']
                
                classification = self.classify_candle(current_open, next_open)
                pattern_chars.append(classification)
            
            pattern_type = ''.join(pattern_chars)
            
            # Price change for this basket
            basket_start_price = chunk_bars.iloc[0]['o']
            if i + chunk_size < len(df_offset):
                basket_end_price = df_offset.iloc[i + chunk_size]['o']
            else:
                basket_end_price = chunk_bars.iloc[-1]['c']
            
            basket_price_change = basket_end_price - basket_start_price
            
            # Volume and trade data
            basket_volume = chunk_bars['v'].sum()
            basket_trades = chunk_bars.get('n', pd.Series([0]*len(chunk_bars))).sum()
            
            # High/Low for basket
            basket_high = chunk_bars['h'].max()
            basket_low = chunk_bars['l'].min()
            basket_range = basket_high - basket_low
            
            basket = {
                'basket_id': basket_id,
                'pattern_type': pattern_type,
                'start_time': start_time,
                'end_time': end_time,
                'duration_minutes': basket_duration,
                'start_price': basket_start_price,
                'end_price': basket_end_price,
                'price_change': basket_price_change,
                'volume': basket_volume,
                'trades': basket_trades,
                'basket_high': basket_high,
                'basket_low': basket_low,
                'basket_range': basket_range,
                'start_index': i,
                'end_index': i + chunk_size - 1
            }
            
            baskets.append(basket)
            total_contiguous_change += basket_price_change
            total_contiguous_time += basket_duration
            
            basket_id += 1
            i += chunk_size
        
        # Handle remainder bars (incomplete basket at the end)
        remainder_bars = len(df_offset) % chunk_size
        remainder_change = 0
        remainder_time = 0
        
        if remainder_bars > 0:
            last_complete_index = len(baskets) * chunk_size
            remainder_chunk = df_offset.iloc[last_complete_index:]
            
            if len(remainder_chunk) > 0:
                remainder_start_price = remainder_chunk.iloc[0]['o']
                remainder_end_price = remainder_chunk.iloc[-1]['c']
                remainder_change = remainder_end_price - remainder_start_price
                
                remainder_start_time = remainder_chunk.iloc[0]['timestamp']
                remainder_end_time = remainder_chunk.iloc[-1]['timestamp']
                remainder_time = (remainder_end_time - remainder_start_time).total_seconds() / 60
        
        # Calculate overall statistics
        actual_total_change = df_offset.iloc[-1]['c'] - df_offset.iloc[0]['o']
        actual_total_time = (df_offset.iloc[-1]['timestamp'] - df_offset.iloc[0]['timestamp']).total_seconds() / 60
        
        # Mathematical verification
        accounted_change = total_contiguous_change + remainder_change
        accounted_time = total_contiguous_time + remainder_time
        
        change_discrepancy = abs(actual_total_change - accounted_change)
        time_discrepancy = abs(actual_total_time - accounted_time)
        
        summary = {
            'offset': offset,
            'total_baskets': len(baskets),
            'remainder_bars': remainder_bars,
            'baskets': baskets,
            'total_contiguous_change': total_contiguous_change,
            'remainder_change': remainder_change,
            'accounted_total_change': accounted_change,
            'actual_total_change': actual_total_change,
            'change_discrepancy': change_discrepancy,
            'total_contiguous_time': total_contiguous_time,
            'remainder_time': remainder_time,
            'accounted_total_time': accounted_time,
            'actual_total_time': actual_total_time,
            'time_discrepancy': time_discrepancy,
            'mathematical_consistency': {
                'change_matches': change_discrepancy < 0.0001,
                'time_matches': time_discrepancy < 0.1  # 0.1 minute tolerance
            }
        }
        
        return summary
    
    def export_basket_summary(self, basket_summary: dict, offset: int) -> None:
        """Export detailed basket summary to CSV and JSON files."""
        
        # Export basket details to CSV
        basket_file = os.path.join(self.output_dir, f"basket_summary_offset_{offset}.csv")
        
        with open(basket_file, 'w', newline='') as csvfile:
            fieldnames = [
                'basket_id', 'pattern_type', 'start_time', 'end_time', 'duration_minutes',
                'start_price', 'end_price', 'price_change', 'volume', 'trades',
                'basket_high', 'basket_low', 'basket_range'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for basket in basket_summary['baskets']:
                row = {
                    'basket_id': basket['basket_id'],
                    'pattern_type': basket['pattern_type'],
                    'start_time': basket['start_time'].strftime('%Y-%m-%d %H:%M:%S'),
                    'end_time': basket['end_time'].strftime('%Y-%m-%d %H:%M:%S'),
                    'duration_minutes': f"{basket['duration_minutes']:.2f}",
                    'start_price': f"{basket['start_price']:.4f}",
                    'end_price': f"{basket['end_price']:.4f}",
                    'price_change': f"{basket['price_change']:.4f}",
                    'volume': basket['volume'],
                    'trades': basket['trades'],
                    'basket_high': f"{basket['basket_high']:.4f}",
                    'basket_low': f"{basket['basket_low']:.4f}",
                    'basket_range': f"{basket['basket_range']:.4f}"
                }
                writer.writerow(row)
        
        # Export summary statistics
        summary_stats_file = os.path.join(self.output_dir, f"basket_statistics_offset_{offset}.json")
        
        # Prepare JSON-serializable summary
        json_summary = {
            'offset': basket_summary['offset'],
            'total_baskets': basket_summary['total_baskets'],
            'remainder_bars': basket_summary['remainder_bars'],
            'total_contiguous_change': float(basket_summary['total_contiguous_change']),
            'remainder_change': float(basket_summary['remainder_change']),
            'accounted_total_change': float(basket_summary['accounted_total_change']),
            'actual_total_change': float(basket_summary['actual_total_change']),
            'change_discrepancy': float(basket_summary['change_discrepancy']),
            'total_contiguous_time': float(basket_summary['total_contiguous_time']),
            'remainder_time': float(basket_summary['remainder_time']),
            'accounted_total_time': float(basket_summary['accounted_total_time']),
            'actual_total_time': float(basket_summary['actual_total_time']),
            'time_discrepancy': float(basket_summary['time_discrepancy']),
            'mathematical_consistency': {
                'change_matches': bool(basket_summary['mathematical_consistency']['change_matches']),
                'time_matches': bool(basket_summary['mathematical_consistency']['time_matches'])
            },
            'pattern_type_breakdown': self.analyze_pattern_types(basket_summary['baskets'])
        }
        
        with open(summary_stats_file, 'w') as f:
            json.dump(json_summary, f, indent=2)
        
        print(f"  ✅ Basket summary saved to: {basket_file}")
        print(f"  ✅ Basket statistics saved to: {summary_stats_file}")
    
    def analyze_pattern_types(self, baskets: list) -> dict:
        """Analyze the distribution and performance of different pattern types."""
        pattern_stats = defaultdict(lambda: {
            'count': 0,
            'total_change': 0.0,
            'total_time': 0.0,
            'changes': [],
            'durations': []
        })
        
        for basket in baskets:
            pattern = basket['pattern_type']
            pattern_stats[pattern]['count'] += 1
            pattern_stats[pattern]['total_change'] += basket['price_change']
            pattern_stats[pattern]['total_time'] += basket['duration_minutes']
            pattern_stats[pattern]['changes'].append(basket['price_change'])
            pattern_stats[pattern]['durations'].append(basket['duration_minutes'])
        
        # Calculate derived statistics
        for pattern, stats in pattern_stats.items():
            if stats['count'] > 0:
                stats['avg_change'] = stats['total_change'] / stats['count']
                stats['avg_duration'] = stats['total_time'] / stats['count']
                
                if len(stats['changes']) > 1:
                    stats['change_std'] = np.std(stats['changes'])
                    stats['duration_std'] = np.std(stats['durations'])
                else:
                    stats['change_std'] = 0.0
                    stats['duration_std'] = 0.0
                
                # Remove raw lists for JSON serialization
                del stats['changes']
                del stats['durations']
        
        return dict(pattern_stats)
    
    def process_patterns_3min(self, df: pd.DataFrame, offset: int = 0) -> dict:
        """Process data in 3-minute chunks with specified offset."""
        pattern_buckets = defaultdict(lambda: {
            'occurrences': [],
            'total_change': 0.0,
            'count': 0,
            'total_volume': 0,
            'individual_changes': []
        })
        
        chunk_size = 3
        
        print(f"\n📊 Processing 3-minute patterns with offset {offset}...")
        
        # Apply offset
        df_offset = df.iloc[offset:].reset_index(drop=True)
        
        # Create pattern occurrences file
        occurrences_file = os.path.join(self.output_dir, f"pattern_occurrences_offset_{offset}.csv")
        occ_file = open(occurrences_file, 'w', newline='')
        occ_writer = csv.DictWriter(occ_file, fieldnames=[
            'pattern', 'timestamp', 'minute_1_time', 'minute_2_time', 'minute_3_time',
            'first_open', 'last_next_open', 'total_change', 
            'change_1', 'change_2', 'change_3', 'volume'
        ])
        occ_writer.writeheader()
        
        i = 0
        while i + chunk_size < len(df_offset):
            chunk_bars = df_offset.iloc[i:i + chunk_size]
            
            # Build pattern string
            pattern_chars = []
            individual_changes = []
            minute_timestamps = []
            
            for j in range(chunk_size):
                current_open = chunk_bars.iloc[j]['o']
                if j < chunk_size - 1:
                    next_open = chunk_bars.iloc[j + 1]['o']
                else:
                    next_open = df_offset.iloc[i + chunk_size]['o'] if i + chunk_size < len(df_offset) else chunk_bars.iloc[j]['c']
                
                classification = self.classify_candle(current_open, next_open)
                pattern_chars.append(classification)
                minute_timestamps.append(chunk_bars.iloc[j]['timestamp'])
                
                change = next_open - current_open
                individual_changes.append(change)
            
            pattern_string = ''.join(pattern_chars)
            
            # Calculate total change
            first_open = chunk_bars.iloc[0]['o']
            if i + chunk_size < len(df_offset):
                last_next_open = df_offset.iloc[i + chunk_size]['o']
                total_change = last_next_open - first_open
            else:
                last_next_open = chunk_bars.iloc[-1]['c']
                total_change = last_next_open - first_open
            
            # Calculate volume
            total_volume = chunk_bars['v'].sum()
            
            # Store pattern occurrence
            start_timestamp = chunk_bars.iloc[0]['timestamp']
            end_timestamp = chunk_bars.iloc[-1]['timestamp']
            
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
            occ_row = {
                'pattern': pattern_string,
                'timestamp': start_timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'minute_1_time': minute_timestamps[0].strftime('%H:%M:%S'),
                'minute_2_time': minute_timestamps[1].strftime('%H:%M:%S'),
                'minute_3_time': minute_timestamps[2].strftime('%H:%M:%S'),
                'first_open': f"{first_open:.4f}",
                'last_next_open': f"{last_next_open:.4f}",
                'total_change': f"{total_change:.4f}",
                'change_1': f"{individual_changes[0]:.4f}",
                'change_2': f"{individual_changes[1]:.4f}",
                'change_3': f"{individual_changes[2]:.4f}",
                'volume': total_volume
            }
            occ_writer.writerow(occ_row)
            
            i += chunk_size
        
        occ_file.close()
        print(f"  ✅ Pattern occurrences saved to: {occurrences_file}")
        
        return pattern_buckets
    
    def calculate_statistics(self, pattern_buckets: dict) -> None:
        """Calculate comprehensive statistics for each pattern."""
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
    
    def export_results(self, pattern_buckets: dict, offset: int) -> None:
        """Export analysis results for specific offset."""
        summary_file = os.path.join(self.output_dir, f"pattern_summary_offset_{offset}.csv")
        
        with open(summary_file, 'w', newline='') as csvfile:
            fieldnames = ['pattern', 'count', 'frequency_%', 'total_change', 'avg_change', 
                         'std_dev', 'min_change', 'max_change', 'win_rate', 
                         'return_risk_ratio', 'avg_volume']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            total_patterns = sum(b['count'] for b in pattern_buckets.values())
            
            for pattern, bucket in sorted(pattern_buckets.items(), 
                                         key=lambda x: x[1].get('avg_total_change', 0), 
                                         reverse=True):
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
        
        print(f"  ✅ Pattern summary saved to: {summary_file}")
    
    def run_analysis(self):
        """Main method to run the 3-minute pattern analysis."""
        print(f"\n{'='*80}")
        print(f"THREE-MINUTE PATTERN ANALYSIS")
        print(f"{'='*80}")
        print(f"Symbol: {self.symbol}")
        print(f"Output: {self.output_dir}")
        
        # Step 1: Load data
        df = self.load_fetched_data()
        
        # Step 2: Clean data
        df_cleaned, cleanup_summary = self.clean_data(df)
        
        if len(df_cleaned) < 4:
            print("❌ Insufficient data after cleanup")
            return None
        
        # Step 3: Analyze with different offsets
        print(f"\n{'='*60}")
        print("ANALYZING PATTERNS WITH OFFSETS")
        print(f"{'='*60}")
        
        offset_results = []
        for offset in range(3):
            print(f"\n▶ Offset {offset}:")
            
            # Process patterns
            pattern_buckets = self.process_patterns_3min(df_cleaned, offset)
            
            # Calculate statistics
            self.calculate_statistics(pattern_buckets)
            
            # Export results
            self.export_results(pattern_buckets, offset)
            
            # NEW: Create contiguous basket summary
            print(f"  📊 Creating contiguous basket analysis...")
            basket_summary = self.create_contiguous_basket_summary(df_cleaned, offset)
            self.export_basket_summary(basket_summary, offset)
            
            # Validation report for this offset
            change_valid = basket_summary['mathematical_consistency']['change_matches']
            time_valid = basket_summary['mathematical_consistency']['time_matches']
            print(f"  ✅ Mathematical validation: Changes {'✓' if change_valid else '✗'}, Times {'✓' if time_valid else '✗'}")
            print(f"  📈 Total baskets: {basket_summary['total_baskets']}, Change discrepancy: ${basket_summary['change_discrepancy']:.6f}")
            
            # Collect summary
            total_patterns = sum(b['count'] for b in pattern_buckets.values())
            unique_patterns = len([b for b in pattern_buckets.values() if b['count'] > 0])
            
            offset_results.append({
                'offset': offset,
                'total_patterns': int(total_patterns),
                'unique_patterns': int(unique_patterns),
                'total_baskets': int(basket_summary['total_baskets']),
                'change_discrepancy': float(basket_summary['change_discrepancy']),
                'mathematical_consistency': {
                    'change_matches': bool(basket_summary['mathematical_consistency']['change_matches']),
                    'time_matches': bool(basket_summary['mathematical_consistency']['time_matches'])
                },
                'top_pattern': max(pattern_buckets.items(), 
                                 key=lambda x: x[1].get('avg_total_change', 0))[0] if pattern_buckets else 'N/A'
            })
            
            print(f"  Found {unique_patterns} unique patterns from {total_patterns} occurrences")
        
        # Save final summary
        summary = {
            'symbol': self.symbol,
            'data_file': self.data_file,
            'analysis_timestamp': datetime.now().isoformat(),
            'bars_analyzed': len(df_cleaned),
            'date_range': {
                'start': str(df_cleaned['timestamp'].min()),
                'end': str(df_cleaned['timestamp'].max())
            },
            'offset_results': offset_results
        }
        
        summary_file = os.path.join(self.output_dir, 'analysis_summary.json')
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"\n{'='*80}")
        print("ANALYSIS COMPLETE")
        print(f"{'='*80}")
        print(f"✅ All results saved to: {self.output_dir}")
        print(f"✅ Summary saved to: {summary_file}")
        
        return self.output_dir


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Analyze 3-minute patterns in fetched stock data')
    parser.add_argument('--data', required=True, help='Path to fetched CSV data file')
    parser.add_argument('--output', help='Output directory (auto-generated if not specified)')
    
    args = parser.parse_args()
    
    # Validate input file exists
    if not os.path.exists(args.data):
        print(f"Error: Data file not found: {args.data}")
        return 1
    
    try:
        # Run analysis
        analyzer = ThreeMinutePatternAnalyzer(args.data, args.output)
        output_dir = analyzer.run_analysis()
        
        if output_dir:
            print(f"\n✅ Success! Analysis results saved to: {output_dir}")
            print("\nNext steps:")
            print(f"1. Validate results: python validate_patterns.py {output_dir} {analyzer.symbol}")
            print(f"2. Create visualizations: python visualize_patterns.py {output_dir}")
            return 0
        else:
            return 1
            
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())