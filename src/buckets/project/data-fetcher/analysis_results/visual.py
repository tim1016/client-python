"""
Three-Minute Pattern Visualizer - Updated Version
Creates comprehensive visualizations for pattern analysis results
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import json
import os
import argparse
from matplotlib.patches import Rectangle
from matplotlib.gridspec import GridSpec
from datetime import datetime

class ThreeMinutePatternVisualizer:
    def __init__(self, analysis_dir: str):
        """Initialize visualizer with analysis directory."""
        self.analysis_dir = analysis_dir
        self.output_dir = os.path.join(analysis_dir, 'visualizations')
        os.makedirs(self.output_dir, exist_ok=True)
        self.setup_style()
        self.load_analysis_info()
        
    def setup_style(self):
        """Set up consistent plot styling."""
        # Use a style that's available in all matplotlib versions
        plt.style.use('default')
        sns.set_palette("husl")
        plt.rcParams['figure.facecolor'] = 'white'
        plt.rcParams['axes.facecolor'] = 'white'
        plt.rcParams['savefig.facecolor'] = 'white'
        plt.rcParams['savefig.edgecolor'] = 'none'
        plt.rcParams['font.size'] = 10
        plt.rcParams['axes.labelsize'] = 11
        plt.rcParams['axes.titlesize'] = 12
        plt.rcParams['xtick.labelsize'] = 9
        plt.rcParams['ytick.labelsize'] = 9
        plt.rcParams['legend.fontsize'] = 9
    
    def load_analysis_info(self):
        """Load analysis summary information."""
        summary_file = os.path.join(self.analysis_dir, 'analysis_summary.json')
        if os.path.exists(summary_file):
            with open(summary_file, 'r') as f:
                self.analysis_info = json.load(f)
                self.symbol = self.analysis_info.get('symbol', 'Unknown')
        else:
            self.analysis_info = {}
            self.symbol = 'Unknown'
    
    def load_pattern_data(self, offset: int) -> pd.DataFrame:
        """Load the pattern analysis summary data for specific offset."""
        summary_file = os.path.join(self.analysis_dir, f"pattern_summary_offset_{offset}.csv")
        
        if not os.path.exists(summary_file):
            print(f"Warning: Pattern summary file not found for offset {offset}")
            return pd.DataFrame()
        
        df = pd.read_csv(summary_file)
        
        # Clean percentage columns
        if 'frequency_%' in df.columns:
            df['frequency_pct'] = pd.to_numeric(
                df['frequency_%'].astype(str).str.rstrip('%'), 
                errors='coerce'
            )
        
        if 'win_rate' in df.columns:
            # Handle percentage format
            win_rate_str = df['win_rate'].astype(str).str.rstrip('%')
            df['win_rate_pct'] = pd.to_numeric(win_rate_str, errors='coerce')
        
        # Convert string numbers to float
        numeric_columns = ['avg_change', 'total_change', 'std_dev', 'min_change', 
                          'max_change', 'return_risk_ratio', 'avg_volume']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df
    
    def analyze_pattern_composition(self, df: pd.DataFrame) -> pd.DataFrame:
        """Analyze the composition of each pattern (P, N, O counts)."""
        composition_data = []
        
        for _, row in df.iterrows():
            pattern = row['pattern']
            p_count = pattern.count('P')
            n_count = pattern.count('N')
            o_count = pattern.count('O')
            
            # Determine pattern type
            if p_count >= 2:
                pattern_type = 'P-Heavy'
            elif n_count >= 2:
                pattern_type = 'N-Heavy'
            elif o_count >= 2:
                pattern_type = 'O-Heavy'
            else:
                pattern_type = 'Mixed'
            
            composition_data.append({
                'pattern': pattern,
                'P_count': p_count,
                'N_count': n_count,
                'O_count': o_count,
                'pattern_type': pattern_type,
                'avg_change': row.get('avg_change', 0),
                'count': row.get('count', 0),
                'win_rate': row.get('win_rate_pct', 0),
                'return_risk_ratio': row.get('return_risk_ratio', 0)
            })
        
        return pd.DataFrame(composition_data)
    
    def create_overview_dashboard(self, df: pd.DataFrame, offset: int = 0):
        """Create a comprehensive 4-panel dashboard for 3-minute patterns."""
        if df.empty:
            print(f"No data available for offset {offset}")
            return
            
        fig = plt.figure(figsize=(20, 16))
        gs = GridSpec(2, 2, figure=fig, hspace=0.3, wspace=0.3)
        
        # Panel 1: Top 10 Profitable Patterns
        ax1 = fig.add_subplot(gs[0, 0])
        top_patterns = df.nlargest(min(10, len(df)), 'avg_change')
        
        if not top_patterns.empty:
            colors = ['green' if x > 0 else 'red' for x in top_patterns['avg_change']]
            bars = ax1.barh(range(len(top_patterns)), top_patterns['avg_change'], 
                           color=colors, alpha=0.7)
            ax1.set_yticks(range(len(top_patterns)))
            ax1.set_yticklabels(top_patterns['pattern'])
            ax1.set_xlabel('Average Change ($)')
            ax1.set_title(f'Top 10 Most Profitable 3-Minute Patterns (Offset {offset})', 
                         fontsize=14, fontweight='bold')
            ax1.grid(axis='x', alpha=0.3)
            
            # Add value labels
            for i, val in enumerate(top_patterns['avg_change']):
                ax1.text(val, i, f' ${val:.4f}', va='center', fontsize=9)
        
        # Panel 2: Pattern Frequency Distribution
        ax2 = fig.add_subplot(gs[0, 1])
        
        all_patterns = df.nlargest(min(15, len(df)), 'count')
        if not all_patterns.empty:
            ax2.bar(range(len(all_patterns)), all_patterns['count'], 
                   color=plt.cm.viridis(np.linspace(0.3, 0.9, len(all_patterns))), 
                   alpha=0.8)
            ax2.set_xticks(range(len(all_patterns)))
            ax2.set_xticklabels(all_patterns['pattern'], rotation=45, ha='right')
            ax2.set_ylabel('Number of Occurrences')
            ax2.set_title(f'Most Frequent 3-Minute Patterns (Offset {offset})', 
                         fontsize=14, fontweight='bold')
            ax2.grid(axis='y', alpha=0.3)
        
        # Panel 3: Win Rate vs Average Change Scatter
        ax3 = fig.add_subplot(gs[1, 0])
        
        if 'win_rate_pct' in df.columns and 'avg_change' in df.columns:
            # Filter out invalid data
            valid_data = df.dropna(subset=['win_rate_pct', 'avg_change', 'count'])
            
            if not valid_data.empty:
                scatter = ax3.scatter(valid_data['win_rate_pct'], 
                                    valid_data['avg_change'], 
                                    s=valid_data['count']*3, 
                                    alpha=0.6, 
                                    c=valid_data.get('return_risk_ratio', 0), 
                                    cmap='RdYlGn')
                ax3.set_xlabel('Win Rate (%)')
                ax3.set_ylabel('Average Change ($)')
                ax3.set_title('3-Minute Pattern Performance: Win Rate vs Profitability', 
                            fontsize=14, fontweight='bold')
                ax3.axhline(y=0, color='black', linestyle='--', alpha=0.3)
                ax3.axvline(x=50, color='black', linestyle='--', alpha=0.3)
                ax3.grid(alpha=0.3)
                
                # Add colorbar
                cbar = plt.colorbar(scatter, ax=ax3)
                cbar.set_label('Return/Risk Ratio', rotation=270, labelpad=15)
                
                # Add annotations for best patterns
                if 'return_risk_ratio' in valid_data.columns:
                    best_patterns = valid_data.nlargest(min(3, len(valid_data)), 'return_risk_ratio')
                    for _, row in best_patterns.iterrows():
                        ax3.annotate(row['pattern'], 
                                   (row['win_rate_pct'], row['avg_change']),
                                   fontsize=8, alpha=0.7)
        
        # Panel 4: Pattern Type Distribution
        ax4 = fig.add_subplot(gs[1, 1])
        composition_df = self.analyze_pattern_composition(df)
        
        if not composition_df.empty:
            type_stats = composition_df.groupby('pattern_type').agg({
                'count': 'sum',
                'avg_change': 'mean'
            })
            
            if not type_stats.empty:
                colors_map = {'P-Heavy': 'green', 'N-Heavy': 'red', 
                            'O-Heavy': 'gray', 'Mixed': 'blue'}
                colors = [colors_map.get(pt, 'gray') for pt in type_stats.index]
                
                bars = ax4.bar(range(len(type_stats)), type_stats['count'], 
                             color=colors, alpha=0.7)
                ax4.set_xticks(range(len(type_stats)))
                ax4.set_xticklabels(type_stats.index)
                ax4.set_ylabel('Total Occurrences')
                ax4.set_title('3-Minute Pattern Type Distribution', 
                            fontsize=14, fontweight='bold')
                ax4.grid(axis='y', alpha=0.3)
                
                # Add average change as secondary info
                ax4_twin = ax4.twinx()
                ax4_twin.plot(range(len(type_stats)), type_stats['avg_change'], 
                            'ko-', linewidth=2, markersize=8, label='Avg Change')
                ax4_twin.set_ylabel('Average Change ($)')
                ax4_twin.legend(loc='upper right')
        
        plt.suptitle(f'3-Minute Pattern Analysis Dashboard - {self.symbol} - Offset {offset}', 
                    fontsize=16, fontweight='bold', y=1.02)
        
        output_file = os.path.join(self.output_dir, f'dashboard_offset_{offset}.png')
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"  ✓ Dashboard saved to: {output_file}")
    
    def create_profitability_heatmap(self, df: pd.DataFrame, offset: int = 0):
        """Create a heatmap showing pattern profitability."""
        if df.empty:
            print(f"No data available for offset {offset}")
            return
            
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 10))
        
        # Heatmap 1: Top patterns by profitability
        matrix_size = min(27, len(df))  # Max 27 patterns for 3-minute
        matrix_data = np.zeros((6, 5))
        matrix_labels = [['' for _ in range(5)] for _ in range(6)]
        
        df_sorted = df.sort_values('avg_change', ascending=False).head(matrix_size)
        
        for idx, (_, row) in enumerate(df_sorted.iterrows()):
            if idx < 27:
                row_idx = idx // 5
                col_idx = idx % 5
                matrix_data[row_idx, col_idx] = row['avg_change']
                matrix_labels[row_idx][col_idx] = row['pattern']
        
        # Mask empty cells
        mask = np.zeros_like(matrix_data, dtype=bool)
        mask[5, 2:] = True  # Last 3 cells are empty for 27 patterns
        
        sns.heatmap(matrix_data, annot=matrix_labels, fmt='', 
                   cmap='RdYlGn', center=0, ax=ax1,
                   mask=mask,
                   cbar_kws={'label': 'Average Change ($)'})
        ax1.set_title(f'Pattern Profitability Map (Offset {offset})', 
                     fontsize=14, fontweight='bold')
        ax1.set_xlabel('Position')
        ax1.set_ylabel('Rank Group')
        
        # Heatmap 2: Pattern composition vs performance
        composition_df = self.analyze_pattern_composition(df)
        
        if not composition_df.empty:
            pivot_data = composition_df.pivot_table(
                values='avg_change',
                index='P_count',
                columns='N_count',
                aggfunc='mean'
            )
            
            if not pivot_data.empty:
                sns.heatmap(pivot_data, annot=True, fmt='.4f', 
                           cmap='RdYlGn', center=0, ax=ax2,
                           cbar_kws={'label': 'Average Change ($)'})
                ax2.set_title('Performance by P/N Composition', 
                            fontsize=14, fontweight='bold')
                ax2.set_xlabel('Number of N (Negative) Minutes')
                ax2.set_ylabel('Number of P (Positive) Minutes')
        
        plt.suptitle(f'3-Minute Pattern Profitability Analysis - {self.symbol} - Offset {offset}', 
                    fontsize=16, fontweight='bold')
        plt.tight_layout()
        
        output_file = os.path.join(self.output_dir, f'profitability_heatmap_offset_{offset}.png')
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"  ✓ Heatmap saved to: {output_file}")
    
    def create_offset_comparison(self):
        """Create comprehensive offset comparison visualizations."""
        # Load data from all three offsets
        offset_data = {}
        for offset in range(3):
            df = self.load_pattern_data(offset)
            if not df.empty:
                offset_data[offset] = df
        
        if len(offset_data) < 2:
            print("Not enough offset data for comparison")
            return
        
        fig = plt.figure(figsize=(20, 16))
        gs = GridSpec(2, 2, figure=fig, hspace=0.3, wspace=0.3)
        
        # Panel 1: Pattern consistency across offsets
        ax1 = fig.add_subplot(gs[0, 0])
        
        # Get all unique patterns
        all_patterns = set()
        for df in offset_data.values():
            all_patterns.update(df['pattern'].tolist())
        
        # Select top patterns by average performance
        pattern_performance = {}
        for pattern in all_patterns:
            perf_values = []
            for df in offset_data.values():
                pattern_data = df[df['pattern'] == pattern]
                if not pattern_data.empty:
                    perf_values.append(pattern_data.iloc[0]['avg_change'])
            if perf_values:
                pattern_performance[pattern] = np.mean(perf_values)
        
        top_patterns = sorted(pattern_performance.keys(), 
                            key=lambda x: abs(pattern_performance[x]), 
                            reverse=True)[:15]
        
        # Create consistency matrix
        consistency_matrix = []
        for pattern in top_patterns:
            row = []
            for offset in range(3):
                if offset in offset_data:
                    pattern_data = offset_data[offset][offset_data[offset]['pattern'] == pattern]
                    if not pattern_data.empty:
                        row.append(pattern_data.iloc[0]['avg_change'])
                    else:
                        row.append(0)
                else:
                    row.append(0)
            consistency_matrix.append(row)
        
        if consistency_matrix:
            consistency_df = pd.DataFrame(consistency_matrix, 
                                        index=top_patterns, 
                                        columns=[f'Offset {i}' for i in range(3)])
            
            sns.heatmap(consistency_df, annot=True, fmt='.4f', cmap='RdYlGn', 
                       center=0, ax=ax1, cbar_kws={'label': 'Average Change ($)'})
            ax1.set_title('Pattern Performance Across Offsets (Top 15)', 
                         fontsize=14, fontweight='bold')
            ax1.set_ylabel('Pattern')
        
        # Panel 2: Offset performance comparison
        ax2 = fig.add_subplot(gs[0, 1])
        
        offset_stats = []
        for offset, df in offset_data.items():
            offset_stats.append({
                'Offset': offset,
                'Total Patterns': len(df),
                'Avg Performance': df['avg_change'].mean(),
                'Best Pattern': df['avg_change'].max() if len(df) > 0 else 0,
                'Worst Pattern': df['avg_change'].min() if len(df) > 0 else 0
            })
        
        if offset_stats:
            stats_df = pd.DataFrame(offset_stats)
            
            x = np.arange(len(stats_df))
            width = 0.2
            
            ax2.bar(x - width, stats_df['Avg Performance'], width, 
                   label='Avg Performance', color='blue', alpha=0.7)
            ax2.bar(x, stats_df['Best Pattern'], width, 
                   label='Best Pattern', color='green', alpha=0.7)
            ax2.bar(x + width, stats_df['Worst Pattern'], width, 
                   label='Worst Pattern', color='red', alpha=0.7)
            
            ax2.set_xlabel('Offset')
            ax2.set_ylabel('Change ($)')
            ax2.set_title('Performance Comparison Across Offsets', 
                         fontsize=14, fontweight='bold')
            ax2.set_xticks(x)
            ax2.set_xticklabels([f'Offset {i}' for i in stats_df['Offset']])
            ax2.legend()
            ax2.grid(axis='y', alpha=0.3)
        
        # Panel 3: Pattern frequency comparison
        ax3 = fig.add_subplot(gs[1, 0])
        
        freq_comparison = []
        for pattern in top_patterns[:10]:
            row = {'pattern': pattern}
            for offset, df in offset_data.items():
                pattern_data = df[df['pattern'] == pattern]
                if not pattern_data.empty:
                    row[f'offset_{offset}'] = pattern_data.iloc[0]['count']
                else:
                    row[f'offset_{offset}'] = 0
            freq_comparison.append(row)
        
        if freq_comparison:
            freq_df = pd.DataFrame(freq_comparison)
            freq_df.set_index('pattern', inplace=True)
            
            freq_df.plot(kind='bar', ax=ax3, width=0.8, alpha=0.7)
            ax3.set_xlabel('Pattern')
            ax3.set_ylabel('Occurrences')
            ax3.set_title('Pattern Frequency Across Offsets (Top 10)', 
                         fontsize=14, fontweight='bold')
            ax3.legend(title='Offset', labels=[f'Offset {i}' for i in range(3)])
            ax3.grid(axis='y', alpha=0.3)
            plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        # Panel 4: Summary statistics table
        ax4 = fig.add_subplot(gs[1, 1])
        ax4.axis('off')
        
        # Create summary table
        summary_data = []
        for offset, df in offset_data.items():
            avg_win_rate = df['win_rate_pct'].mean() if 'win_rate_pct' in df.columns else 0
            
            summary_data.append([
                f'Offset {offset}',
                len(df),
                f'{df["count"].sum()}',
                f'${df["avg_change"].mean():.4f}',
                f'{avg_win_rate:.1f}%',
                f'${df["avg_change"].std():.4f}'
            ])
        
        if summary_data:
            table = ax4.table(cellText=summary_data,
                            colLabels=['Offset', 'Unique\nPatterns', 'Total\nOccurrences', 
                                      'Avg\nChange', 'Avg Win\nRate', 'Std Dev'],
                            cellLoc='center',
                            loc='center')
            table.auto_set_font_size(False)
            table.set_fontsize(10)
            table.scale(1.2, 2)
            ax4.set_title('Offset Comparison Summary Statistics', 
                         fontsize=14, fontweight='bold', pad=20)
        
        plt.suptitle(f'3-Minute Pattern Analysis: Offset Comparison - {self.symbol}', 
                    fontsize=16, fontweight='bold')
        plt.tight_layout()
        
        output_file = os.path.join(self.output_dir, 'offset_comparison.png')
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"  ✓ Offset comparison saved to: {output_file}")
    
    def create_pattern_timeline(self, offset: int = 0):
        """Create timeline visualization of pattern occurrences."""
        occurrences_file = os.path.join(self.analysis_dir, 
                                       f"pattern_occurrences_offset_{offset}.csv")
        
        if not os.path.exists(occurrences_file):
            print(f"Pattern occurrences file not found for offset {offset}")
            return
        
        occ_df = pd.read_csv(occurrences_file)
        occ_df['timestamp'] = pd.to_datetime(occ_df['timestamp'])
        occ_df['total_change'] = pd.to_numeric(occ_df['total_change'], errors='coerce')
        
        fig, axes = plt.subplots(2, 1, figsize=(18, 12))
        
        # Panel 1: Cumulative changes over time
        ax1 = axes[0]
        occ_df['cumulative_change'] = occ_df['total_change'].cumsum()
        ax1.plot(occ_df['timestamp'], occ_df['cumulative_change'], 
                linewidth=2, color='blue', alpha=0.7)
        ax1.fill_between(occ_df['timestamp'], 0, occ_df['cumulative_change'], 
                         alpha=0.3)
        ax1.set_xlabel('Time')
        ax1.set_ylabel('Cumulative Change ($)')
        ax1.set_title(f'Cumulative Pattern Performance Over Time (Offset {offset})', 
                     fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.axhline(y=0, color='black', linestyle='--', alpha=0.5)
        
        # Panel 2: Pattern distribution over time
        ax2 = axes[1]
        
        # Get top patterns
        top_patterns = occ_df['pattern'].value_counts().head(5).index
        
        for i, pattern in enumerate(top_patterns):
            pattern_data = occ_df[occ_df['pattern'] == pattern].copy()
            ax2.scatter(pattern_data['timestamp'], [i]*len(pattern_data), 
                       s=abs(pattern_data['total_change'])*100, 
                       alpha=0.6, label=pattern)
        
        ax2.set_xlabel('Time')
        ax2.set_ylabel('Pattern')
        ax2.set_yticks(range(len(top_patterns)))
        ax2.set_yticklabels(top_patterns)
        ax2.set_title(f'Top 5 Pattern Occurrences Over Time (Offset {offset})', 
                     fontsize=14, fontweight='bold')
        ax2.legend(loc='upper right', bbox_to_anchor=(1.15, 1))
        ax2.grid(True, alpha=0.3, axis='x')
        
        plt.suptitle(f'3-Minute Pattern Timeline Analysis - {self.symbol} - Offset {offset}', 
                    fontsize=16, fontweight='bold')
        plt.tight_layout()
        
        output_file = os.path.join(self.output_dir, f'timeline_offset_{offset}.png')
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"  ✓ Timeline saved to: {output_file}")
    
    def generate_summary_report(self):
        """Generate a text summary report of the analysis."""
        report_file = os.path.join(self.output_dir, 'visualization_summary.txt')
        
        with open(report_file, 'w') as f:
            f.write("="*80 + "\n")
            f.write("THREE-MINUTE PATTERN VISUALIZATION SUMMARY\n")
            f.write("="*80 + "\n")
            f.write(f"Symbol: {self.symbol}\n")
            f.write(f"Analysis Directory: {self.analysis_dir}\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            if self.analysis_info:
                f.write("ANALYSIS INFORMATION\n")
                f.write("-"*40 + "\n")
                f.write(f"Data File: {self.analysis_info.get('data_file', 'N/A')}\n")
                f.write(f"Bars Analyzed: {self.analysis_info.get('bars_analyzed', 'N/A')}\n")
                
                date_range = self.analysis_info.get('date_range', {})
                f.write(f"Date Range: {date_range.get('start', 'N/A')} to {date_range.get('end', 'N/A')}\n\n")
            
            f.write("VISUALIZATIONS GENERATED\n")
            f.write("-"*40 + "\n")
            
            # List all generated files
            generated_files = [f for f in os.listdir(self.output_dir) if f.endswith('.png')]
            for file in sorted(generated_files):
                f.write(f"  • {file}\n")
            
            f.write(f"\nTotal visualizations: {len(generated_files)}\n")
            
            # Pattern statistics across offsets
            f.write("\n" + "="*80 + "\n")
            f.write("PATTERN STATISTICS BY OFFSET\n")
            f.write("="*80 + "\n")
            
            for offset in range(3):
                df = self.load_pattern_data(offset)
                if not df.empty:
                    f.write(f"\nOffset {offset}:\n")
                    f.write("-"*40 + "\n")
                    f.write(f"  Unique patterns: {len(df)}\n")
                    f.write(f"  Total occurrences: {df['count'].sum()}\n")
                    f.write(f"  Mean performance: ${df['avg_change'].mean():.6f}\n")
                    
                    top_pattern = df.nlargest(1, 'avg_change')
                    if not top_pattern.empty:
                        f.write(f"  Best pattern: {top_pattern.iloc[0]['pattern']} ")
                        f.write(f"(${top_pattern.iloc[0]['avg_change']:.6f})\n")
                    
                    worst_pattern = df.nsmallest(1, 'avg_change')
                    if not worst_pattern.empty:
                        f.write(f"  Worst pattern: {worst_pattern.iloc[0]['pattern']} ")
                        f.write(f"(${worst_pattern.iloc[0]['avg_change']:.6f})\n")
        
        print(f"  ✓ Summary report saved to: {report_file}")
    
    def run_all_visualizations(self):
        """Generate all visualizations for the analysis."""
        print(f"\n{'='*80}")
        print("GENERATING VISUALIZATIONS")
        print(f"{'='*80}")
        print(f"Symbol: {self.symbol}")
        print(f"Output Directory: {self.output_dir}\n")
        
        # Generate visualizations for each offset
        for offset in range(3):
            print(f"📊 Processing Offset {offset}...")
            
            df = self.load_pattern_data(offset)
            if not df.empty:
                print(f"  Found {len(df)} patterns")
                self.create_overview_dashboard(df, offset)
                self.create_profitability_heatmap(df, offset)
                self.create_pattern_timeline(offset)
            else:
                print(f"  No data for offset {offset}")
        
        # Generate comparison visualizations
        print("\n📊 Creating offset comparison...")
        self.create_offset_comparison()
        
        # Generate summary report
        print("\n📝 Generating summary report...")
        self.generate_summary_report()
        
        print(f"\n{'='*80}")
        print("VISUALIZATION COMPLETE")
        print(f"{'='*80}")
        print(f"✓ All visualizations saved to: {self.output_dir}")
        
        return self.output_dir


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Visualize 3-minute pattern analysis results')
    parser.add_argument('analysis_dir', help='Directory containing analysis results')
    args = parser.parse_args()
    
    visualizer = ThreeMinutePatternVisualizer(args.analysis_dir)
    visualizer.run_all_visualizations()


if __name__ == "__main__":
    main()
        