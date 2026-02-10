"""
Pattern Visualization Tool - Enhanced with Basket Analysis
Creates comprehensive visualizations for 3-minute pattern analysis results
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import json
import os
import argparse
from datetime import datetime
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

class PatternVisualizer:
    def __init__(self, analysis_dir: str):
        """Initialize visualizer with analysis directory."""
        self.analysis_dir = analysis_dir
        self.symbol = self.extract_symbol_from_dir(analysis_dir)
        self.viz_dir = os.path.join(analysis_dir, "visualizations")
        os.makedirs(self.viz_dir, exist_ok=True)
        
        # Set up plotting style
        plt.style.use('default')
        sns.set_palette("husl")
        
    def extract_symbol_from_dir(self, dir_path: str) -> str:
        """Extract symbol from analysis directory name."""
        dir_name = os.path.basename(dir_path)
        # Format: SYMBOL_TIMESTAMP
        return dir_name.split('_')[0]
    
    def load_analysis_data(self, offset: int) -> tuple:
        """Load all analysis data for a specific offset."""
        try:
            # Pattern summary
            pattern_file = os.path.join(self.analysis_dir, f"pattern_summary_offset_{offset}.csv")
            pattern_df = pd.read_csv(pattern_file) if os.path.exists(pattern_file) else None
            
            # Pattern occurrences
            occurrences_file = os.path.join(self.analysis_dir, f"pattern_occurrences_offset_{offset}.csv")
            occurrences_df = pd.read_csv(occurrences_file) if os.path.exists(occurrences_file) else None
            if occurrences_df is not None:
                occurrences_df['timestamp'] = pd.to_datetime(occurrences_df['timestamp'])
            
            # Basket summary
            basket_file = os.path.join(self.analysis_dir, f"basket_summary_offset_{offset}.csv")
            basket_df = pd.read_csv(basket_file) if os.path.exists(basket_file) else None
            if basket_df is not None:
                basket_df['start_time'] = pd.to_datetime(basket_df['start_time'])
                basket_df['end_time'] = pd.to_datetime(basket_df['end_time'])
            
            # Basket statistics
            basket_stats_file = os.path.join(self.analysis_dir, f"basket_statistics_offset_{offset}.json")
            basket_stats = None
            if os.path.exists(basket_stats_file):
                with open(basket_stats_file, 'r') as f:
                    basket_stats = json.load(f)
            
            return pattern_df, occurrences_df, basket_df, basket_stats
            
        except Exception as e:
            print(f"Error loading data for offset {offset}: {e}")
            return None, None, None, None
    
    def create_pattern_performance_chart(self):
        """Create pattern performance comparison across all offsets."""
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle(f'{self.symbol} - Pattern Performance Analysis', fontsize=16, fontweight='bold')
        
        all_patterns = set()
        offset_data = {}
        
        # Collect data from all offsets
        for offset in range(3):
            pattern_df, _, _, _ = self.load_analysis_data(offset)
            if pattern_df is not None:
                offset_data[offset] = pattern_df
                all_patterns.update(pattern_df['pattern'].tolist())
        
        # Top patterns by average change
        ax1 = axes[0, 0]
        for offset, df in offset_data.items():
            top_patterns = df.nlargest(10, 'avg_change')
            ax1.barh(range(len(top_patterns)), top_patterns['avg_change'], 
                    alpha=0.7, label=f'Offset {offset}')
            ax1.set_yticks(range(len(top_patterns)))
            ax1.set_yticklabels(top_patterns['pattern'])
        ax1.set_xlabel('Average Change ($)')
        ax1.set_title('Top 10 Patterns by Average Change')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Pattern frequency distribution
        ax2 = axes[0, 1]
        pattern_counts = defaultdict(int)
        for offset, df in offset_data.items():
            for _, row in df.iterrows():
                pattern_counts[row['pattern']] += row['count']
        
        top_frequent = sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)[:15]
        patterns, counts = zip(*top_frequent)
        ax2.bar(patterns, counts, alpha=0.7)
        ax2.set_xlabel('Pattern')
        ax2.set_ylabel('Total Occurrences')
        ax2.set_title('Most Frequent Patterns (All Offsets)')
        ax2.tick_params(axis='x', rotation=45)
        ax2.grid(True, alpha=0.3)
        
        # Win rate vs Return scatter
        ax3 = axes[1, 0]
        for offset, df in offset_data.items():
            # Convert win_rate from percentage string to float
            win_rates = []
            avg_changes = []
            for _, row in df.iterrows():
                try:
                    win_rate = float(row['win_rate'].replace('%', '')) / 100
                    win_rates.append(win_rate)
                    avg_changes.append(row['avg_change'])
                except:
                    continue
            
            ax3.scatter(win_rates, avg_changes, alpha=0.6, label=f'Offset {offset}', s=30)
        
        ax3.set_xlabel('Win Rate')
        ax3.set_ylabel('Average Change ($)')
        ax3.set_title('Win Rate vs Average Return')
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        ax3.axhline(y=0, color='red', linestyle='--', alpha=0.5)
        ax3.axvline(x=0.5, color='red', linestyle='--', alpha=0.5)
        
        # Return vs Risk scatter
        ax4 = axes[1, 1]
        for offset, df in offset_data.items():
            ax4.scatter(df['std_dev'], df['avg_change'], alpha=0.6, 
                       label=f'Offset {offset}', s=30)
        
        ax4.set_xlabel('Standard Deviation ($)')
        ax4.set_ylabel('Average Change ($)')
        ax4.set_title('Return vs Risk Profile')
        ax4.legend()
        ax4.grid(True, alpha=0.3)
        ax4.axhline(y=0, color='red', linestyle='--', alpha=0.5)
        
        plt.tight_layout()
        output_file = os.path.join(self.viz_dir, 'pattern_performance_analysis.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"Pattern performance chart saved to: {output_file}")
    
    def create_basket_analysis_charts(self):
        """Create comprehensive basket analysis visualizations."""
        fig, axes = plt.subplots(3, 2, figsize=(16, 18))
        fig.suptitle(f'{self.symbol} - Contiguous Basket Analysis', fontsize=16, fontweight='bold')
        
        for offset in range(3):
            _, _, basket_df, basket_stats = self.load_analysis_data(offset)
            
            if basket_df is None or basket_stats is None:
                continue
            
            row = offset
            
            # Cumulative price change over time
            ax1 = axes[row, 0]
            cumulative_change = basket_df['price_change'].cumsum()
            ax1.plot(basket_df['basket_id'], cumulative_change, 'b-', linewidth=2, marker='o', markersize=3)
            ax1.set_xlabel('Basket ID')
            ax1.set_ylabel('Cumulative Price Change ($)')
            ax1.set_title(f'Offset {offset}: Cumulative Price Change')
            ax1.grid(True, alpha=0.3)
            ax1.axhline(y=0, color='red', linestyle='--', alpha=0.5)
            
            # Add mathematical validation info
            consistency = basket_stats['mathematical_consistency']
            status_text = f"Valid: Changes {'✓' if consistency['change_matches'] else '✗'}, Times {'✓' if consistency['time_matches'] else '✗'}"
            ax1.text(0.02, 0.98, status_text, transform=ax1.transAxes, 
                    bbox=dict(boxstyle='round', facecolor='lightgreen' if all(consistency.values()) else 'lightcoral'),
                    verticalalignment='top', fontsize=9)
            
            # Pattern type performance
            ax2 = axes[row, 1]
            pattern_breakdown = basket_stats['pattern_type_breakdown']
            
            if pattern_breakdown:
                patterns = list(pattern_breakdown.keys())
                avg_changes = [pattern_breakdown[p]['avg_change'] for p in patterns]
                counts = [pattern_breakdown[p]['count'] for p in patterns]
                
                # Create bubble chart - size represents frequency
                scatter = ax2.scatter(range(len(patterns)), avg_changes, s=[c*10 for c in counts], 
                                    alpha=0.6, c=avg_changes, cmap='RdYlGn')
                ax2.set_xticks(range(len(patterns)))
                ax2.set_xticklabels(patterns, rotation=45)
                ax2.set_ylabel('Average Change ($)')
                ax2.set_title(f'Offset {offset}: Pattern Performance (Size = Frequency)')
                ax2.grid(True, alpha=0.3)
                ax2.axhline(y=0, color='red', linestyle='--', alpha=0.5)
                
                # Add colorbar
                cbar = plt.colorbar(scatter, ax=ax2)
                cbar.set_label('Avg Change ($)')
        
        plt.tight_layout()
        output_file = os.path.join(self.viz_dir, 'basket_analysis_charts.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"Basket analysis charts saved to: {output_file}")
    
    def create_pattern_heatmap(self):
        """Create heatmap showing pattern performance across different metrics."""
        fig, axes = plt.subplots(1, 3, figsize=(20, 6))
        fig.suptitle(f'{self.symbol} - Pattern Performance Heatmaps', fontsize=16, fontweight='bold')
        
        for offset in range(3):
            pattern_df, _, _, _ = self.load_analysis_data(offset)
            
            if pattern_df is None:
                continue
            
            ax = axes[offset]
            
            # Prepare data for heatmap
            patterns = pattern_df['pattern'].tolist()
            metrics = ['avg_change', 'std_dev', 'count']
            
            heatmap_data = []
            for metric in metrics:
                if metric == 'win_rate':
                    # Convert percentage string to float
                    values = [float(str(val).replace('%', '')) / 100 for val in pattern_df[metric]]
                else:
                    values = pattern_df[metric].tolist()
                heatmap_data.append(values)
            
            heatmap_array = np.array(heatmap_data)
            
            # Normalize each metric to 0-1 scale for better visualization
            for i in range(len(metrics)):
                if heatmap_array[i].std() > 0:
                    heatmap_array[i] = (heatmap_array[i] - heatmap_array[i].min()) / (heatmap_array[i].max() - heatmap_array[i].min())
            
            # Create heatmap
            im = ax.imshow(heatmap_array, cmap='RdYlGn', aspect='auto')
            
            # Set labels
            ax.set_xticks(range(len(patterns)))
            ax.set_xticklabels(patterns, rotation=45)
            ax.set_yticks(range(len(metrics)))
            ax.set_yticklabels(['Avg Change', 'Std Dev', 'Count'])
            ax.set_title(f'Offset {offset} - Pattern Metrics (Normalized)')
            
            # Add colorbar
            plt.colorbar(im, ax=ax)
        
        plt.tight_layout()
        output_file = os.path.join(self.viz_dir, 'pattern_heatmaps.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"Pattern heatmaps saved to: {output_file}")
    
    def create_time_series_analysis(self):
        """Create time series analysis of pattern occurrences."""
        fig, axes = plt.subplots(3, 1, figsize=(16, 12))
        fig.suptitle(f'{self.symbol} - Pattern Time Series Analysis', fontsize=16, fontweight='bold')
        
        for offset in range(3):
            _, occurrences_df, basket_df, _ = self.load_analysis_data(offset)
            
            if occurrences_df is None or basket_df is None:
                continue
            
            ax = axes[offset]
            
            # Plot cumulative returns over time
            occurrences_df_sorted = occurrences_df.sort_values('timestamp')
            cumulative_returns = occurrences_df_sorted['total_change'].cumsum()
            
            ax.plot(occurrences_df_sorted['timestamp'], cumulative_returns, 'b-', linewidth=1.5, alpha=0.8)
            ax.fill_between(occurrences_df_sorted['timestamp'], cumulative_returns, 0, alpha=0.3)
            
            # Overlay basket boundaries
            for _, basket in basket_df.iterrows():
                ax.axvline(x=basket['start_time'], color='red', alpha=0.3, linewidth=0.5)
            
            ax.set_xlabel('Time')
            ax.set_ylabel('Cumulative Returns ($)')
            ax.set_title(f'Offset {offset}: Cumulative Returns Over Time')
            ax.grid(True, alpha=0.3)
            ax.axhline(y=0, color='black', linestyle='-', alpha=0.5)
            
            # Add summary statistics
            total_return = cumulative_returns.iloc[-1] if len(cumulative_returns) > 0 else 0
            max_drawdown = (cumulative_returns - cumulative_returns.expanding().max()).min()
            
            stats_text = f"Total Return: ${total_return:.4f}\nMax Drawdown: ${max_drawdown:.4f}"
            ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, 
                   bbox=dict(boxstyle='round', facecolor='lightblue'),
                   verticalalignment='top', fontsize=9)
        
        plt.tight_layout()
        output_file = os.path.join(self.viz_dir, 'time_series_analysis.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"Time series analysis saved to: {output_file}")
    
    def create_validation_dashboard(self):
        """Create comprehensive validation dashboard."""
        fig, axes = plt.subplots(2, 3, figsize=(18, 12))
        fig.suptitle(f'{self.symbol} - Mathematical Validation Dashboard', fontsize=16, fontweight='bold')
        
        validation_data = []
        
        for offset in range(3):
            _, _, basket_df, basket_stats = self.load_analysis_data(offset)
            
            if basket_df is None or basket_stats is None:
                continue
            
            # Collect validation metrics
            validation_data.append({
                'offset': offset,
                'total_baskets': basket_stats['total_baskets'],
                'change_discrepancy': basket_stats['change_discrepancy'],
                'time_discrepancy': basket_stats['time_discrepancy'],
                'change_valid': basket_stats['mathematical_consistency']['change_matches'],
                'time_valid': basket_stats['mathematical_consistency']['time_matches'],
                'accounted_change': basket_stats['accounted_total_change'],
                'actual_change': basket_stats['actual_total_change']
            })
            
            # Individual basket change distribution
            ax = axes[0, offset]
            ax.hist(basket_df['price_change'], bins=30, alpha=0.7, edgecolor='black')
            ax.set_xlabel('Basket Price Change ($)')
            ax.set_ylabel('Frequency')
            ax.set_title(f'Offset {offset}: Basket Change Distribution')
            ax.grid(True, alpha=0.3)
            ax.axvline(x=0, color='red', linestyle='--', alpha=0.7)
            
            # Add statistics
            mean_change = basket_df['price_change'].mean()
            std_change = basket_df['price_change'].std()
            ax.text(0.02, 0.98, f'Mean: ${mean_change:.6f}\nStd: ${std_change:.6f}', 
                   transform=ax.transAxes, bbox=dict(boxstyle='round', facecolor='lightblue'),
                   verticalalignment='top', fontsize=9)
        
        # Summary validation metrics
        if validation_data:
            # Discrepancy comparison
            ax = axes[1, 0]
            offsets = [d['offset'] for d in validation_data]
            change_discrepancies = [abs(d['change_discrepancy']) for d in validation_data]
            time_discrepancies = [d['time_discrepancy'] for d in validation_data]
            
            x = np.arange(len(offsets))
            width = 0.35
            
            ax.bar(x - width/2, change_discrepancies, width, label='Change Discrepancy', alpha=0.7)
            ax.bar(x + width/2, time_discrepancies, width, label='Time Discrepancy', alpha=0.7)
            
            ax.set_xlabel('Offset')
            ax.set_ylabel('Discrepancy (absolute)')
            ax.set_title('Validation Discrepancies by Offset')
            ax.set_xticks(x)
            ax.set_xticklabels(offsets)
            ax.legend()
            ax.grid(True, alpha=0.3)
            
            # Validation status
            ax = axes[1, 1]
            change_valid_count = sum(1 for d in validation_data if d['change_valid'])
            time_valid_count = sum(1 for d in validation_data if d['time_valid'])
            
            categories = ['Change Validation', 'Time Validation']
            valid_counts = [change_valid_count, time_valid_count]
            invalid_counts = [len(validation_data) - change_valid_count, len(validation_data) - time_valid_count]
            
            x = np.arange(len(categories))
            ax.bar(x, valid_counts, label='Valid', color='green', alpha=0.7)
            ax.bar(x, invalid_counts, bottom=valid_counts, label='Invalid', color='red', alpha=0.7)
            
            ax.set_ylabel('Count')
            ax.set_title('Validation Status Summary')
            ax.set_xticks(x)
            ax.set_xticklabels(categories)
            ax.legend()
            
            # Accounted vs Actual comparison
            ax = axes[1, 2]
            accounted_changes = [d['accounted_change'] for d in validation_data]
            actual_changes = [d['actual_change'] for d in validation_data]
            
            ax.scatter(actual_changes, accounted_changes, s=100, alpha=0.7)
            
            # Add perfect correlation line
            min_val = min(min(actual_changes), min(accounted_changes))
            max_val = max(max(actual_changes), max(accounted_changes))
            ax.plot([min_val, max_val], [min_val, max_val], 'r--', alpha=0.7, label='Perfect Match')
            
            ax.set_xlabel('Actual Total Change ($)')
            ax.set_ylabel('Accounted Total Change ($)')
            ax.set_title('Accounted vs Actual Change')
            ax.legend()
            ax.grid(True, alpha=0.3)
            
            # Add correlation coefficient
            correlation = np.corrcoef(actual_changes, accounted_changes)[0, 1]
            ax.text(0.02, 0.98, f'Correlation: {correlation:.6f}', 
                   transform=ax.transAxes, bbox=dict(boxstyle='round', facecolor='lightgreen'),
                   verticalalignment='top', fontsize=9)
        
        plt.tight_layout()
        output_file = os.path.join(self.viz_dir, 'validation_dashboard.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"Validation dashboard saved to: {output_file}")
    
    def create_summary_report(self):
        """Create a summary report with key findings."""
        report_file = os.path.join(self.viz_dir, 'visualization_summary.txt')
        
        with open(report_file, 'w') as f:
            f.write("="*80 + "\n")
            f.write("PATTERN ANALYSIS VISUALIZATION SUMMARY\n")
            f.write("="*80 + "\n")
            f.write(f"Symbol: {self.symbol}\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Analysis Directory: {self.analysis_dir}\n\n")
            
            f.write("GENERATED VISUALIZATIONS:\n")
            f.write("-"*50 + "\n")
            f.write("1. pattern_performance_analysis.png - Pattern performance comparison\n")
            f.write("2. basket_analysis_charts.png - Contiguous basket analysis\n")
            f.write("3. pattern_heatmaps.png - Pattern metric heatmaps\n")
            f.write("4. time_series_analysis.png - Time series of returns\n")
            f.write("5. validation_dashboard.png - Mathematical validation dashboard\n\n")
            
            # Add key statistics
            f.write("KEY FINDINGS SUMMARY:\n")
            f.write("-"*50 + "\n")
            
            total_baskets = 0
            total_patterns = 0
            all_valid = True
            
            for offset in range(3):
                pattern_df, _, _, basket_stats = self.load_analysis_data(offset)
                
                if pattern_df is not None and basket_stats is not None:
                    f.write(f"\nOffset {offset}:\n")
                    f.write(f"  Total Patterns: {len(pattern_df)}\n")
                    f.write(f"  Total Baskets: {basket_stats['total_baskets']}\n")
                    f.write(f"  Change Discrepancy: ${basket_stats['change_discrepancy']:.6f}\n")
                    f.write(f"  Mathematical Validation: {basket_stats['mathematical_consistency']}\n")
                    
                    # Best performing pattern
                    best_pattern = pattern_df.loc[pattern_df['avg_change'].idxmax()]
                    f.write(f"  Best Pattern: {best_pattern['pattern']} (${best_pattern['avg_change']:.6f})\n")
                    
                    total_baskets += basket_stats['total_baskets']
                    total_patterns += len(pattern_df)
                    
                    if not all(basket_stats['mathematical_consistency'].values()):
                        all_valid = False
            
            f.write(f"\nOVERALL SUMMARY:\n")
            f.write(f"Total Unique Patterns Across All Offsets: {total_patterns}\n")
            f.write(f"Total Baskets Analyzed: {total_baskets}\n")
            f.write(f"Mathematical Validation Status: {'PASSED' if all_valid else 'FAILED'}\n")
            
            f.write(f"\nNext Steps:\n")
            f.write("1. Review validation dashboard for any mathematical inconsistencies\n")
            f.write("2. Analyze pattern performance charts for trading opportunities\n")
            f.write("3. Examine time series analysis for market timing insights\n")
            f.write("4. Consider statistical significance of pattern frequencies\n")
        
        print(f"Summary report saved to: {report_file}")
    
    def generate_all_visualizations(self):
        """Generate all visualization charts and reports."""
        print(f"\n{'='*60}")
        print("GENERATING PATTERN VISUALIZATIONS")
        print(f"{'='*60}")
        print(f"Symbol: {self.symbol}")
        print(f"Output Directory: {self.viz_dir}")
        
        try:
            self.create_pattern_performance_chart()
            self.create_basket_analysis_charts()
            self.create_pattern_heatmap()
            self.create_time_series_analysis()
            self.create_validation_dashboard()
            self.create_summary_report()
            
            print(f"\n{'='*60}")
            print("VISUALIZATION COMPLETE")
            print(f"{'='*60}")
            print(f"All visualizations saved to: {self.viz_dir}")
            
        except Exception as e:
            print(f"Error generating visualizations: {e}")
            import traceback
            traceback.print_exc()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Create visualizations for pattern analysis results')
    parser.add_argument('analysis_dir', help='Path to analysis results directory')
    
    args = parser.parse_args()
    
    if not os.path.isdir(args.analysis_dir):
        print(f"Error: Analysis directory not found: {args.analysis_dir}")
        return 1
    
    try:
        visualizer = PatternVisualizer(args.analysis_dir)
        visualizer.generate_all_visualizations()
        return 0
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())