import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import time
from typing import Dict, List, Optional
import os

# ============================================================================
# GLOBAL CONFIGURATION - MODIFY THESE SETTINGS
# ============================================================================

# API Configuration
API_KEY = "Z_ENWpm0RRrvXvLOY65uMH8RB93B4gBN"

# Single Ticker Configuration
TICKER = "SPY"
START_DATE = "2024-09-01"    # YYYY-MM-DD format
END_DATE = "2025-08-30"      # YYYY-MM-DD format
INTERVAL_MINUTES = 5         # 1, 5, 15, 30, 60 minutes
OUTPUT_FILENAME_BASE = "spy_5min_data"  # Base name for output files

# Plotting Configuration
COLORMAP = 'viridis'         # viridis, plasma, coolwarm, RdYlBu_r, etc.
SHOW_PLOTS = True            # Display plots
SAVE_PLOTS = True            # Save plots as PNG
PLOT_OUTPUT_DIR = "./plots"  # Directory for saved plots

# API Settings
RATE_LIMIT_DELAY = 0.1       # Seconds between API calls
MAX_BARS_PER_REQUEST = 50000 # Polygon.io limit
ADJUSTED_PRICES = True       # Adjust for splits/dividends

# ============================================================================
# DATA FETCHING CLASS
# ============================================================================

class IntradayDataFetcher:
    def __init__(self):
        self.base_url = "https://api.polygon.io"
        
        # Validate configuration
        if not API_KEY:
            raise ValueError("API_KEY must be set in global configuration")
        if not TICKER:
            raise ValueError("TICKER must be set in global configuration")
        if not START_DATE or not END_DATE:
            raise ValueError("START_DATE and END_DATE must be set")
    
    def fetch_data(self) -> pd.DataFrame:
        """Fetch intraday data and return processed DataFrame."""
        print(f"Fetching {INTERVAL_MINUTES}-minute data for {TICKER}")
        print(f"Date range: {START_DATE} to {END_DATE}")
        
        # Construct API URL
        url = f"{self.base_url}/v2/aggs/ticker/{TICKER}/range/{INTERVAL_MINUTES}/minute/{START_DATE}/{END_DATE}"
        
        params = {
            'adjusted': str(ADJUSTED_PRICES).lower(),
            'sort': 'asc',
            'limit': MAX_BARS_PER_REQUEST,
            'apikey': API_KEY
        }
        
        all_results = []
        next_url = None
        request_count = 0
        
        try:
            while True:
                request_count += 1
                print(f"Making API request #{request_count}...")
                
                request_url = next_url if next_url else url
                response = requests.get(request_url if next_url else url, 
                                      params=None if next_url else params)
                response.raise_for_status()
                data = response.json()
                
                if 'results' not in data or not data['results']:
                    print("No more data available")
                    break
                
                results = data['results']
                all_results.extend(results)
                print(f"Retrieved {len(results)} bars (Total: {len(all_results)})")
                
                if 'next_url' in data and data['next_url']:
                    next_url = data['next_url'] + f"&apikey={API_KEY}"
                    time.sleep(RATE_LIMIT_DELAY)
                else:
                    break
            
            if not all_results:
                print("No data found")
                return pd.DataFrame()
            
            # Process the raw data
            df = self._process_data(all_results)
            
            print(f"Data collection complete!")
            print(f"Total bars: {len(df)}")
            print(f"Date range: {df['datetime'].min()} to {df['datetime'].max()}")
            
            return df
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data: {e}")
            return pd.DataFrame()
    
    def _process_data(self, raw_results: List[Dict]) -> pd.DataFrame:
        """Process raw API data into clean DataFrame."""
        df = pd.DataFrame(raw_results)
        
        # Rename columns
        df = df.rename(columns={
            'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close',
            'v': 'volume', 'vw': 'vwap', 't': 'timestamp'
        })
        
        # Convert timestamp to UTC datetime
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        
        # Add useful time columns
        df['date'] = df['datetime'].dt.date
        df['time'] = df['datetime'].dt.time
        df['hour'] = df['datetime'].dt.hour
        df['minute'] = df['datetime'].dt.minute
        
        # Sort by datetime
        df = df.sort_values('datetime').reset_index(drop=True)
        
        return df
    
    def save_pivoted_data(self, df: pd.DataFrame) -> List[str]:
        """Save data as pivoted CSV files (dates x time intervals)."""
        if df.empty:
            print("No data to save")
            return []
        
        variables = ['open', 'high', 'low', 'close', 'volume', 'vwap']
        available_variables = [var for var in variables if var in df.columns]
        saved_files = []
        
        print("Creating pivoted CSV files...")
        
        for variable in available_variables:
            print(f"Processing {variable}...")
            
            # Create pivot table
            pivot_df = self._create_pivot_table(df, variable)
            
            if not pivot_df.empty:
                filename = f"{OUTPUT_FILENAME_BASE}_{variable}.csv"
                pivot_df.to_csv(filename)
                saved_files.append(filename)
                print(f"  Saved: {filename} ({pivot_df.shape[0]} days x {pivot_df.shape[1]} intervals)")
        
        return saved_files
    
    def _create_pivot_table(self, df: pd.DataFrame, variable: str) -> pd.DataFrame:
        """Create pivot table with dates as rows, time intervals as columns."""
        df_copy = df.copy()
        
        # Create time string in HH:MM format (24-hour UTC)
        df_copy['time_str'] = df_copy['datetime'].dt.strftime('%H:%M')
        
        # Create pivot table
        pivot_df = df_copy.pivot_table(
            index='date',
            columns='time_str',
            values=variable,
            aggfunc='first'
        )
        
        # Sort columns chronologically
        pivot_df = pivot_df.reindex(sorted(pivot_df.columns), axis=1)
        
        # Fill NaN values
        if variable == 'volume':
            pivot_df = pivot_df.fillna(0)
        else:
            pivot_df = pivot_df.ffill(axis=1)
        
        return pivot_df

