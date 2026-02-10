# Three-Minute Pattern Analysis System

A comprehensive stock market analysis tool that identifies and validates three-minute candle patterns with mathematical verification and advanced visualizations.

## Overview

This system analyzes minute-level stock data to identify patterns in three-minute chunks, providing:

- Pattern classification and frequency analysis
- Mathematical validation of price and time continuity
- Contiguous basket analysis with comprehensive statistics
- Advanced diagnostic visualizations
- PDF report generation

## Installation

### Prerequisites

```bash
pip install pandas numpy matplotlib seaborn reportlab pypdf2 pillow
pip install requests  # For data fetching
```

### Project Structure

```
project/
├── fetcher.py              # Data fetching from Polygon.io
├── analyzer.py             # Main pattern analysis
├── validate_patterns.py    # Mathematical validation
├── visualize_patterns.py   # Enhanced visualization
├── generate_pdf_report.py  # PDF report generation
├── config.json            # API configuration
└── README.md              # This file
```

## Quick Start

### 1. Configure API Access

Edit `config.json` with your Polygon.io API key:

```json
{
  "api": {
    "key": "YOUR_POLYGON_API_KEY_HERE",
    ...
  }
}
```

### 2. Fetch Market Data

```bash
python fetcher.py
```

This will download minute-level data for symbols specified in config.json.

### 3. Run Pattern Analysis

```bash
python analyzer.py --data market_data/raw/SPY_2023-01-01_to_2024-01-01_raw.csv
```

### 4. Validate Results

```bash
python validate_patterns.py analysis_results/SPY_20241201_143022 SPY
```

### 5. Generate Visualizations

```bash
python visualize_patterns.py analysis_results/SPY_20241201_143022
```

### 6. Create PDF Report

```bash
python generate_pdf_report.py analysis_results/SPY_20241201_143022
```

## Key Features

### Pattern Classification

- **P (Positive)**: Next open > Current open
- **N (Negative)**: Next open < Current open
- **O (Zero)**: Next open = Current open (within threshold)

### Three Offset Analysis

The system analyzes patterns with three different starting offsets (0, 1, 2) to capture all possible three-minute patterns in the data.

### Mathematical Validation

- Verifies that sum of pattern changes equals total price change
- Validates time continuity across baskets
- Identifies and reports any discrepancies

### Contiguous Basket Analysis

Groups consecutive three-minute patterns into "baskets" with:

- Start/end times and prices
- Pattern type classification
- Volume and trade statistics
- Mathematical consistency checks

## Visualization Components

### 1. Pattern Performance Analysis

- Top patterns by average change
- Frequency distribution
- Win rate vs return scatter plots
- Risk-return profiles

### 2. Basket Analysis Charts

- Cumulative price changes over time
- Pattern type performance bubbles
- Mathematical validation indicators

### 3. Time Series Analysis

- Cumulative returns over time
- Basket boundary markers
- Drawdown analysis

### 4. Validation Dashboard

- Discrepancy comparisons
- Validation status summary
- Accounted vs actual change correlation

### 5. Diagnostic Summation Charts

- Time summation validation
- Price change summation tracking
- Remainder handling visualization
- Gap detection and reporting

## Output Files

### Analysis Results Directory Structure

```
analysis_results/SYMBOL_TIMESTAMP/
├── cleaned_SYMBOL.csv              # Cleaned data
├── cleanup_summary.json            # Data cleaning report
├── analysis_summary.json           # Overall analysis summary
├── pattern_summary_offset_*.csv    # Pattern statistics per offset
├── pattern_occurrences_offset_*.csv # Detailed occurrences
├── basket_summary_offset_*.csv     # Basket details
├── basket_statistics_offset_*.json # Basket statistics
├── validation_report.txt           # Validation results
├── visualizations/                 # All generated charts
│   ├── pattern_performance_analysis.png
│   ├── basket_analysis_charts.png
│   ├── pattern_heatmaps.png
│   ├── time_series_analysis.png
│   ├── validation_dashboard.png
│   ├── diagnostic_summation_charts.png
│   └── visualization_summary.txt
└── analysis_report.pdf            # Complete PDF report

```

## Understanding the Results

### Pattern Summary CSV

- **pattern**: Three-character pattern (e.g., "PPN")
- **count**: Number of occurrences
- **avg_change**: Average price change
- **win_rate**: Percentage of positive outcomes
- **return_risk_ratio**: Sharpe-like ratio

### Basket Statistics JSON

- **total_baskets**: Number of complete 3-minute baskets
- **change_discrepancy**: Difference between accounted and actual price change
- **mathematical_consistency**: Validation results
- **pattern_type_breakdown**: Performance by pattern type

### Validation Report

Shows whether the sum of all pattern changes equals the total price movement, validating the mathematical model.

## Troubleshooting

### Common Issues

1. **Insufficient Data**

   - Ensure at least 4 minutes of data after cleaning
   - Check cleanup_summary.json for data removal statistics

2. **Validation Failures**

   - Small discrepancies (<0.0001) are normal due to floating-point precision
   - Large discrepancies may indicate data gaps or processing errors

3. **Missing Visualizations**
   - Ensure all dependencies are installed
   - Check console output for specific error messages

## Advanced Configuration

### Adjusting Analysis Parameters

In `analyzer.py`:

- `chunk_size = 3`: Number of minutes per pattern (default: 3)
- `threshold = 0.0001`: Price change threshold for classification

In `config.json`:

- `chunk_days`: Days of data to fetch per API call
- `data_quality`: Validation and cleaning options

## Performance Considerations

- Large datasets (>1 million bars) may require significant memory
- PDF generation with many charts can take several seconds
- Consider processing data in chunks for very long time periods

## Support

For issues or questions:

1. Check the validation_report.txt for mathematical consistency
2. Review visualization_summary.txt for chart descriptions
3. Examine analysis_summary.json for overall statistics

## License

This project is for educational and research purposes.
