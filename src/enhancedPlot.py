import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import glob
import os
import sys
from matplotlib.patches import Rectangle
from matplotlib.gridspec import GridSpec

class EnhancedPatternVisualizer:
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
    
    def load_pattern_data(self) -> pd.DataFrame:
        """Load the pattern analysis summary data."""
        summary_file = os.path.join(self.base_dir, "pattern_analysis_summary.csv")
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
            
            # Determine pattern type
            if p_count >= 3:
                pattern_type = 'P-Heavy'
            elif n_count >= 3:
                pattern_type = 'N-Heavy'
            elif o_count >= 3:
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
    
    def create_overview_dashboard(self, df: pd.DataFrame):
        """Create a comprehensive 4-panel dashboard."""
        fig = plt.figure(figsize=(20, 16))
        gs = GridSpec(2, 2, figure=fig, hspace=0.3, wspace=0.3)
        
        # Panel 1: Top 15 Profitable Patterns
        ax1 = fig.add_subplot(gs[0, 0])
        top_patterns = df.nlargest(15, 'avg_change')
        
        colors = ['green' if x > 0 else 'red' for x in top_patterns['avg_change']]
        bars = ax1.barh(range(len(top_patterns)), top_patterns['avg_change'], color=colors, alpha=0.7)
        ax1.set_yticks(range(len(top_patterns)))
        ax1.set_yticklabels(top_patterns['pattern'])
        ax1.set_xlabel('Average Change ($)')
        ax1.set_title('Top 15 Most Profitable Patterns', fontsize=14, fontweight='bold')
        ax1.grid(axis='x', alpha=0.3)
        
        # Add value labels
        for i, val in enumerate(top_patterns['avg_change']):
            ax1.text(val, i, f' ${val:.4f}', va='center', fontsize=9)
        
        # Panel 2: Pattern Frequency Distribution
        ax2 = fig.add_subplot(gs[0, 1])
        
        # Get top 20 by frequency
        top_freq = df.nlargest(20, 'count')
        ax2.bar(range(len(top_freq)), top_freq['count'], 
                color=plt.cm.viridis(np.linspace(0.3, 0.9, len(top_freq))), alpha=0.8)
        ax2.set_xticks(range(len(top_freq)))
        ax2.set_xticklabels(top_freq['pattern'], rotation=45, ha='right')
        ax2.set_ylabel('Number of Occurrences')
        ax2.set_title('Top 20 Most Frequent Patterns', fontsize=14, fontweight='bold')
        ax2.grid(axis='y', alpha=0.3)
        
        # Panel 3: Win Rate vs Average Change Scatter
        ax3 = fig.add_subplot(gs[1, 0])
        
        # Ensure we have the columns we need
        if 'win_rate_pct' in df.columns and 'return_risk_ratio' in df.columns:
            scatter = ax3.scatter(df['win_rate_pct'], df['avg_change'], 
                                s=df['count']*2, alpha=0.6, 
                                c=df['return_risk_ratio'], cmap='RdYlGn')
            ax3.set_xlabel('Win Rate (%)')
            ax3.set_ylabel('Average Change ($)')
            ax3.set_title('Pattern Performance: Win Rate vs Profitability', fontsize=14, fontweight='bold')
            ax3.axhline(y=0, color='black', linestyle='--', alpha=0.3)
            ax3.axvline(x=50, color='black', linestyle='--', alpha=0.3)
            ax3.grid(alpha=0.3)
            
            # Add colorbar
            cbar = plt.colorbar(scatter, ax=ax3)
            cbar.set_label('Return/Risk Ratio', rotation=270, labelpad=15)
            
            # Add annotations for best patterns
            best_patterns = df.nlargest(5, 'return_risk_ratio')
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
        ax4.set_title('Pattern Type Distribution', fontsize=14, fontweight='bold')
        ax4.grid(axis='y', alpha=0.3)
        
        # Add average change as secondary info
        ax4_twin = ax4.twinx()
        ax4_twin.plot(range(len(type_stats)), type_stats['avg_change'], 
                     'ko-', linewidth=2, markersize=8, label='Avg Change')
        ax4_twin.set_ylabel('Average Change ($)')
        ax4_twin.legend(loc='upper right')
        
        plt.suptitle('Enhanced Pattern Analysis Dashboard - 3-Type Classification (P/N/O)', 
                    fontsize=16, fontweight='bold', y=1.02)
        
        plt.savefig(os.path.join(self.base_dir, 'pattern_overview_dashboard.png'), 
                   dpi=300, bbox_inches='tight')
        plt.close()
    
    def create_profitability_heatmap(self, df: pd.DataFrame):
        """Create a heatmap showing pattern profitability."""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 10))
        
        # Prepare data for heatmap (5x49 grid for 245 patterns, but we'll show what we have)
        # Create a matrix representation
        patterns_matrix = []
        patterns_labels = []
        
        # Sort patterns by average change
        df_sorted = df.sort_values('avg_change', ascending=False)
        
        # Take top 50 patterns for visibility
        top_50 = df_sorted.head(50)
        
        # Reshape for heatmap (10x5)
        matrix_data = np.zeros((10, 5))
        matrix_labels = [['' for _ in range(5)] for _ in range(10)]
        
        for idx, (_, row) in enumerate(top_50.iterrows()):
            if idx < 50:
                row_idx = idx // 5
                col_idx = idx % 5
                matrix_data[row_idx, col_idx] = row['avg_change']
                matrix_labels[row_idx][col_idx] = row['pattern']
        
        # Heatmap 1: Top 50 by profitability
        sns.heatmap(matrix_data, annot=matrix_labels, fmt='', 
                   cmap='RdYlGn', center=0, ax=ax1,
                   cbar_kws={'label': 'Average Change ($)'})
        ax1.set_title('Top 50 Patterns by Profitability', fontsize=14, fontweight='bold')
        ax1.set_xlabel('Position')
        ax1.set_ylabel('Rank Group')
        
        # Heatmap 2: Pattern composition vs performance
        composition_df = self.analyze_pattern_composition(df)
        pivot_data = composition_df.pivot_table(
            values='avg_change',
            index='P_count',
            columns='N_count',
            aggfunc='mean'
        )
        
        sns.heatmap(pivot_data, annot=True, fmt='.4f', 
                   cmap='RdYlGn', center=0, ax=ax2,
                   cbar_kws={'label': 'Average Change ($)'})
        ax2.set_title('Average Performance by P/N Composition', fontsize=14, fontweight='bold')
        ax2.set_xlabel('Number of N (Negative) Candles')
        ax2.set_ylabel('Number of P (Positive) Candles')
        
        plt.suptitle('Pattern Profitability Analysis', fontsize=16, fontweight='bold')
        plt.tight_layout()
        
        plt.savefig(os.path.join(self.base_dir, 'pattern_profitability_analysis.png'), 
                   dpi=300, bbox_inches='tight')
        plt.close()
    
    def create_statistical_analysis(self, df: pd.DataFrame):
        """Create statistical analysis visualizations."""
        fig, axes = plt.subplots(2, 3, figsize=(18, 12))
        
        # Plot 1: Distribution of average changes
        axes[0, 0].hist(df['avg_change'], bins=30, edgecolor='black', alpha=0.7, color='skyblue')
        axes[0, 0].axvline(df['avg_change'].mean(), color='red', linestyle='--', label=f'Mean: {df["avg_change"].mean():.4f}')
        axes[0, 0].axvline(df['avg_change'].median(), color='green', linestyle='--', label=f'Median: {df["avg_change"].median():.4f}')
        axes[0, 0].set_xlabel('Average Change ($)')
        axes[0, 0].set_ylabel('Number of Patterns')
        axes[0, 0].set_title('Distribution of Pattern Performance')
        axes[0, 0].legend()
        axes[0, 0].grid(alpha=0.3)
        
        # Plot 2: Risk vs Return
        if 'std_dev' in df.columns and 'return_risk_ratio' in df.columns:
            axes[0, 1].scatter(df['std_dev'], df['avg_change'], 
                             s=df['count']*2, alpha=0.6, c=df['count'], cmap='viridis')
            axes[0, 1].set_xlabel('Standard Deviation (Risk)')
            axes[0, 1].set_ylabel('Average Change (Return)')
            axes[0, 1].set_title('Risk-Return Profile of Patterns')
            axes[0, 1].grid(alpha=0.3)
            
            # Add colorbar
            cbar = plt.colorbar(axes[0, 1].collections[0], ax=axes[0, 1])
            cbar.set_label('Pattern Count', rotation=270, labelpad=15)
        
        # Plot 3: Win Rate Distribution
        if 'win_rate_pct' in df.columns:
            axes[0, 2].hist(df['win_rate_pct'], bins=20, edgecolor='black', alpha=0.7, color='lightgreen')
            axes[0, 2].axvline(50, color='red', linestyle='--', label='50% Win Rate')
            axes[0, 2].set_xlabel('Win Rate (%)')
            axes[0, 2].set_ylabel('Number of Patterns')
            axes[0, 2].set_title('Distribution of Win Rates')
            axes[0, 2].legend()
            axes[0, 2].grid(alpha=0.3)
        
        # Plot 4: Pattern frequency distribution
        axes[1, 0].hist(df['count'], bins=30, edgecolor='black', alpha=0.7, color='coral')
        axes[1, 0].set_xlabel('Number of Occurrences')
        axes[1, 0].set_ylabel('Number of Patterns')
        axes[1, 0].set_title('Pattern Frequency Distribution')
        axes[1, 0].grid(alpha=0.3)
        
        # Plot 5: Correlation matrix
        numeric_cols = ['count', 'avg_change', 'std_dev', 'win_rate_pct', 'return_risk_ratio']
        available_cols = [col for col in numeric_cols if col in df.columns]
        
        if len(available_cols) > 1:
            corr_matrix = df[available_cols].corr()
            sns.heatmap(corr_matrix, annot=True, fmt='.2f', cmap='coolwarm', 
                       center=0, ax=axes[1, 1])
            axes[1, 1].set_title('Correlation Matrix of Pattern Metrics')
        
        # Plot 6: Top patterns by different metrics
        metrics_comparison = pd.DataFrame({
            'By Profit': df.nlargest(10, 'avg_change')['pattern'].values[:10],
            'By Frequency': df.nlargest(10, 'count')['pattern'].values[:10],
            'By Consistency': df.nlargest(10, 'return_risk_ratio')['pattern'].values[:10] if 'return_risk_ratio' in df.columns else ['N/A']*10
        })
        
        axes[1, 2].axis('tight')
        axes[1, 2].axis('off')
        table = axes[1, 2].table(cellText=metrics_comparison.values,
                                colLabels=metrics_comparison.columns,
                                cellLoc='center',
                                loc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1.2, 1.5)
        axes[1, 2].set_title('Top 10 Patterns by Different Metrics', pad=20)
        
        plt.suptitle('Statistical Analysis of Pattern Performance', fontsize=16, fontweight='bold')
        plt.tight_layout()
        
        plt.savefig(os.path.join(self.base_dir, 'pattern_statistics_analysis.png'), 
                   dpi=300, bbox_inches='tight')
        plt.close()
    
    def create_pattern_composition_analysis(self, df: pd.DataFrame):
        """Create detailed pattern composition analysis."""
        composition_df = self.analyze_pattern_composition(df)
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        
        # Plot 1: Stacked bar chart of pattern compositions
        pattern_types = composition_df['pattern_type'].value_counts()
        colors = {'P-Heavy': 'green', 'N-Heavy': 'red', 'O-Heavy': 'gray', 'Mixed': 'blue'}
        
        ax1 = axes[0, 0]
        bars = []
        for ptype in ['P-Heavy', 'N-Heavy', 'O-Heavy', 'Mixed']:
            if ptype in pattern_types.index:
                bars.append(pattern_types[ptype])
            else:
                bars.append(0)
        
        bar_colors = [colors[pt] for pt in ['P-Heavy', 'N-Heavy', 'O-Heavy', 'Mixed']]
        ax1.pie(bars, labels=['P-Heavy', 'N-Heavy', 'O-Heavy', 'Mixed'], 
                colors=bar_colors, autopct='%1.1f%%', startangle=90)
        ax1.set_title('Distribution of Pattern Types', fontsize=12, fontweight='bold')
        
        # Plot 2: Average performance by pattern type
        ax2 = axes[0, 1]
        type_performance = composition_df.groupby('pattern_type')['avg_change'].mean().sort_values()
        colors_list = [colors.get(pt, 'gray') for pt in type_performance.index]
        
        bars = ax2.barh(range(len(type_performance)), type_performance.values, color=colors_list, alpha=0.7)
        ax2.set_yticks(range(len(type_performance)))
        ax2.set_yticklabels(type_performance.index)
        ax2.set_xlabel('Average Change ($)')
        ax2.set_title('Performance by Pattern Type', fontsize=12, fontweight='bold')
        ax2.grid(axis='x', alpha=0.3)
        
        # Add value labels
        for i, val in enumerate(type_performance.values):
            ax2.text(val, i, f' ${val:.4f}', va='center')
        
        # Plot 3: 3D composition scatter
        ax3 = axes[1, 0]
        scatter = ax3.scatter(composition_df['P_count'], composition_df['N_count'], 
                            s=composition_df['count']*5, 
                            c=composition_df['avg_change'], 
                            cmap='RdYlGn', alpha=0.6)
        ax3.set_xlabel('P Count')
        ax3.set_ylabel('N Count')
        ax3.set_title('Pattern Composition Space', fontsize=12, fontweight='bold')
        ax3.grid(alpha=0.3)
        
        # Add colorbar
        cbar = plt.colorbar(scatter, ax=ax3)
        cbar.set_label('Avg Change ($)', rotation=270, labelpad=15)
        
        # Plot 4: Win rate by pattern type
        ax4 = axes[1, 1]
        if 'win_rate' in composition_df.columns:
            type_winrate = composition_df.groupby('pattern_type')['win_rate'].mean().sort_values()
            colors_list = [colors.get(pt, 'gray') for pt in type_winrate.index]
            
            bars = ax4.barh(range(len(type_winrate)), type_winrate.values, color=colors_list, alpha=0.7)
            ax4.set_yticks(range(len(type_winrate)))
            ax4.set_yticklabels(type_winrate.index)
            ax4.set_xlabel('Average Win Rate (%)')
            ax4.set_title('Win Rate by Pattern Type', fontsize=12, fontweight='bold')
            ax4.axvline(x=50, color='black', linestyle='--', alpha=0.3, label='50% baseline')
            ax4.legend()
            ax4.grid(axis='x', alpha=0.3)
            
            # Add value labels
            for i, val in enumerate(type_winrate.values):
                ax4.text(val, i, f' {val:.1f}%', va='center')
        
        plt.suptitle('Pattern Composition Analysis (P/N/O Classification)', 
                    fontsize=16, fontweight='bold')
        plt.tight_layout()
        
        plt.savefig(os.path.join(self.base_dir, 'pattern_composition_analysis.png'), 
                   dpi=300, bbox_inches='tight')
        plt.close()
    
    def export_enhanced_summary(self, df: pd.DataFrame):
        """Export an enhanced summary with all metrics."""
        composition_df = self.analyze_pattern_composition(df)
        
        # Merge composition data with original data
        enhanced_df = df.merge(
            composition_df[['pattern', 'P_count', 'N_count', 'O_count', 'pattern_type']], 
            on='pattern'
        )
        
        # Sort by average change
        enhanced_df = enhanced_df.sort_values('avg_change', ascending=False)
        
        # Save to CSV
        output_file = os.path.join(self.base_dir, 'enhanced_pattern_summary.csv')
        enhanced_df.to_csv(output_file, index=False)
        
        print(f"Enhanced summary saved to: {output_file}")
        
        # Print summary statistics
        print("\n" + "="*80)
        print("PATTERN ANALYSIS SUMMARY STATISTICS")
        print("="*80)
        
        print(f"\nTotal Patterns Found: {len(df)}")
        print(f"Total Pattern Occurrences: {df['count'].sum()}")
        print(f"Average Pattern Frequency: {df['count'].mean():.2f}")
        
        print("\nPattern Type Distribution:")
        print("-"*40)
        type_counts = composition_df['pattern_type'].value_counts()
        for ptype, count in type_counts.items():
            print(f"{ptype}: {count} patterns ({count/len(df)*100:.1f}%)")
        
        print("\nPerformance Metrics:")
        print("-"*40)
        print(f"Best Pattern: {df.iloc[0]['pattern']} (Avg: ${df.iloc[0]['avg_change']:.4f})")
        print(f"Worst Pattern: {df.iloc[-1]['pattern']} (Avg: ${df.iloc[-1]['avg_change']:.4f})")
        print(f"Mean Performance: ${df['avg_change'].mean():.4f}")
        print(f"Median Performance: ${df['avg_change'].median():.4f}")
        
        if 'win_rate_pct' in df.columns:
            print(f"Average Win Rate: {df['win_rate_pct'].mean():.1f}%")
            print(f"Patterns with >50% Win Rate: {(df['win_rate_pct'] > 50).sum()}")
        
        if 'return_risk_ratio' in df.columns:
            print(f"Best Risk-Adjusted Pattern: {df.loc[df['return_risk_ratio'].idxmax(), 'pattern']}")
            print(f"Average Return/Risk Ratio: {df['return_risk_ratio'].mean():.4f}")
        
        print("\nTop 5 Most Profitable Patterns:")
        print("-"*40)
        for i, row in df.head(5).iterrows():
            print(f"{row['pattern']}: ${row['avg_change']:.4f} ({row['count']} occurrences)")
        
        print("\nTop 5 Most Frequent Patterns:")
        print("-"*40)
        top_freq = df.nlargest(5, 'count')
        for _, row in top_freq.iterrows():
            print(f"{row['pattern']}: {row['count']} occurrences (${row['avg_change']:.4f} avg)")

    def load_offset_data(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Load data from offset analysis files."""
        offsets_data = []
        
        # Load data from each offset file
        for offset in range(5):
            file_path = os.path.join(self.base_dir, f"summary_{offset}_offset.csv")
            if os.path.exists(file_path):
                df = pd.read_csv(file_path)
                df['offset'] = offset
                offsets_data.append(df)
        
        if not offsets_data:
            raise FileNotFoundError("No offset summary files found")
            
        # Combine all offset data
        combined_df = pd.concat(offsets_data, ignore_index=True)
        
        # Create pivot tables for changes and occurrences
        changes_pivot = combined_df.pivot(
            index='pattern',
            columns='offset',
            values='total_change'
        )
        
        occurrences_pivot = combined_df.pivot(
            index='pattern',
            columns='offset',
            values='occurrences'
        )
        
        return changes_pivot, occurrences_pivot

    def create_offset_analysis_plots(self, changes_pivot: pd.DataFrame, occurrences_pivot: pd.DataFrame):
        """Create visualizations for offset analysis."""
        # Create figure with 2x2 subplots
        fig = plt.figure(figsize=(20, 20))
        gs = GridSpec(2, 2, figure=fig, hspace=0.3, wspace=0.3)
        
        # 1. Heatmap of changes across offsets
        ax1 = fig.add_subplot(gs[0, 0])
        sns.heatmap(changes_pivot, 
                   cmap='RdYlBu_r',
                   center=0,
                   annot=True,
                   fmt='.4f',
                   ax=ax1)
        ax1.set_title('Pattern Changes Across Offsets', fontsize=14, fontweight='bold')
        ax1.set_xlabel('Offset')
        ax1.set_ylabel('Pattern')
        
        # 2. Heatmap of occurrences across offsets
        ax2 = fig.add_subplot(gs[0, 1])
        sns.heatmap(occurrences_pivot,
                   cmap='YlOrRd',
                   annot=True,
                   fmt='g',
                   ax=ax2)
        ax2.set_title('Pattern Occurrences Across Offsets', fontsize=14, fontweight='bold')
        ax2.set_xlabel('Offset')
        ax2.set_ylabel('Pattern')
        
        # 3. Box plot of changes by offset
        ax3 = fig.add_subplot(gs[1, 0])
        changes_pivot.boxplot(ax=ax3)
        ax3.set_title('Distribution of Changes by Offset', fontsize=14, fontweight='bold')
        ax3.set_xlabel('Offset')
        ax3.set_ylabel('Total Change')
        ax3.grid(True, alpha=0.3)
        
        # 4. Pattern consistency analysis
        ax4 = fig.add_subplot(gs[1, 1])
        
        # Calculate consistency metrics
        std_changes = changes_pivot.std(axis=1)
        mean_changes = changes_pivot.mean(axis=1)
        total_occurrences = occurrences_pivot.sum(axis=1)
        
        scatter = ax4.scatter(std_changes, mean_changes, 
                            s=total_occurrences/5,  # Size based on occurrences
                            alpha=0.6,
                            c=total_occurrences,
                            cmap='viridis')
        
        ax4.set_title('Pattern Consistency Analysis', fontsize=14, fontweight='bold')
        ax4.set_xlabel('Standard Deviation of Changes')
        ax4.set_ylabel('Mean Change')
        ax4.grid(True, alpha=0.3)
        
        # Add colorbar
        cbar = plt.colorbar(scatter, ax=ax4)
        cbar.set_label('Total Occurrences', rotation=270, labelpad=15)
        
        # Add annotations for most consistent patterns
        consistency_ratio = abs(mean_changes/std_changes)
        top_consistent = consistency_ratio.nlargest(5)
        for pattern in top_consistent.index:
            ax4.annotate(pattern, 
                        (std_changes[pattern], mean_changes[pattern]),
                        xytext=(5, 5), textcoords='offset points',
                        fontsize=8)
        
        plt.suptitle('4-Minute Pattern Offset Analysis', fontsize=16, fontweight='bold')
        
        # Save plot
        plt.savefig(os.path.join(self.base_dir, 'offset_analysis.png'), 
                    dpi=300, bbox_inches='tight')
        plt.close()

    def export_offset_summary(self, changes_pivot: pd.DataFrame, occurrences_pivot: pd.DataFrame):
        """Export summary statistics for offset analysis."""
        summary_data = []
        
        for pattern in changes_pivot.index:
            changes = changes_pivot.loc[pattern]
            occurrences = occurrences_pivot.loc[pattern]
            
            summary_data.append({
                'pattern': pattern,
                'mean_change': changes.mean(),
                'std_change': changes.std(),
                'total_occurrences': occurrences.sum(),
                'consistency_ratio': abs(changes.mean()/changes.std()) if changes.std() != 0 else float('inf'),
                'max_change_diff': changes.max() - changes.min(),
                'occurrence_stability': occurrences.std()/occurrences.mean() if occurrences.mean() != 0 else float('inf')
            })
        
        summary_df = pd.DataFrame(summary_data)
        summary_df = summary_df.sort_values('consistency_ratio', ascending=False)
        
        # Save to CSV
        output_file = os.path.join(self.base_dir, 'offset_analysis_summary.csv')
        summary_df.to_csv(output_file, index=False)
        print(f"\nOffset analysis summary saved to: {output_file}")

def main():
    """Main execution function."""
    # Get directory path from command line argument
    if len(sys.argv) != 2:
        print("Usage: python matplot_enhanced.py <analysis_directory_path>")
        print("Example: python matplot_enhanced.py enhanced_analysis_GLD_2025-01-01_to_2025-01-07")
        sys.exit(1)
    
    base_dir = sys.argv[1]
    
    # Validate directory exists
    if not os.path.isdir(base_dir):
        print(f"Error: Directory not found: {base_dir}")
        sys.exit(1)
    
    print("="*80)
    print("ENHANCED PATTERN VISUALIZATION SYSTEM")
    print("="*80)
    print(f"Processing data from: {base_dir}")
    print("-"*80)
    
    try:
        # Initialize visualizer
        visualizer = EnhancedPatternVisualizer(base_dir)
        
        # Load pattern data
        print("\n📊 Loading pattern data...")
        df = visualizer.load_pattern_data()
        print(f"✓ Loaded {len(df)} patterns")
        
        # Create visualizations
        print("\n🎨 Creating visualizations...")
        
        print("  • Creating overview dashboard...")
        visualizer.create_overview_dashboard(df)
        print("    ✓ Saved: pattern_overview_dashboard.png")
        
        print("  • Creating profitability heatmap...")
        visualizer.create_profitability_heatmap(df)
        print("    ✓ Saved: pattern_profitability_analysis.png")
        
        print("  • Creating statistical analysis...")
        visualizer.create_statistical_analysis(df)
        print("    ✓ Saved: pattern_statistics_analysis.png")
        
        print("  • Creating composition analysis...")
        visualizer.create_pattern_composition_analysis(df)
        print("    ✓ Saved: pattern_composition_analysis.png")
        
        # Load offset data
        print("\n📊 Loading offset analysis data...")
        changes_pivot, occurrences_pivot = visualizer.load_offset_data()
        
        # Create offset analysis plots
        print("  • Creating offset analysis plots...")
        visualizer.create_offset_analysis_plots(changes_pivot, occurrences_pivot)
        print("    ✓ Saved: offset_analysis.png")
        
        print("\n📁 Exporting enhanced summary...")
        visualizer.export_enhanced_summary(df)
        visualizer.export_offset_summary(changes_pivot, occurrences_pivot)
        
        print("\n✅ Visualization complete!")
        print(f"All outputs saved to: {base_dir}/")
        
    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
        print("Make sure you run the enhanced pattern analyzer first to generate the data.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()