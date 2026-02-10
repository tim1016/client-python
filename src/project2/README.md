# Three-Minute Stock Pattern Analysis Toolkit

A comprehensive Python toolkit for fetching, analyzing, and visualizing 3-minute stock price patterns using Polygon.io API data with mathematical validation and contiguous basket tracking.

## Overview

This advanced pattern analysis system consists of four main components:

1. **Data Fetcher** (`fetcher.py`) - Downloads minute-level stock data from Polygon.io
2. **Pattern Analyzer** (`analyzer.py`) - Analyzes 3-minute price patterns with contiguous basket tracking
3. **Pattern Validator** (`validate_patterns.py`) - Validates mathematical accuracy of pattern analysis
4. **Visualization Tool** (`visualize_patterns.py`) - Creates comprehensive charts and dashboards

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Detailed Setup](#detailed-setup)
- [Usage Workflow](#usage-workflow)
- [Understanding the Analysis](#understanding-the-analysis)
- [Output Files Reference](#output-files-reference)
- [Visualization Gallery](#visualization-gallery)
- [Configuration Guide](#configuration-guide)
- [Troubleshooting](#troubleshooting)
- [Mathematical Validation](#mathematical-validation)
- [Advanced Features](#advanced-features)
- [Best Practices](#best-practices)
- [Limitations](#limitations)

## Prerequisites

### Required Python Packages

```bash
pip install pandas numpy matplotlib seaborn requests
```

### API Access

- **Polygon.io API key** (free tier available)
- Sign up at [https://polygon.io/](https://polygon.io/)
- Free tier provides delayed data with rate limits
- Paid tiers offer real-time data and higher limits

## Installation

1. **Clone or download the toolkit files:**

   ```
   fetcher.py
   analyzer.py
   validate_patterns.py
   visualize_patterns.py
   ```

2. **Install dependencies:**

   ```bash
   pip install pandas numpy matplotlib seaborn requests
   ```

3. **Set up API credentials** (see [Configuration Guide](#configuration-guide))

## Quick Start

### 1. Initial Setup

```bash
# Create default configuration
python fetcher.py
# Edit config.json with your API key
```

### 2. Fetch Data

```bash
python fetcher.py
```

### 3. Analyze Patterns

```bash
python analyzer.py --data market_data/raw/SPY_2024-01-01_to_2024-12-31_raw.csv
```

### 4. Validate Results

```bash
python validate_patterns.py analysis_results/SPY_20241201_143022 SPY
```

### 5. Create Visualizations

```bash
python visualize_patterns.py analysis_results/SPY_20241201_143022
```

## Detailed Setup

### Step 1: Configuration Setup

Run the fetcher once to create the default configuration:

```bash
python fetcher.py
```

This creates `config.json`. Edit it with your settings:

```json
{
  "api": {
    "key": "YOUR_POLYGON_API_KEY_HERE",
    "base_url": "https://api.polygon.io",
    "rate_limit_delay": 0.5,
    "retry_count": 3,
    "timeout": 30
  },
  "storage": {
    "output_dir": "market_data",
    "create_subdirs": true,
    "raw_data_dir": "raw",
    "metadata_dir": "metadata",
    "log_dir": "logs"
  },
  "fetch_settings":
```
