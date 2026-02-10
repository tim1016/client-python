import pandas as pd
import numpy as np
import os
import csv
from datetime import datetime
import matplotlib.pyplot as plt

class ThreeMinutePatternValidator:
    def __init__(self, base_dir):
        """Initialize validator with the analysis directory."""
        self.base_dir = base_dir
        self.validation_results = {}
        
    def load_cleaned_data(self, symbol):
        """Load the cleaned data file."""
        cleaned_file = os.path.join(self.base_dir, f"cleaned_{symbol}.csv")
        if not os.path.exists(cleaned_file):
            raise FileNotFoundError(f"Cleaned data file not found: {cleaned_file}")
        
        df = pd.read_csv(cleaned_file)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    
    def validate_pattern_changes(self, df, offset=0):
        """
        Validate that the sum of pattern changes equals the total price change.
        
        The validation checks:
        1. Sum of open-to-open changes in 3-minute chunks
        2. Gap changes between chunks
        3. Total should equal: last_close - first_open
        """
        print(f"\n{'='*80}")
        print(f"VALIDATING OFFSET {offset}")
        print(f"{'='*80}")
        
        # Apply offset
        df_offset = df.iloc[offset:].reset_index(drop=True)
        
        if len(df_offset) < 4:  # Need at least 4 candles for one pattern
            print(f"Insufficient data for offset {offset}")
            return None
        
        # Track all changes
        pattern_changes = []
        gap_changes = []
        pattern_details = []
        
        # Process in 3-minute chunks
        chunk_size = 3
        i = 0
        
        while i + chunk_size < len(df_offset):
            chunk = df_offset.iloc[i:i+chunk_size]
            
            # Pattern changes: open-to-open within the chunk
            pattern_change_sum = 0
            chunk_changes = []
            
            for j in range(chunk_size):
                if j < chunk_size - 1:
                    # Change from current open to next open
                    change = chunk.iloc[j+1]['o'] - chunk.iloc[j]['o']
                else:
                    # Last candle: change from open to next chunk's open (if exists)
                    if i + chunk_size < len(df_offset):
                        change = df_offset.iloc[i+chunk_size]['o'] - chunk.iloc[j]['o']
                    else:
                        # If no next chunk, use close of last candle
                        change = chunk.iloc[j]['c'] - chunk.iloc[j]['o']
                
                chunk_changes.append(change)
                pattern_change_sum += change
            
            pattern_changes.append(pattern_change_sum)
            
            # Store pattern details
            pattern_details.append({
                'chunk_index': i // chunk_size,
                'start_idx': i,
                'end_idx': i + chunk_size - 1,
                'first_open': chunk.iloc[0]['o'],
                'last_open': chunk.iloc[-1]['o'],
                'next_open': df_offset.iloc[i+chunk_size]['o'] if i+chunk_size < len(df_offset) else chunk.iloc[-1]['c'],
                'pattern_change': pattern_change_sum,
                'individual_changes': chunk_changes,
                'timestamp': chunk.iloc[0]['timestamp']
            })
            
            # Gap change (if there's a gap between chunks due to missing data)
            # This would be 0 in continuous data
            if i + chunk_size < len(df_offset):
                # Check if there's a time gap
                current_end_time = chunk.iloc[-1]['timestamp']
                next_start_time = df_offset.iloc[i+chunk_size]['timestamp']
                time_diff = (next_start_time - current_end_time).total_seconds() / 60
                
                if time_diff > 1:  # More than 1 minute gap
                    # There's a gap - but in price terms, this is already accounted for
                    # in the next pattern's first open
                    gap_changes.append(0)  # Price continuity is maintained
                else:
                    gap_changes.append(0)
            
            i += chunk_size
        
        # Calculate totals
        total_pattern_changes = sum(pattern_changes)
        total_gap_changes = sum(gap_changes)
        
        # Actual change in the data
        first_open = df_offset.iloc[0]['o']
        last_close = df_offset.iloc[-1]['c']
        actual_total_change = last_close - first_open
        
        # Account for the remainder (bars not included in complete patterns)
        remainder_bars = len(df_offset) % chunk_size
        remainder_change = 0
        if remainder_bars > 0:
            # Change from the last complete chunk to the end
            last_chunk_end = (len(df_offset) // chunk_size) * chunk_size
            if last_chunk_end < len(df_offset):
                remainder_start = df_offset.iloc[last_chunk_end]['o']
                remainder_end = df_offset.iloc[-1]['c']
                remainder_change = remainder_end - remainder_start
        
        # Total accounted change
        total_accounted = total_pattern_changes + total_gap_changes + remainder_change
        
        # Validation check
        discrepancy = abs(actual_total_change - total_accounted)
        validation_passed = discrepancy < 0.0001  # Small tolerance for floating point
        
        # Store results
        validation_result = {
            'offset': offset,
            'num_patterns': len(pattern_changes),
            'pattern_changes_sum': total_pattern_changes,
            'gap_changes_sum': total_gap_changes,
            'remainder_change': remainder_change,
            'total_accounted': total_accounted,
            'actual_change': actual_total_change,
            'discrepancy': discrepancy,
            'validation_passed': validation_passed,
            'pattern_details': pattern_details
        }
        
        # Print results
        print(f"\nValidation Results for Offset {offset}:")
        print(f"{'='*60}")
        print(f"Number of complete 3-minute patterns: {len(pattern_changes)}")
        print(f"Sum of pattern changes: ${total_pattern_changes:.6f}")
        print(f"Sum of gap changes: ${total_gap_changes:.6f}")
        print(f"Remainder change: ${remainder_change:.6f}")
        print(f"Total accounted: ${total_accounted:.6f}")
        print(f"Actual price change: ${actual_total_change:.6f}")
        print(f"Discrepancy: ${discrepancy:.6f}")
        print(f"Validation: {'✅ PASSED' if validation_passed else '❌ FAILED'}")
        
        if not validation_passed:
            print(f"\n⚠️ Warning: Discrepancy of ${discrepancy:.6f} detected!")
        
        return validation_result
    
    def compare_with_analysis_results(self, symbol, offset=0):
        """Compare validation with the original analysis results."""
        # Load pattern summary from analysis
        summary_file = os.path.join(self.base_dir, f"pattern_summary_offset_{offset}.csv")
        if not os.path.exists(summary_file):
            print(f"Pattern summary not found for offset {offset}")
            return None
        
        summary_df = pd.read_csv(summary_file)
        
        # Calculate total from pattern analysis
        analysis_total = summary_df['total_change'].sum()
        analysis_count = summary_df['count'].sum()
        
        print(f"\n{'='*60}")
        print(f"Comparison with Original Analysis (Offset {offset}):")
        print(f"{'='*60}")
        print(f"Analysis total change: ${analysis_total:.6f}")
        print(f"Analysis pattern count: {analysis_count}")
        
        if offset in self.validation_results:
            val_result = self.validation_results[offset]
            print(f"Validation total change: ${val_result['pattern_changes_sum']:.6f}")
            print(f"Validation pattern count: {val_result['num_patterns']}")
            
            # Check consistency
            count_match = analysis_count == val_result['num_patterns']
            total_match = abs(analysis_total - val_result['pattern_changes_sum']) < 0.0001
            
            print(f"\nConsistency Check:")
            print(f"Pattern count matches: {'✅' if count_match else '❌'}")
            print(f"Total change matches: {'✅' if total_match else '❌'}")
    
    def create_validation_visualization(self, symbol):
        """Create visualization showing the validation results."""
        df = self.load_cleaned_data(symbol)
        
        fig, axes = plt.subplots(3, 1, figsize=(15, 12))
        
        for offset in range(3):
            ax = axes[offset]
            
            if offset not in self.validation_results:
                continue
            
            val_result = self.validation_results[offset]
            pattern_details = val_result['pattern_details']
            
            # Calculate cumulative changes
            cumulative_pattern = [0]
            cumulative_sum = 0
            
            for detail in pattern_details:
                cumulative_sum += detail['pattern_change']
                cumulative_pattern.append(cumulative_sum)
            
            # Add remainder if any
            cumulative_sum += val_result['remainder_change']
            cumulative_pattern.append(cumulative_sum)
            
            # Create x-axis (pattern indices)
            x_pattern = list(range(len(cumulative_pattern)))
            
            # Actual price line (normalized to start at 0)
            df_offset = df.iloc[offset:].reset_index(drop=True)
            actual_prices = df_offset['o'].values
            actual_changes = actual_prices - actual_prices[0]
            
            # Plot both lines
            ax.plot(x_pattern, cumulative_pattern, 'b-', linewidth=2, 
                   label='Cumulative Pattern Changes', marker='o', markersize=4)
            
            # Sample actual prices to match pattern points
            sample_indices = [i*3 for i in range(len(pattern_details)+1) if i*3 < len(actual_changes)]
            sampled_actual = [actual_changes[i] if i < len(actual_changes) else actual_changes[-1] 
                             for i in sample_indices]
            
            ax.plot(range(len(sampled_actual)), sampled_actual, 'r--', linewidth=2, 
                   label='Actual Price Changes', marker='s', markersize=4)
            
            # Add validation status
            status = '✅ PASSED' if val_result['validation_passed'] else '❌ FAILED'
            ax.text(0.02, 0.98, f'Validation: {status}\nDiscrepancy: ${val_result["discrepancy"]:.6f}',
                   transform=ax.transAxes, fontsize=10, verticalalignment='top',
                   bbox=dict(boxstyle='round', facecolor='lightgreen' if val_result['validation_passed'] else 'lightcoral'))
            
            ax.set_xlabel('Pattern Index')
            ax.set_ylabel('Cumulative Change ($)')
            ax.set_title(f'Offset {offset}: Pattern Change Validation')
            ax.legend()
            ax.grid(True, alpha=0.3)
            ax.axhline(y=0, color='black', linestyle='-', alpha=0.3)
        
        plt.suptitle(f'Three-Minute Pattern Validation for {symbol}', fontsize=14, fontweight='bold')
        plt.tight_layout()
        
        output_file = os.path.join(self.base_dir, 'pattern_validation_chart.png')
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"\n✅ Validation chart saved to: {output_file}")
    
    def export_validation_report(self, symbol):
        """Export detailed validation report."""
        report_file = os.path.join(self.base_dir, 'validation_report.txt')
        
        with open(report_file, 'w') as f:
            f.write("="*80 + "\n")
            f.write("THREE-MINUTE PATTERN VALIDATION REPORT\n")
            f.write("="*80 + "\n")
            f.write(f"Symbol: {symbol}\n")
            f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Analysis Directory: {self.base_dir}\n")
            f.write("\n")
            
            # Summary table
            f.write("VALIDATION SUMMARY\n")
            f.write("-"*80 + "\n")
            f.write(f"{'Offset':<10} {'Patterns':<10} {'Pattern Δ':<15} {'Actual Δ':<15} {'Discrepancy':<15} {'Status':<10}\n")
            f.write("-"*80 + "\n")
            
            all_passed = True
            for offset in range(3):
                if offset in self.validation_results:
                    r = self.validation_results[offset]
                    status = 'PASSED' if r['validation_passed'] else 'FAILED'
                    if not r['validation_passed']:
                        all_passed = False
                    
                    f.write(f"{offset:<10} {r['num_patterns']:<10} "
                           f"${r['pattern_changes_sum']:<14.6f} "
                           f"${r['actual_change']:<14.6f} "
                           f"${r['discrepancy']:<14.6f} "
                           f"{status:<10}\n")
            
            f.write("\n")
            f.write("OVERALL VALIDATION: " + ('✅ ALL OFFSETS PASSED' if all_passed else '⚠️ SOME OFFSETS FAILED') + "\n")
            
            # Detailed breakdown for each offset
            f.write("\n" + "="*80 + "\n")
            f.write("DETAILED PATTERN BREAKDOWN\n")
            f.write("="*80 + "\n")
            
            for offset in range(3):
                if offset in self.validation_results:
                    r = self.validation_results[offset]
                    f.write(f"\nOffset {offset}:\n")
                    f.write("-"*40 + "\n")
                    
                    # First 5 patterns as examples
                    for i, detail in enumerate(r['pattern_details'][:5]):
                        f.write(f"Pattern {i+1}: ")
                        f.write(f"Change=${detail['pattern_change']:.6f}, ")
                        f.write(f"Changes={[f'{c:.4f}' for c in detail['individual_changes']]}\n")
                    
                    if len(r['pattern_details']) > 5:
                        f.write(f"... and {len(r['pattern_details'])-5} more patterns\n")
        
        print(f"✅ Validation report saved to: {report_file}")
    
    def run_complete_validation(self, symbol):
        """Run complete validation for all offsets."""
        print("\n" + "="*80)
        print("RUNNING COMPLETE THREE-MINUTE PATTERN VALIDATION")
        print("="*80)
        
        # Load data
        df = self.load_cleaned_data(symbol)
        print(f"Loaded {len(df)} cleaned bars for {symbol}")
        
        # Validate each offset
        for offset in range(3):
            result = self.validate_pattern_changes(df, offset)
            if result:
                self.validation_results[offset] = result
                self.compare_with_analysis_results(symbol, offset)
        
        # Create visualization
        print("\n📊 Creating validation visualization...")
        self.create_validation_visualization(symbol)
        
        # Export report
        print("\n📄 Exporting validation report...")
        self.export_validation_report(symbol)
        
        # Final summary
        print("\n" + "="*80)
        print("VALIDATION COMPLETE")
        print("="*80)
        
        all_passed = all(r['validation_passed'] for r in self.validation_results.values())
        if all_passed:
            print("✅ All offsets passed validation!")
            print("The three-minute pattern model correctly accounts for all price changes.")
        else:
            failed_offsets = [o for o, r in self.validation_results.items() if not r['validation_passed']]
            print(f"⚠️ Validation failed for offsets: {failed_offsets}")
            print("Review the validation report for details.")

def main():
    """Main execution function."""
    import sys
    
    if len(sys.argv) != 3:
        print("Usage: python validate_patterns.py <analysis_directory> <symbol>")
        print("Example: python validate_patterns.py analysis_results/SPY_20241201_143022 SPY")
        sys.exit(1)
    
    base_dir = sys.argv[1]
    symbol = sys.argv[2]
    
    if not os.path.isdir(base_dir):
        print(f"Error: Directory not found: {base_dir}")
        sys.exit(1)
    
    validator = ThreeMinutePatternValidator(base_dir)
    validator.run_complete_validation(symbol)

if __name__ == "__main__":
    main()