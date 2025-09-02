import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import glob
import os
import sys

def combine_pattern_summaries(base_dir: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Combine pattern summaries from different offsets into DataFrames."""
    all_data = []
    
    # Process each offset's summary file
    for offset in range(5):  # 0-4 offsets
        # Use os.path.join for proper path construction
        file_pattern = os.path.join(base_dir, f"summary_{offset}_offset.csv")
        files = glob.glob(file_pattern)
        
        if files:
            print(f"Processing {files[0]}...")
            df = pd.read_csv(files[0])
            df['offset'] = offset
            all_data.append(df)
            print(f"Added offset {offset} data with {len(df)} patterns")
    
    if not all_data:
        raise FileNotFoundError(f"No pattern summary files found in directory: {base_dir}")
    
    # Combine all offset data
    combined_df = pd.concat(all_data, ignore_index=True)
    
    # Create two pivot tables
    # 1. For total changes
    pivot_changes = combined_df.pivot(
        index='pattern',
        columns='offset',
        values='total_change'
    )
    pivot_changes.columns = [f'offset_{i}' for i in pivot_changes.columns]
    
    # 2. For occurrences
    pivot_occurrences = combined_df.pivot(
        index='pattern',
        columns='offset',
        values='occurrences'
    )
    pivot_occurrences.columns = [f'offset_{i}' for i in pivot_occurrences.columns]
    
    return pivot_changes, pivot_occurrences

def plot_pattern_changes(pivot_changes: pd.DataFrame, base_dir: str):
    """Create visualizations of pattern changes across offsets."""
    plt.style.use('default')
    
    # Create figure with two subplots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 20), facecolor='white')
    fig.patch.set_facecolor('white')
    
    # 1. Heatmap of pattern changes
    sns.heatmap(pivot_changes, 
                annot=True, 
                fmt='.3f',
                cmap='RdYlBu_r',
                center=0,
                ax=ax1,
                cbar_kws={'label': 'Change Value'})
    
    ax1.set_title('Pattern Price Changes Across Offsets', 
                  fontsize=14, pad=20)
    ax1.set_xlabel('Offset Number')
    ax1.set_ylabel('Pattern')
    ax1.set_facecolor('white')
    
    # 2. Bar chart of changes
    bar_positions = range(len(pivot_changes.index))
    bar_width = 0.15
    
    for i, col in enumerate(pivot_changes.columns):
        offset = int(col.split('_')[1])
        ax2.bar([x + (i * bar_width) for x in bar_positions], 
                pivot_changes[col],
                bar_width,
                label=f'Offset {offset}',
                alpha=0.7)
    
    ax2.set_title('Pattern Price Changes by Offset', fontsize=14, pad=20)
    ax2.set_xlabel('Pattern')
    ax2.set_ylabel('Total Change')
    ax2.set_xticks([x + (bar_width * 2) for x in bar_positions])
    ax2.set_xticklabels(pivot_changes.index, rotation=45, ha='right')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.set_facecolor('white')
    
    plt.tight_layout()
    plt.savefig(f"{base_dir}/pattern_changes_analysis.png", 
                dpi=300, bbox_inches='tight', 
                facecolor='white', edgecolor='none')
    plt.close()

def plot_pattern_occurrences(pivot_occurrences: pd.DataFrame, base_dir: str):
    """Create visualizations of pattern occurrences across offsets."""
    plt.style.use('default')
    
    # Create figure with two subplots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 20), facecolor='white')
    fig.patch.set_facecolor('white')
    
    # 1. Heatmap of occurrences
    sns.heatmap(pivot_occurrences,
                annot=True,
                fmt='g',
                cmap='YlOrRd',
                ax=ax1,
                cbar_kws={'label': 'Number of Occurrences'})
    
    ax1.set_title('Pattern Occurrences Across Offsets', 
                  fontsize=14, pad=20)
    ax1.set_xlabel('Offset Number')
    ax1.set_ylabel('Pattern')
    ax1.set_facecolor('white')
    
    # 2. Bar chart of occurrences
    bar_positions = range(len(pivot_occurrences.index))
    bar_width = 0.15
    
    for i, col in enumerate(pivot_occurrences.columns):
        offset = int(col.split('_')[1])
        ax2.bar([x + (i * bar_width) for x in bar_positions], 
                pivot_occurrences[col],
                bar_width,
                label=f'Offset {offset}',
                alpha=0.7)
    
    ax2.set_title('Pattern Occurrences by Offset', fontsize=14, pad=20)
    ax2.set_xlabel('Pattern')
    ax2.set_ylabel('Number of Occurrences')
    ax2.set_xticks([x + (bar_width * 2) for x in bar_positions])
    ax2.set_xticklabels(pivot_occurrences.index, rotation=45, ha='right')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.set_facecolor('white')
    
    plt.tight_layout()
    plt.savefig(f"{base_dir}/pattern_occurrences_analysis.png", 
                dpi=300, bbox_inches='tight', 
                facecolor='white', edgecolor='none')
    plt.close()

def main():
    # Get directory path from command line argument
    if len(sys.argv) != 2:
        print("Usage: python matplot.py <diagnostic_directory_path>")
        print("Example: python matplot.py src/buckets/diagnostic_GLD_2025-08-22_to_2025-08-29")
        sys.exit(1)
        
    base_dir = sys.argv[1]
    
    # Validate directory exists
    if not os.path.isdir(base_dir):
        print(f"Error: Directory not found: {base_dir}")
        sys.exit(1)
    
    try:
        # Combine pattern summaries
        pivot_changes, pivot_occurrences = combine_pattern_summaries(base_dir)
        
        # Save combined data - changes
        pivot_changes.to_csv(os.path.join(base_dir, "combined_pattern_changes.csv"))
        print(f"Combined changes analysis saved to: {os.path.join(base_dir, 'combined_pattern_changes.csv')}")
        
        # Save combined data - occurrences 
        pivot_occurrences.to_csv(os.path.join(base_dir, "combined_pattern_occurrences.csv"))
        print(f"Combined occurrences analysis saved to: {os.path.join(base_dir, 'combined_pattern_occurrences.csv')}")
        
        # Create separate visualizations
        plot_pattern_changes(pivot_changes, base_dir)
        plot_pattern_occurrences(pivot_occurrences, base_dir)
        print(f"Changes visualization saved to: {os.path.join(base_dir, 'pattern_changes_analysis.png')}")
        print(f"Occurrences visualization saved to: {os.path.join(base_dir, 'pattern_occurrences_analysis.png')}")
        
        # Print summary statistics
        print("\nSummary Statistics:")
        print("==================")
        print(f"Total Patterns Analyzed: {len(pivot_changes)}")
        
        print("\nMean Changes by Offset:")
        for col in pivot_changes.columns:
            print(f"{col}: {pivot_changes[col].mean():.4f}")
            
        print("\nTotal Occurrences by Offset:")
        for col in pivot_occurrences.columns:
            print(f"{col}: {pivot_occurrences[col].sum():,.0f}")
        
        # Create a combined summary with both changes and occurrences
        combined_summary = pd.DataFrame({
            'pattern': pivot_changes.index,
            'mean_change': pivot_changes.mean(axis=1),
            'total_occurrences': pivot_occurrences.sum(axis=1),
            'min_change': pivot_changes.min(axis=1),
            'max_change': pivot_changes.max(axis=1),
            'change_std': pivot_changes.std(axis=1)
        })
        
        combined_summary = combined_summary.sort_values('total_occurrences', ascending=False)
        combined_summary.to_csv(os.path.join(base_dir, "pattern_complete_summary.csv"), index=False)
        print(f"\nComplete summary saved to: {os.path.join(base_dir, 'pattern_complete_summary.csv')}")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()