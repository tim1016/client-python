import requests
import json
from datetime import datetime, timedelta
from collections import defaultdict

class PolygonPatternAnalyzer:
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
            'limit': 50000,  # Add limit parameter
            'apikey': self.api_key
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Add more detailed error checking
            if response.status_code != 200:
                print(f"Error: API returned status code {response.status_code}")
                print(f"Response: {data}")
                return []
                
            if data.get('status') == 'OK' and 'results' in data:
                print(f"Successfully retrieved {len(data['results'])} bars")
                return data['results']
            elif data.get('status') == 'DELAYED':
                print("Note: You're using a free API key with delayed data access.")
                print("Try using historical dates from several days ago, or upgrade to a paid plan.")
                print("Attempting to retrieve available data...")
                return data.get('results', [])
            else:
                print(f"API Status: {data.get('status')}")
                if data.get('error'):
                    print(f"API Error: {data.get('error')}")
                if data.get('message'):
                    print(f"API Message: {data.get('message')}")
                print(f"Request URL: {url}")
                print(f"Parameters: {params}")
                
                # Try to return any available results even if status isn't OK
                if 'results' in data and data['results']:
                    print(f"Found {len(data['results'])} bars despite API status")
                    return data['results']
                return []
                    
        except requests.exceptions.RequestException as e:
            print(f"Network Error: {str(e)}")
            return []
    
    def classify_bar(self, bar):
        """
        Classify a minute bar as Positive (P) or Negative (N)
        Based on close vs open price
        """
        if bar['c'] >= bar['o']:  # close >= open
            return 'P'
        else:
            return 'N'
    
    def find_patterns(self, bars, pattern_length):
        """
        Find all patterns of specified length and calculate VWAP changes
        Returns a dictionary with patterns and their VWAP changes
        """
        patterns_found = defaultdict(list)
        
        # Need at least pattern_length bars to form a pattern
        if len(bars) < pattern_length:
            return patterns_found
        
        for i in range(len(bars) - pattern_length + 1):
            # Extract the pattern sequence
            pattern_bars = bars[i:i + pattern_length]
            pattern_string = ''.join([self.classify_bar(bar) for bar in pattern_bars])
            
            # Calculate VWAP change for this pattern
            first_vwap = pattern_bars[0]['vw']  # VWAP of first bar
            last_vwap = pattern_bars[-1]['vw']  # VWAP of last bar
            vwap_change = last_vwap - first_vwap
            
            # Store the VWAP change for this pattern occurrence
            patterns_found[pattern_string].append(vwap_change)
        
        return patterns_found
    
    def analyze_patterns(self, bars):
        """
        Analyze patterns for lengths 2-5 minutes and calculate VWAP statistics
        """
        # Initialize pattern_counts to store (total_vwap_change_sum, occurrence_count)
        pattern_counts = defaultdict(lambda: [0.0, 0])  # [sum, count]
        
        # Analyze patterns for lengths 2-5
        for length in range(2, 6):
            patterns_found = self.find_patterns(bars, length)
            
            for pattern, vwap_changes in patterns_found.items():
                # Add up all VWAP changes and count occurrences
                total_change = sum(vwap_changes)
                count = len(vwap_changes)
                
                # Update the totals
                pattern_counts[pattern][0] += total_change
                pattern_counts[pattern][1] += count
        
        return pattern_counts
    
    def print_results(self, pattern_counts):
        """
        Print the final results with average VWAP rate of change
        """
        print("\n" + "="*80)
        print("STOCK PATTERN ANALYSIS RESULTS")
        print("="*80)
        print(f"{'Pattern':<10} {'Occurrences':<12} {'Avg VWAP Rate of Change':<25} {'Total VWAP Change':<20}")
        print("-" * 80)
        
        # Sort patterns by length first, then alphabetically
        sorted_patterns = sorted(pattern_counts.keys(), key=lambda x: (len(x), x))
        
        total_patterns = 0
        for pattern in sorted_patterns:
            total_vwap_change_sum, occurrence_count = pattern_counts[pattern]
            
            if occurrence_count > 0:
                # Calculate average rate of change per minute
                pattern_length = len(pattern)
                avg_rate_of_change = total_vwap_change_sum / (occurrence_count * pattern_length)
                
                print(f"{pattern:<10} {occurrence_count:<12} {avg_rate_of_change:<25.6f} {total_vwap_change_sum:<20.6f}")
                total_patterns += occurrence_count
        
        print("-" * 80)
        print(f"Total patterns analyzed: {total_patterns}")
        
        # Print summary by pattern length
        print("\nSUMMARY BY PATTERN LENGTH:")
        print("-" * 40)
        for length in range(2, 6):
            length_patterns = [p for p in sorted_patterns if len(p) == length]
            length_count = sum(pattern_counts[p][1] for p in length_patterns)
            unique_patterns = len(length_patterns)
            max_possible = 2 ** length
            
            print(f"{length}-minute patterns: {length_count} occurrences, "
                  f"{unique_patterns}/{max_possible} unique patterns found")
    
    def run_analysis(self, symbol, start_date, end_date):
        """
        Main method to run the complete analysis
        """
        print(f"Fetching data for {symbol} from {start_date} to {end_date}...")
        
        # Get the minute-level data
        bars = self.get_aggs(symbol, start_date, end_date)
        
        # If no data found, try with older dates (common issue with free API keys)
        if not bars:
            print("No data found with current date range. Trying older dates...")
            older_end = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            older_start = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
            print(f"Trying date range: {older_start} to {older_end}")
            bars = self.get_aggs(symbol, older_start, older_end)
        
        # If still no data, try even older dates
        if not bars:
            print("Still no data. Trying much older dates...")
            much_older_end = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            much_older_start = (datetime.now() - timedelta(days=37)).strftime("%Y-%m-%d")
            print(f"Trying date range: {much_older_start} to {much_older_end}")
            bars = self.get_aggs(symbol, much_older_start, much_older_end)
        
        if not bars:
            print("No data available for analysis after trying multiple date ranges.")
            print("This might be due to:")
            print("1. Free API tier limitations")
            print("2. Weekend/holiday dates with no trading data")
            print("3. Network issues")
            print("Try running the script on a weekday or with a paid API key.")
            return
        
        print(f"Retrieved {len(bars)} minute bars")
        
        # Verify that VWAP data is available
        if 'vw' not in bars[0]:
            print("Error: VWAP data not available in the response")
            print("Available fields:", list(bars[0].keys()))
            return
        
        # Analyze the patterns
        pattern_counts = self.analyze_patterns(bars)
        
        # Print results
        self.print_results(pattern_counts)

def main():
    # Configuration
    API_KEY = "Z_ENWpm0RRrvXvLOY65uMH8RB93B4gBN"  # Replace with your actual API key
    SYMBOL = "GLD"  # Stock symbol to analyze
    
    # Use historical dates to avoid future date issues and API limitations
    # Use dates from a few days ago to ensure data availability
    end_date = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    
    print(f"Using date range: {start_date} to {end_date}")
    
    # Create analyzer instance
    analyzer = PolygonPatternAnalyzer(API_KEY)
    
    # Run the analysis
    analyzer.run_analysis(SYMBOL, start_date, end_date)

if __name__ == "__main__":
    main()