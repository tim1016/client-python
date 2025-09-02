import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
import os
from typing import Optional, List

class CSVContourPlotter:
    """
    Standalone contour plotter for CSV files with pivoted intraday data.
    Expects CSV format: rows = dates, columns = time intervals, values = variable data
    """
    
    def __init__(self):
        """Initialize the contour plotter."""
        pass
    
    def plot_contour_from_csv(self, csv_file: str, variable_name: str = None, 
                             colormap: str = 'viridis', save_plot: bool = True, 
                             show_plot: bool = True, output_dir: str = None) -> str:
        """
        Create a contour plot from a CSV file.
        
        Args:
            csv_file: Path to CSV file with pivoted data
            variable_name: Name of the variable (for title). If None, extracted from filename
            colormap: Matplotlib colormap name ('viridis', 'plasma', 'coolwarm', etc.)
            save_plot: Whether to save the plot as PNG
            show_plot: Whether to display the plot
            output_dir: Directory to save plot (default: same as CSV file)
            
        Returns:
            Filename of saved plot (if saved)
        """
        if not os.path.exists(csv_file):
            raise FileNotFoundError(f"CSV file not found: {csv_file}")
        
        print(f"Loading data from: {csv_file}")
        
        # Load CSV data
        df = pd.read_csv(csv_file, index_col=0)  # First column (dates) as index
        
        if df.empty:
            print("CSV file is empty")
            return ""
        
        # Extract variable name from filename if not provided
        if variable_name is None:
            filename = os.path.basename(csv_file)
            variable_name = self._extract_variable_from_filename(filename)
        
        print(f"Creating contour plot for {variable_name}...")
        print(f"Data shape: {df.shape[0]} days x {df.shape[1]} time intervals")
        
        # Prepare data for contour plot
        X, Y, Z = self._prepare_contour_data(df)
        
        # Create the plot
        fig, ax = plt.subplots(figsize=(15, 10))
        
        # Create contour plot
        contour = ax.contourf(X, Y, Z, levels=50, cmap=colormap, alpha=0.8)
        
        # Add contour lines for better definition
        contour_lines = ax.contour(X, Y, Z, levels=15, colors='white', alpha=0.4, linewidths=0.5)
        
        # Add colorbar
        cbar = plt.colorbar(contour, ax=ax)
        cbar.set_label(f'{variable_name.title()}', rotation=270, labelpad=20, fontsize=12)
        
        # Format axes
        self._format_axes(ax, df, variable_name, csv_file)
        
        # Adjust layout
        plt.tight_layout()
        
        # Save plot
        filename = ""
        if save_plot:
            filename = self._generate_plot_filename(csv_file, variable_name, output_dir)
            plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')
            print(f"Contour plot saved as: {filename}")
        
        # Show plot
        if show_plot:
            plt.show()
        else:
            plt.close()
        
        return filename
    
    def _prepare_contour_data(self, df: pd.DataFrame):
        """
        Prepare X, Y, Z matrices for contour plotting.
        
        Args:
            df: DataFrame with dates as index, time intervals as columns
            
        Returns:
            X, Y, Z matrices for matplotlib contourf
        """
        # Convert time columns to minutes from market open
        time_strings = df.columns.tolist()
        time_minutes = []
        
        for time_str in time_strings:
            try:
                # Handle different time formats (HH:MM, H:MM, etc.)
                if ':' in time_str:
                    hour, minute = map(int, time_str.split(':'))
                else:
                    # If no colon, assume it's just hour
                    hour, minute = int(time_str), 0
                
                # Convert to minutes from market open (9:30 AM = 570 minutes from midnight)
                market_open_minutes = 9 * 60 + 30  # 570 minutes
                current_minutes = hour * 60 + minute
                minutes_from_open = current_minutes - market_open_minutes
                time_minutes.append(minutes_from_open)
            except ValueError:
                # If time parsing fails, use column index
                time_minutes.append(len(time_minutes) * 5)  # Assume 5-minute intervals
        
        # Convert dates to numeric (days from first date)  
        dates = df.index.tolist()
        
        # Handle different date formats
        parsed_dates = []
        for date in dates:
            try:
                if isinstance(date, str):
                    # Try different date formats
                    for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%m/%d/%y', '%Y/%m/%d']:
                        try:
                            parsed_dates.append(datetime.strptime(date, fmt).date())
                            break
                        except ValueError:
                            continue
                    else:
                        # If no format works, use index
                        parsed_dates.append(len(parsed_dates))
                else:
                    parsed_dates.append(date)
            except:
                parsed_dates.append(len(parsed_dates))
        
        # Convert to days from first date
        if all(hasattr(d, 'day') for d in parsed_dates):
            first_date = min(parsed_dates)
            date_numbers = [(d - first_date).days for d in parsed_dates]
        else:
            date_numbers = list(range(len(parsed_dates)))
        
        # Create coordinate matrices
        X, Y = np.meshgrid(time_minutes, date_numbers)
        
        # Convert DataFrame values to numpy array
        Z = df.values.astype(float)
        
        # Handle missing values
        if np.any(np.isnan(Z)):
            print("Warning: Found NaN values, filling with interpolation...")
            # Forward fill, then backward fill
            Z = pd.DataFrame(Z).fillna(method='ffill', axis=1).fillna(method='bfill', axis=1).values
            # If still NaN, fill with column mean
            if np.any(np.isnan(Z)):
                col_means = np.nanmean(Z, axis=0)
                for j in range(Z.shape[1]):
                    Z[np.isnan(Z[:, j]), j] = col_means[j]
        
        return X, Y, Z
    
    def _format_axes(self, ax, df: pd.DataFrame, variable_name: str, csv_file: str):
        """Format the contour plot axes with proper labels and ticks."""
        
        # Extract ticker and interval from filename for title
        filename = os.path.basename(csv_file)
        ticker, interval = self._extract_ticker_and_interval(filename)
        
        # Set title
        title = f"{ticker} {variable_name.title()}"
        if interval:
            title += f" - {interval} Intervals"
        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        
        # X-axis (Time)
        ax.set_xlabel('Minutes from Market Open (9:30 AM)', fontsize=12, fontweight='bold')
        
        # Create time labels for x-axis
        time_strings = df.columns.tolist()
        time_minutes = []
        
        for time_str in time_strings:
            try:
                if ':' in time_str:
                    hour, minute = map(int, time_str.split(':'))
                else:
                    hour, minute = int(time_str), 0
                
                market_open_minutes = 9 * 60 + 30
                current_minutes = hour * 60 + minute
                minutes_from_open = current_minutes - market_open_minutes
                time_minutes.append(minutes_from_open)
            except:
                time_minutes.append(len(time_minutes) * 5)
        
        # Set x-axis ticks - show every ~60 minutes or smart intervals
        num_intervals = len(time_strings)
        if num_intervals <= 20:
            step = 1  # Show all
        elif num_intervals <= 60:
            step = 3  # Show every 3rd
        else:
            step = max(1, num_intervals // 15)  # Show ~15 labels max
        
        tick_indices = list(range(0, len(time_strings), step))
        if len(time_strings) - 1 not in tick_indices:
            tick_indices.append(len(time_strings) - 1)  # Always show last
        
        ax.set_xticks([time_minutes[i] for i in tick_indices])
        ax.set_xticklabels([time_strings[i] for i in tick_indices], rotation=45)
        
        # Y-axis (Days)
        ax.set_ylabel('Trading Days', fontsize=12, fontweight='bold')
        
        # Format date labels for y-axis
        dates = df.index.tolist()
        num_days = len(dates)
        
        if num_days <= 10:
            step = 1  # Show all dates
        elif num_days <= 30:
            step = 2  # Show every other day
        else:
            step = max(1, num_days // 10)  # Show ~10 date labels
        
        tick_indices = list(range(0, num_days, step))
        if num_days - 1 not in tick_indices:
            tick_indices.append(num_days - 1)  # Always show last date
        
        ax.set_yticks(tick_indices)
        
        # Format date labels
        date_labels = []
        for i in tick_indices:
            date = dates[i]
            if isinstance(date, str):
                # Try to parse and reformat
                try:
                    for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%m/%d/%y']:
                        try:
                            parsed = datetime.strptime(date, fmt)
                            date_labels.append(parsed.strftime('%m/%d'))
                            break
                        except ValueError:
                            continue
                    else:
                        date_labels.append(str(date)[:5])  # First 5 chars
                except:
                    date_labels.append(str(date)[:5])
            else:
                date_labels.append(str(date))
        
        ax.set_yticklabels(date_labels)
        
        # Invert y-axis so earliest date is at bottom
        ax.invert_yaxis()
        
        # Add subtle grid
        ax.grid(True, alpha=0.2, linestyle='--')
        
        # Style the plot
        ax.set_facecolor('#fafafa')
        
        # Add stats text box
        self._add_stats_box(ax, df)
    
    def _add_stats_box(self, ax, df: pd.DataFrame):
        """Add a statistics text box to the plot."""
        values = df.values.flatten()
        values = values[~np.isnan(values)]  # Remove NaN values
        
        if len(values) > 0:
            stats_text = f'Min: {values.min():.2f}\nMax: {values.max():.2f}\nMean: {values.mean():.2f}'
            ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, 
                   verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8),
                   fontsize=10)
    
    def _is_dst_change(self, date1: datetime, date2: datetime) -> bool:
        """
        Check if there's a DST change between two dates.
        
        Args:
            date1: First date
            date2: Second date
            
        Returns:
            True if there's likely a DST change between the dates
        """
        # Simple heuristic: DST changes typically happen in March and November
        # and cause significant time shifts in trading data
        month1, month2 = date1.month, date2.month
        
        # Check if we're crossing DST boundaries (rough approximation)
        dst_months = [3, 11]  # March (spring forward) and November (fall back)
        
        # If dates span across DST change months, it might be a DST change
        if month1 != month2 and (month1 in dst_months or month2 in dst_months):
            return True
        
        return False
    
    def _extract_variable_from_filename(self, filename: str) -> str:
        """Extract variable name from CSV filename."""
        # Common patterns: ticker_interval_variable_dates.csv
        parts = filename.replace('.csv', '').split('_')
        
        # Look for common variable names
        variables = ['open', 'high', 'low', 'close', 'volume', 'vwap']
        for part in parts:
            if part.lower() in variables:
                return part.lower()
        
        # If not found, use filename without extension
        return filename.replace('.csv', '').replace('_', ' ').title()
    
    def _extract_ticker_and_interval(self, filename: str) -> tuple:
        """Extract ticker and interval information from filename."""
        parts = filename.replace('.csv', '').split('_')
        
        ticker = "Stock"  # Default
        interval = ""
        
        if len(parts) >= 2:
            ticker = parts[0].upper()
            
            # Look for interval pattern (e.g., "5min", "15min")
            for part in parts:
                if 'min' in part.lower():
                    interval = part
                    break
        
        return ticker, interval
    
    def _generate_plot_filename(self, csv_file: str, variable_name: str, output_dir: str = None) -> str:
        """Generate filename for the saved plot."""
        base_name = os.path.splitext(os.path.basename(csv_file))[0]
        plot_filename = f"{base_name}_contour.png"
        
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            plot_filename = os.path.join(output_dir, plot_filename)
        else:
            # Save in same directory as CSV file
            csv_dir = os.path.dirname(csv_file)
            if csv_dir:
                plot_filename = os.path.join(csv_dir, plot_filename)
        
        return plot_filename
    
    def plot_multiple_csv_files(self, csv_files: List[str], colormap: str = 'viridis',
                               save_plots: bool = True, show_plots: bool = False,
                               output_dir: str = None) -> List[str]:
        """
        Create contour plots for multiple CSV files.
        
        Args:
            csv_files: List of CSV file paths
            colormap: Matplotlib colormap name
            save_plots: Whether to save plots
            show_plots: Whether to display plots  
            output_dir: Directory to save plots
            
        Returns:
            List of saved plot filenames
        """
        saved_files = []
        
        print(f"Creating contour plots for {len(csv_files)} CSV files...")
        
        for csv_file in csv_files:
            try:
                filename = self.plot_contour_from_csv(
                    csv_file=csv_file,
                    colormap=colormap,
                    save_plot=save_plots,
                    show_plot=show_plots,
                    output_dir=output_dir
                )
                if filename:
                    saved_files.append(filename)
            except Exception as e:
                print(f"Error processing {csv_file}: {e}")
        
        print(f"Successfully created {len(saved_files)} contour plots")
        return saved_files


