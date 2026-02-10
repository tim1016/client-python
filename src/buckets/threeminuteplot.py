import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import glob
import os
import sys
from matplotlib.patches import Rectangle
from matplotlib.gridspec import GridSpec

class ThreeMinutePatternVisualizer:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.setup_style()
        
    def setup_style(self):
        """Set up consistent plot styling."""
        plt.style.use('seaborn-v0_8-darkgrid')
        sns.set_palette("husl")
        plt.rcParams['figure.facecolor'] = 'white'
        plt.rcParams['axes.facecolor'] = 'white'
        plt.rcParams['savefig.facecolor'] = 'white'
        plt.rcParams['savefig.edgecolor'] = 'none'
    
    def load_pattern_data(self, offset: int = None) -> pd.DataFrame:
        """Load the pattern analysis summary data for specific offset or combined."""
        if offset is not None:
            summary_file = os.path.join(self.base_dir, f"pattern_summary_offset_{offset}.csv")
            if not os.path.exists(summary_file):
                raise FileNotFoundError(f"Pattern summary file not found: {summary_file}")
        else:
            # Try to load the main summary file
            summary_file = os.path.join(self.base_dir, "pattern_summary_offset_0.csv")
            if not os.path.exists(summary_file):
                raise FileNotFoundError(f"Pattern summary file not found: {summary_file}")
        
        df = pd.read_csv(summary_file)
        
        # Clean percentage columns
        if 'frequency_%' in df.columns:
            df['frequency_pct'] = pd.to_numeric(df['frequency_%'].str.rstrip('%') if df['frequency_%'].dtype == object else df['frequency_%'])
        
        if 'win_rate' in df.columns:
            # Handle percentage format
            if df['win_rate'].dtype == object:
                df['win_rate_pct'] = pd.to_numeric(df['win_rate'].str.rstrip('%').str.replace(',', ''))
            else:
                df['win_rate_pct'] = df['win_rate'] * 100
        
        return df
    
    def analyze_pattern_composition(self, df: pd.DataFrame) -> pd.DataFrame:
        """Analyze the composition of each pattern (P, N, O counts)."""
        composition_data = []
        
        for _, row in df.iterrows():
            pattern = row['pattern']
            p_count = pattern.count('P')
            n_count = pattern.count('N')
            o_count = pattern.count('O')
            
            # Determine pattern type for 3-minute patterns
            if p_count >= 2:  # Adjusted threshold for 3-minute patterns
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
                'avg_change': row['avg_change'],
                'count': row['count'],
                'win_rate': row.get('win_rate_pct', 0),
                'return_risk_ratio': row.get('return_risk_ratio', 0)
            })
        
        return pd.DataFrame(composition_data)
    
    def create_overview_dashboard(self, df: pd.DataFrame, offset: int = 0):
        """Create a comprehensive 4-panel dashboard for 3-minute patterns."""
        fig = plt.figure(figsize=(20, 16))
        gs = GridSpec(2, 2, figure=fig, hspace=0.3, wspace=0.3)
        
        # Panel 1: Top 10 Profitable Patterns (adjusted for 3-minute)
        ax1 = fig.add_subplot(gs[0, 0])
        top_patterns = df.nlargest(10, 'avg_change')
        
        colors = ['green' if x > 0 else 'red' for x in top_patterns['avg_change']]
        bars = ax1.barh(range(len(top_patterns)), top_patterns['avg_change'], color=colors, alpha=0.7)
        ax1.set_yticks(range(len(top_patterns)))
        ax1.set_yticklabels(top_patterns['pattern'])
        ax1.set_xlabel('Average Change ($)')
        ax1.set_title(f'Top 10 Most Profitable 3-Minute Patterns (Offset {offset})', fontsize=14, fontweight='bold')
        ax1.grid(axis='x', alpha=0.3)
        
        # Add value labels
        for i, val in enumerate(top_patterns['avg_change']):
            ax1.text(val, i, f' ${val:.4f}', va='center', fontsize=9)
        
        # Panel 2: Pattern Frequency Distribution
        ax2 = fig.add_subplot(gs[0, 1])
        
        # All patterns for 3-minute analysis (27 total possible)
        all_patterns = df.nlargest(min(15, len(df)), 'count')
        ax2.bar(range(len(all_patterns)), all_patterns['count'], 
                color=plt.cm.viridis(np.linspace(0.3, 0.9, len(all_patterns))), alpha=0.8)
        ax2.set_xticks(range(len(all_patterns)))
        ax2.set_xticklabels(all_patterns['pattern'], rotation=45, ha='right')
        ax2.set_ylabel('Number of Occurrences')
        ax2.set_title(f'Most Frequent 3-Minute Patterns (Offset {offset})', fontsize=14, fontweight='bold')
        ax2.grid(axis='y', alpha=0.3)
        
        # Panel 3: Win Rate vs Average Change Scatter
        ax3 = fig.add_subplot(gs[1, 0])
        
        if 'win_rate_pct' in df.columns and 'return_risk_ratio' in df.columns:
            scatter = ax3.scatter(df['win_rate_pct'], df['avg_change'], 
                                s=df['count']*3, alpha=0.6, 
                                c=df['return_risk_ratio'], cmap='RdYlGn')
            ax3.set_xlabel('Win Rate (%)')
            ax3.set_ylabel('Average Change ($)')
            ax3.set_title('3-Minute Pattern Performance: Win Rate vs Profitability', fontsize=14, fontweight='bold')
            ax3.axhline(y=0, color='black', linestyle='--', alpha=0.3)
            ax3.axvline(x=50, color='black', linestyle='--', alpha=0.3)
            ax3.grid(alpha=0.3)
            
            # Add colorbar
            cbar = plt.colorbar(scatter, ax=ax3)
            cbar.set_label('Return/Risk Ratio', rotation=270, labelpad=15)
            
            # Add annotations for best patterns
            best_patterns = df.nlargest(3, 'return_risk_ratio')
            for _, row in best_patterns.iterrows():
                ax3.annotate(row['pattern'], 
                           (row['win_rate_pct'], row['avg_change']),
                           fontsize=8, alpha=0.7)
        
        # Panel 4: Pattern Type Distribution
        ax4 = fig.add_subplot(gs[1, 1])
        composition_df = self.analyze_pattern_composition(df)
        
        type_stats = composition_df.groupby('pattern_type').agg({
            'count': 'sum',
            'avg_change': 'mean'
        })
        
        colors_map = {'P-Heavy': 'green', 'N-Heavy': 'red', 'O-Heavy': 'gray', 'Mixed': 'blue'}
        colors = [colors_map.get(pt, 'gray') for pt in type_stats.index]
        
        bars = ax4.bar(range(len(type_stats)), type_stats['count'], color=colors, alpha=0.7)
        ax4.set_xticks(range(len(type_stats)))
        ax4.set_xticklabels(type_stats.index)
        ax4.set_ylabel('Total Occurrences')
        ax4.set_title('3-Minute Pattern Type Distribution', fontsize=14, fontweight='bold')
        ax4.grid(axis='y', alpha=0.3)
        
        # Add average change as secondary info
        ax4_twin = ax4.twinx()
        ax4_twin.plot(range(len(type_stats)), type_stats['avg_change'], 
                     'ko-', linewidth=2, markersize=8, label='Avg Change')
        ax4_twin.set_ylabel('Average Change ($)')
        ax4_twin.legend(loc='upper right')
        
        plt.suptitle(f'3-Minute Pattern Analysis Dashboard - Offset {offset} (27 Possible Patterns)', 
                    fontsize=16, fontweight='bold', y=1.02)
        
        plt.savefig(os.path.join(self.base_dir, f'pattern_overview_dashboard_offset_{offset}.png'), 
                   dpi=300, bbox_inches='tight')
        plt.close()
    
    def create_profitability_heatmap(self, df: pd.DataFrame, offset: int = 0):
        """Create a heatmap showing pattern profitability for 3-minute patterns."""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 10))
        
        # For 3-minute patterns, we have 27 total patterns (3^3)
        # Create a 6x5 grid (30 slots, will have 3 empty)
        matrix_data = np.zeros((6, 5))
        matrix_labels = [['' for _ in range(5)] for _ in range(6)]
        
        # Sort patterns by average change
        df_sorted = df.sort_values('avg_change', ascending=False)
        
        # Fill the matrix
        for idx, (_, row) in enumerate(df_sorted.iterrows()):
            if idx < 27:  # Only 27 patterns for 3-minute
                row_idx = idx // 5
                col_idx = idx % 5
                matrix_data[row_idx, col_idx] = row['avg_change']
                matrix_labels[row_idx][col_idx] = row['pattern']
        
        # Mask empty cells
        mask = np.zeros_like(matrix_data, dtype=bool)
        mask[5, 2:] = True  # Last 3 cells are empty
        
        # Heatmap 1: All 27 patterns by profitability
        sns.heatmap(matrix_data, annot=matrix_labels, fmt='', 
                   cmap='RdYlGn', center=0, ax=ax1,
                   mask=mask,
                   cbar_kws={'label': 'Average Change ($)'})
        ax1.set_title(f'All 27 3-Minute Patterns by Profitability (Offset {offset})', fontsize=14, fontweight='bold')
        ax1.set_xlabel('Position')
        ax1.set_ylabel('Rank Group')
        
        # Heatmap 2: Pattern composition vs performance
        composition_df = self.analyze_pattern_composition(df)
        
        # For 3-minute patterns, P and N counts can be 0, 1, 2, or 3
        pivot_data = composition_df.pivot_table(
            values='avg_change',
            index='P_count',
            columns='N_count',
            aggfunc='mean'
        )
        
        sns.heatmap(pivot_data, annot=True, fmt='.4f', 
                   cmap='RdYlGn', center=0, ax=ax2,
                   cbar_kws={'label': 'Average Change ($)'})
        ax2.set_title('3-Minute Pattern Performance by P/N Composition', fontsize=14, fontweight='bold')
        ax2.set_xlabel('Number of N (Negative) Minutes')
        ax2.set_ylabel('Number of P (Positive) Minutes')
        
        plt.suptitle(f'3-Minute Pattern Profitability Analysis - Offset {offset}', fontsize=16, fontweight='bold')
        plt.tight_layout()
        
        plt.savefig(os.path.join(self.base_dir, f'pattern_profitability_analysis_offset_{offset}.png'), 
                   dpi=300, bbox_inches='tight')
        plt.close()
    
    def create_offset_comparison(self):
        """Create comprehensive offset comparison visualizations for 3-minute patterns."""
        # Load data from all three offsets
        offset_data = {}
        for offset in range(3):
            try:
                offset_data[offset] = self.load_pattern_data(offset)
            except FileNotFoundError:
                print(f"Warning: No data found for offset {offset}")
                continue
        
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
        
        pattern_list = sorted(list(all_patterns))[:15]  # Top 15 for visibility
        
        # Create consistency matrix
        consistency_matrix = []
        for pattern in pattern_list:
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
        
        consistency_df = pd.DataFrame(consistency_matrix, 
                                     index=pattern_list, 
                                     columns=[f'Offset {i}' for i in range(3)])
        
        sns.heatmap(consistency_df, annot=True, fmt='.4f', cmap='RdYlGn', 
                   center=0, ax=ax1, cbar_kws={'label': 'Average Change ($)'})
        ax1.set_title('Pattern Performance Across Offsets (Top 15)', fontsize=14, fontweight='bold')
        ax1.set_ylabel('Pattern')
        
        # Panel 2: Offset performance comparison
        ax2 = fig.add_subplot(gs[0, 1])
        
        offset_stats = []
        for offset, df in offset_data.items():
            offset_stats.append({
                'Offset': offset,
                'Total Patterns': len(df),
                'Avg Performance': df['avg_change'].mean(),
                'Best Pattern': df.nlargest(1, 'avg_change')['avg_change'].values[0] if len(df) > 0 else 0,
                'Worst Pattern': df.nsmallest(1, 'avg_change')['avg_change'].values[0] if len(df) > 0 else 0
            })
        
        stats_df = pd.DataFrame(offset_stats)
        
        x = np.arange(len(stats_df))
        width = 0.2
        
        ax2.bar(x - width, stats_df['Avg Performance'], width, label='Avg Performance', color='blue', alpha=0.7)
        ax2.bar(x, stats_df['Best Pattern'], width, label='Best Pattern', color='green', alpha=0.7)
        ax2.bar(x + width, stats_df['Worst Pattern'], width, label='Worst Pattern', color='red', alpha=0.7)
        
        ax2.set_xlabel('Offset')
        ax2.set_ylabel('Change ($)')
        ax2.set_title('Performance Comparison Across Offsets', fontsize=14, fontweight='bold')
        ax2.set_xticks(x)
        ax2.set_xticklabels([f'Offset {i}' for i in stats_df['Offset']])
        ax2.legend()
        ax2.grid(axis='y', alpha=0.3)
        
        # Panel 3: Pattern frequency comparison
        ax3 = fig.add_subplot(gs[1, 0])
        
        freq_comparison = []
        for pattern in pattern_list[:10]:  # Top 10 patterns
            row = {'pattern': pattern}
            for offset, df in offset_data.items():
                pattern_data = df[df['pattern'] == pattern]
                if not pattern_data.empty:
                    row[f'offset_{offset}'] = pattern_data.iloc[0]['count']
                else:
                    row[f'offset_{offset}'] = 0
            freq_comparison.append(row)
        
        freq_df = pd.DataFrame(freq_comparison)
        freq_df.set_index('pattern', inplace=True)
        
        freq_df.plot(kind='bar', ax=ax3, width=0.8, alpha=0.7)
        ax3.set_xlabel('Pattern')
        ax3.set_ylabel('Occurrences')
        ax3.set_title('Pattern Frequency Across Offsets (Top 10)', fontsize=14, fontweight='bold')
        ax3.legend(title='Offset', labels=[f'Offset {i}' for i in range(3)])
        ax3.grid(axis='y', alpha=0.3)
        plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        # Panel 4: Summary statistics table
        ax4 = fig.add_subplot(gs[1, 1])
        ax4.axis('off')
        
        # Create summary table
        summary_data = []
        for offset, df in offset_data.items():
            if 'win_rate_pct' in df.columns:
                avg_win_rate = df['win_rate_pct'].mean()
            else:
                avg_win_rate = 0
                
            summary_data.append([
                f'Offset {offset}',
                len(df),
                f'{df["count"].sum()}',
                f'${df["avg_change"].mean():.4f}',
                f'{avg_win_rate:.1f}%',
                f'${df["avg_change"].std():.4f}'
            ])
        
        table = ax4.table(cellText=summary_data,
                         colLabels=['Offset', 'Unique\nPatterns', 'Total\nOccurrences', 
                                   'Avg\nChange', 'Avg Win\nRate', 'Std Dev'],
                         cellLoc='center',
                         loc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1.2, 2)
        ax4.set_title('Offset Comparison Summary Statistics', fontsize=14, fontweight='bold', pad=20)
        
        plt.suptitle('3-Minute Pattern Analysis: Offset Comparison (0, 1, 2 minutes)', 
                    fontsize=16, fontweight='bold')
        plt.tight_layout()
        
        plt.savefig(os.path.join(self.base_dir, 'offset_comparison_analysis.png'), 
                   dpi=300, bbox_inches='tight')
        plt.close()
    
    def create_pattern_occurrences_timeline(self, offset: int = 0):
        """Create timeline visualization of pattern occurrences."""
        # Load pattern occurrences data
        occurrences_file = os.path.join(self.base_dir, f"pattern_occurrences_offset_{offset}.csv")
        if not os.path.exists(occurrences_file):
            print(f"Pattern occurrences file not found for offset {offset}")
            return
        
        occ_df = pd.read_csv(occurrences_file)
        occ_df['timestamp'] = pd.to_datetime(occ_df['timestamp'])
        
        fig, axes = plt.subplots(2, 1, figsize=(18, 12))
        
        # Panel 1: Timeline of cumulative changes
        ax1 = axes[0]
        occ_df['cumulative_change'] = occ_df['total_change'].cumsum()
        ax1.plot(occ_df['timestamp'], occ_df['cumulative_change'], linewidth=2, color='blue', alpha=0.7)
        ax1.fill_between(occ_df['timestamp'], 0, occ_df['cumulative_change'], alpha=0.3)
        ax1.set_xlabel('Time')
        ax1.set_ylabel('Cumulative Change ($)')
        ax1.set_title(f'Cumulative Pattern Performance Over Time (Offset {offset})', fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.axhline(y=0, color='black', linestyle='--', alpha=0.5)
        
        # Panel 2: Pattern distribution over time
        ax2 = axes[1]
        
        # Group by pattern and count occurrences over time
        top_patterns = occ_df['pattern'].value_counts().head(5).index
        
        for pattern in top_patterns:
            pattern_data = occ_df[occ_df['pattern'] == pattern].copy()
            pattern_data['occurrence_num'] = range(1, len(pattern_data) + 1)
            ax2.scatter(pattern_data['timestamp'], [pattern]*len(pattern_data), 
                       s=abs(pattern_data['total_change'])*100, 
                       alpha=0.6, label=pattern)
        
        ax2.set_xlabel('Time')
        ax2.set_ylabel('Pattern')
        ax2.set_title(f'Top 5 Pattern Occurrences Over Time (Offset {offset})', fontsize=14, fontweight='bold')
        ax2.legend(loc='upper right', bbox_to_anchor=(1.15, 1))
        ax2.grid(True, alpha=0.3, axis='x')
        
        plt.suptitle(f'3-Minute Pattern Timeline Analysis - Offset {offset}', 
                    fontsize=16, fontweight='bold')
        plt.tight_layout()
        
        plt.savefig(os.path.join(self.base_dir, f'pattern_timeline_offset_{offset}.png'), 
                   dpi=300, bbox_inches='tight')
        plt.close()
    
    def export_enhanced_summary(self):
        """Export comprehensive summary combining all offsets."""
        all_summaries = []
        
        for offset in range(3):
            try:
                df = self.load_pattern_data(offset)
                composition_df = self.analyze_pattern_composition(df)
                
                # Add offset column
                composition_df['offset'] = offset
                all_summaries.append(composition_df)
            except FileNotFoundError:
                continue
        
        if not all_summaries:
            print("No data to summarize")
            return
        
        # Combine all data
        combined_df = pd.concat(all_summaries, ignore_index=True)
        
        # Save to CSV
        output_file = os.path.join(self.base_dir, 'enhanced_3min_pattern_summary.csv')
        combined_df.to_csv(output_file, index=False)
        
        print(f"\nEnhanced 3-minute pattern summary saved to: {output_file}")
        
        # Print summary statistics
        print("\n" + "="*80)
        print("3-MINUTE PATTERN ANALYSIS SUMMARY STATISTICS")
        print("="*80)
        
        print(f"\nTotal Unique Patterns Found: {combined_df['pattern'].nunique()}")
        print(f"Maximum Possible Patterns: 27 (3^3)")
        print(f"Pattern Coverage: {combined_df['pattern'].nunique()/27*100:.1f}%")
        
        print("\nPattern Type Distribution Across All Offsets:")
        print("-"*40)
        type_counts = combined_df.groupby('pattern_type')['pattern'].nunique()
        for ptype, count in type_counts.items():
            print(f"{ptype}: {count} unique patterns")
        
        print("\nPerformance Metrics Across All Offsets:")
        print("-"*40)
        
        for offset in range(3):
            offset_data = combined_df[combined_df['offset'] == offset]
            if len(offset_data) > 0:
                print(f"\nOffset {offset}:")
                print(f"  Unique patterns: {offset_data['pattern'].nunique()}")
                print(f"  Mean performance: ${offset_data['avg_change'].mean():.4f}")
                print(f"  Best pattern: {offset_data.nlargest(1, 'avg_change')['pattern'].values[0]} "
                      f"(${offset_data.nlargest(1, 'avg_change')['avg_change'].values[0]:.4f})")
                print(f"  Total occurrences: {offset_data['count'].sum()}")
        
        # Find most consistent patterns across offsets
        pattern_consistency = combined_df.groupby('pattern').agg({
            'avg_change': ['mean', 'std'],
            'offset': 'count'
        })
        pattern_consistency.columns = ['mean_change', 'std_change', 'offset_count']
        pattern_consistency = pattern_consistency[pattern_consistency['offset_count'] == 3]  # Present in all offsets
        
        if len(pattern_consistency) > 0:
            pattern_consistency['consistency_score'] = abs(pattern_consistency['mean_change'] / 
                                                         (pattern_consistency['std_change'] + 0.0001))
            pattern_consistency = pattern_consistency.sort_values('consistency_score', ascending=False)
            
            print("\nMost Consistent Patterns Across All Offsets:")
            print("-"*40)
            for pattern in pattern_consistency.head(5).index:
                mean_val = pattern_consistency.loc[pattern, 'mean_change']
                std_val = pattern_consistency.loc[pattern, 'std_change']
                print(f"{pattern}: Mean=${mean_val:.4f}, Std=${std_val:.4f}")

def main():
    """Main execution function."""
    # Get directory path from command line argument
    if len(sys.argv) != 2:
        print("Usage: python three_minute_visualizer.py <analysis_directory_path>")
        print("Example: python three_minute_visualizer.py 3min_analysis_SPY_2023-01-01_to_2024-01-01")
        sys.exit(1)
    
    base_dir = sys.argv[1]
    
    # Validate directory exists
    if not os.path.isdir(base_dir):
        print(f"Error: Directory not found: {base_dir}")
        sys.exit(1)
    
    print("="*80)
    print("3-MINUTE PATTERN VISUALIZATION SYSTEM")
    print("="*80)
    print(f"Processing data from: {base_dir}")
    print("-"*80)
    
    try:
        # Initialize visualizer
        visualizer = ThreeMinutePatternVisualizer(base_dir)
        
        # Process each offset
        for offset in range(3):
            print(f"\n📊 Processing Offset {offset}...")
            
            try:
                df = visualizer.load_pattern_data(offset)
                print(f"✓ Loaded {len(df)} patterns for offset {offset}")
                
                # Create visualizations for this offset
                print(f"  • Creating overview dashboard for offset {offset}...")
                visualizer.create_overview_dashboard(df, offset)
                print(f"    ✓ Saved: pattern_overview_dashboard_offset_{offset}.png")
                
                print(f"  • Creating profitability heatmap for offset {offset}...")
                visualizer.create_profitability_heatmap(df, offset)
                print(f"    ✓ Saved: pattern_profitability_analysis_offset_{offset}.png")
                
                print(f"  • Creating timeline visualization for offset {offset}...")
                visualizer.create_pattern_occurrences_timeline(offset)
                print(f"    ✓ Saved: pattern_timeline_offset_{offset}.png")
                
            except FileNotFoundError:
                print(f"  ⚠ No data found for offset {offset}, skipping...")
                continue
        
        # Create offset comparison
        print("\n📊 Creating offset comparison analysis...")
        visualizer.create_offset_comparison()
        print("  ✓ Saved: offset_comparison_analysis.png")
        
        # Export enhanced summary
        print("\n📝 Exporting enhanced summary...")
        visualizer.export_enhanced_summary()
        
        print("\n✅ Visualization complete!")
        print(f"All outputs saved to: {base_dir}/")
        
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()