# ============================================================================
# ENHANCED PLOTTING CLASS
# ============================================================================

class EnhancedContourPlotter:
    def __init__(self):
        if SAVE_PLOTS and PLOT_OUTPUT_DIR:
            os.makedirs(PLOT_OUTPUT_DIR, exist_ok=True)
    
    def plot_csv_contour(self, csv_file: str) -> str:
        """Create enhanced contour plot from CSV file."""
        if not os.path.exists(csv_file):
            raise FileNotFoundError(f"CSV file not found: {csv_file}")
        
        print(f"Creating contour plot for: {csv_file}")
        
        # Load data
        df = pd.read_csv(csv_file, index_col=0)
        if df.empty:
            print("CSV file is empty")
            return ""
        
        # Extract variable name from filename
        variable_name = self._extract_variable_name(csv_file)
        
        # Prepare data for plotting
        X, Y, Z, time_labels, date_labels, month_positions = self._prepare_plot_data(df)
        
        # Create the plot
        fig, ax = plt.subplots(figsize=(16, 10))
        
        # Create contour plot
        contour = ax.contourf(X, Y, Z, levels=50, cmap=COLORMAP, alpha=0.9)
        contour_lines = ax.contour(X, Y, Z, levels=15, colors='white', alpha=0.3, linewidths=0.5)
        
        # Add colorbar
        cbar = plt.colorbar(contour, ax=ax, shrink=0.8, aspect=30)
        cbar.set_label(f'{variable_name.title()}', rotation=270, labelpad=20, fontsize=12, fontweight='bold')
        
        # Format axes with enhanced styling
        self._format_enhanced_axes(ax, df, variable_name, time_labels, date_labels, month_positions)
        
        plt.tight_layout()
        
        # Save plot
        filename = ""
        if SAVE_PLOTS:
            filename = self._generate_plot_filename(csv_file)
            plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white', edgecolor='none')
            print(f"Plot saved: {filename}")
        
        if SHOW_PLOTS:
            plt.show()
        else:
            plt.close()
        
        return filename
    
    def _prepare_plot_data(self, df: pd.DataFrame):
        """Prepare data matrices and labels for enhanced plotting."""
        # Time processing
        time_strings = df.columns.tolist()
        time_minutes = []
        
        for time_str in time_strings:
            try:
                hour, minute = map(int, time_str.split(':'))
                time_minutes.append(hour * 60 + minute)
            except:
                time_minutes.append(len(time_minutes) * INTERVAL_MINUTES + 9*60 + 30)
        
        # Date processing - convert to datetime for better handling
        dates = df.index.tolist()
        parsed_dates = []
        
        for date in dates:
            try:
                if isinstance(date, str):
                    parsed_date = pd.to_datetime(date).date()
                else:
                    parsed_date = date
                parsed_dates.append(parsed_date)
            except:
                parsed_dates.append(pd.to_datetime(f'2024-01-{len(parsed_dates)+1:02d}').date())
        
        # Create date numbers (days from first date)
        first_date = min(parsed_dates)
        date_numbers = [(d - first_date).days for d in parsed_dates]
        
        # Find month boundaries for y-axis labels
        month_positions = []
        month_labels = []
        current_month = None
        
        for i, date in enumerate(parsed_dates):
            if current_month != date.month:
                month_positions.append(date_numbers[i])
                month_labels.append(date.strftime('%b %Y'))
                current_month = date.month
        
        # Create coordinate matrices
        X, Y = np.meshgrid(time_minutes, date_numbers)
        Z = df.values.astype(float)
        
        # Handle NaN values
        if np.any(np.isnan(Z)):
            Z = pd.DataFrame(Z).ffill(axis=1).bfill(axis=1).values
            if np.any(np.isnan(Z)):
                Z = np.nan_to_num(Z, nan=np.nanmean(Z))
        
        # Create time labels for x-axis
        time_labels = []
        for i, time_str in enumerate(time_strings):
            try:
                hour = int(time_str.split(':')[0])
                time_labels.append((time_minutes[i], hour, time_str))
            except:
                time_labels.append((time_minutes[i], 9 + i//12, time_str))
        
        return X, Y, Z, time_labels, (month_positions, month_labels), (month_positions, month_labels)
    
    def _format_enhanced_axes(self, ax, df, variable_name, time_labels, date_labels, month_positions):
        """Format axes with enhanced styling."""
        # Title
        title = f"{TICKER} {variable_name.title()} - {INTERVAL_MINUTES}min Intervals"
        ax.set_title(title, fontsize=18, fontweight='bold', pad=25)
        
        # X-axis (Time) - Hours as major ticks, minutes as subticks
        unique_hours = {}
        for time_min, hour, time_str in time_labels:
            if hour not in unique_hours:
                unique_hours[hour] = time_min
        
        # Set major ticks at each hour
        major_ticks = []
        major_labels = []
        for hour in sorted(unique_hours.keys()):
            if 9 <= hour <= 16:  # Trading hours
                major_ticks.append(unique_hours[hour])
                major_labels.append(f"{hour:02d}")
        
        ax.set_xticks(major_ticks)
        ax.set_xticklabels(major_labels, fontsize=11)
        ax.set_xlabel('Trading Hours (UTC)', fontsize=14, fontweight='bold', labelpad=10)
        
        # Add minor ticks for minutes (subticks)
        minor_ticks = [time_min for time_min, _, _ in time_labels]
        ax.set_xticks(minor_ticks, minor=True)
        ax.tick_params(which='minor', axis='x', length=3)
        ax.tick_params(which='major', axis='x', length=6, width=2)
        
        # Y-axis (Dates) - Month labels
        month_positions, month_labels = month_positions
        ax.set_yticks(month_positions)
        ax.set_yticklabels(month_labels, fontsize=11)
        ax.set_ylabel('Trading Months', fontsize=14, fontweight='bold', labelpad=10)
        
        # Invert y-axis so earliest dates are at bottom
        ax.invert_yaxis()
        
        # Enhanced grid
        ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5, which='major')
        ax.grid(True, alpha=0.1, linestyle='--', linewidth=0.3, which='minor')
        
        # Style improvements
        ax.set_facecolor('#fafafa')
        
        # Add statistics box
        self._add_enhanced_stats_box(ax, df)
        
        # Add time zone indicator
        ax.text(0.99, 0.01, 'Times in UTC', transform=ax.transAxes,
               ha='right', va='bottom', fontsize=9, style='italic',
               bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))
    
    def _add_enhanced_stats_box(self, ax, df):
        """Add enhanced statistics box."""
        values = df.values.flatten()
        values = values[~np.isnan(values)]
        
        if len(values) > 0:
            stats_text = (f'Data Points: {len(values):,}\n'
                         f'Range: {values.min():.2f} - {values.max():.2f}\n'
                         f'Mean: {values.mean():.2f}\n'
                         f'Std Dev: {values.std():.2f}')
            
            ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
                   verticalalignment='top', fontsize=10,
                   bbox=dict(boxstyle='round,pad=0.5', facecolor='white', 
                            alpha=0.9, edgecolor='gray', linewidth=1))
    
    def _extract_variable_name(self, filename: str) -> str:
        """Extract variable name from filename."""
        base = os.path.basename(filename).replace('.csv', '')
        variables = ['open', 'high', 'low', 'close', 'volume', 'vwap']
        
        for var in variables:
            if var in base.lower():
                return var
        
        return "Data"
    
    def _generate_plot_filename(self, csv_file: str) -> str:
        """Generate filename for saved plot."""
        base_name = os.path.splitext(os.path.basename(csv_file))[0]
        plot_filename = f"{base_name}_contour.png"
        
        if PLOT_OUTPUT_DIR:
            return os.path.join(PLOT_OUTPUT_DIR, plot_filename)
        return plot_filename
    
    def plot_all_variables(self, csv_files: List[str]) -> List[str]:
        """Plot all variable files."""
        saved_plots = []
        
        print(f"Creating {len(csv_files)} contour plots...")
        
        for csv_file in csv_files:
            try:
                plot_file = self.plot_csv_contour(csv_file)
                if plot_file:
                    saved_plots.append(plot_file)
            except Exception as e:
                print(f"Error plotting {csv_file}: {e}")
        
        return saved_plots

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function."""
    print("="*60)
    print(f"INTRADAY DATA FETCHER AND PLOTTER")
    print("="*60)
    print(f"Ticker: {TICKER}")
    print(f"Date Range: {START_DATE} to {END_DATE}")
    print(f"Interval: {INTERVAL_MINUTES} minutes")
    print(f"Output Base: {OUTPUT_FILENAME_BASE}")
    print("="*60)
    
    # Step 1: Fetch data
    print("\n[1/3] FETCHING DATA...")
    fetcher = IntradayDataFetcher()
    df = fetcher.fetch_data()
    
    if df.empty:
        print("No data retrieved. Exiting.")
        return
    
    # Step 2: Save pivoted CSV files
    print("\n[2/3] SAVING CSV FILES...")
    csv_files = fetcher.save_pivoted_data(df)
    
    if not csv_files:
        print("No CSV files created. Exiting.")
        return
    
    # Step 3: Create plots
    print("\n[3/3] CREATING PLOTS...")
    plotter = EnhancedContourPlotter()
    plot_files = plotter.plot_all_variables(csv_files)
    
    # Summary
    print("\n" + "="*60)
    print("EXECUTION COMPLETE")
    print("="*60)
    print(f"CSV Files Created: {len(csv_files)}")
    for f in csv_files:
        print(f"  • {f}")
    
    print(f"\nPlot Files Created: {len(plot_files)}")
    for f in plot_files:
        print(f"  • {f}")
    
    print(f"\nData Summary:")
    print(f"  • Total bars: {len(df):,}")
    print(f"  • Date range: {df['datetime'].dt.date.min()} to {df['datetime'].dt.date.max()}")
    print(f"  • Trading days: {df['date'].nunique()}")
    print("="*60)

if __name__ == "__main__":
    main()