# Convenience functions for easy usage

def plot_csv_contour(csv_file: str, colormap: str = 'viridis', save_plot: bool = True, 
                    show_plot: bool = True) -> str:
    """
    Simple function to create a contour plot from a CSV file.
    
    Args:
        csv_file: Path to CSV file with pivoted data
        colormap: Matplotlib colormap ('viridis', 'plasma', 'coolwarm', etc.)
        save_plot: Whether to save the plot
        show_plot: Whether to display the plot
        
    Returns:
        Filename of saved plot
    """
    plotter = CSVContourPlotter()
    return plotter.plot_contour_from_csv(csv_file, colormap=colormap, 
                                        save_plot=save_plot, show_plot=show_plot)

def plot_multiple_csvs(csv_files: List[str], colormap: str = 'viridis') -> List[str]:
    """
    Create contour plots for multiple CSV files.
    
    Args:
        csv_files: List of CSV file paths
        colormap: Matplotlib colormap
        
    Returns:
        List of saved plot filenames
    """
    plotter = CSVContourPlotter()
    return plotter.plot_multiple_csv_files(csv_files, colormap=colormap)


# Example usage
def main():
    """Example usage of the CSV contour plotter."""
    
    # Example 1: Plot a single CSV file
    print("=== Example 1: Single CSV File ===")
    
    # Replace with your actual CSV file path
    csv_file = "spy_5min_data_volume.csv"
    
    try:
        plot_filename = plot_csv_contour(
            csv_file=csv_file,
            colormap='viridis',
            save_plot=True,
            show_plot=True
        )
        print(f"Plot saved as: {plot_filename}")
    except FileNotFoundError:
        print(f"CSV file not found: {csv_file}")
        print("Please update the csv_file path to point to your actual CSV file")
    
    # Example 2: Plot multiple CSV files
    # print("\n=== Example 2: Multiple CSV Files ===")
    
    # csv_files = [
    #     "AAPL_5min_open_2024-08-01_to_2024-08-31.csv",
    #     "AAPL_5min_high_2024-08-01_to_2024-08-31.csv", 
    #     "AAPL_5min_low_2024-08-01_to_2024-08-31.csv",
    #     "AAPL_5min_close_2024-08-01_to_2024-08-31.csv",
    #     "AAPL_5min_volume_2024-08-01_to_2024-08-31.csv"
    # ]
    
    # # Filter to only existing files
    # existing_files = [f for f in csv_files if os.path.exists(f)]
    
    # if existing_files:
    #     plot_files = plot_multiple_csvs(existing_files, colormap='plasma')
    #     print(f"Created {len(plot_files)} contour plots")
    # else:
    #     print("No CSV files found. Please update paths to your actual CSV files")
    
    # # Example 3: Advanced usage with custom options
    # print("\n=== Example 3: Advanced Usage ===")
    
    # plotter = CSVContourPlotter()
    
    # # Plot with custom settings
    # if os.path.exists(csv_file):
    #     plot_filename = plotter.plot_contour_from_csv(
    #         csv_file=csv_file,
    #         variable_name="Close Price",
    #         colormap='RdYlBu_r',  # Reversed Red-Yellow-Blue
    #         save_plot=True,
    #         show_plot=False,  # Don't display, just save
    #         output_dir="./plots"  # Custom output directory
    #     )

if __name__ == "__main__":
    main()

"""
# USAGE EXAMPLES:

# Simple usage - plot one CSV file
plot_csv_contour("my_data.csv", colormap='viridis')

# Plot multiple files
csv_files = ["open_data.csv", "close_data.csv", "volume_data.csv"] 
plot_multiple_csvs(csv_files, colormap='plasma')

# Advanced usage
plotter = CSVContourPlotter()
plotter.plot_contour_from_csv(
    csv_file="my_data.csv",
    variable_name="Custom Variable", 
    colormap='coolwarm',
    save_plot=True,
    show_plot=False,
    output_dir="./my_plots"
)

# Expected CSV format:
# date,09:30,09:35,09:40,09:45,10:00,...,15:55
# 2024-08-01,150.25,150.30,150.45,150.60,...,151.20  
# 2024-08-02,151.00,151.15,151.25,151.40,...,152.10
# 2024-08-03,152.00,152.20,152.15,152.30,...,153.00

# Available colormaps:
# 'viridis', 'plasma', 'inferno', 'magma', 'coolwarm', 'RdYlBu', 'seismic', 'Spectral', etc.
"""