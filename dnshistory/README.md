# DNS History Tracker

A simple Python script to check the historical IP addresses associated with a domain name.

## Description

This script retrieves the DNS history for a specified domain by querying dnsarchive.net. It displays a chronological list of all IP addresses that the domain has pointed to over time.

## Requirements

- Python 3.x
- Required packages:
  - requests
  - validators
  - re (included in Python standard library)
  - sys (included in Python standard library)

## Installation

```bash
pip install requests validators
```

## Usage

1. Run the script:
   ```bash
   python dnshistory.py
   ```

2. Enter a domain when prompted:
   ```
   Enter a domain name: example.com
   ```

3. The script will display results formatted by date with associated IP addresses.

## Sample Output

```
Latest     | 2023-04-15 | 93.184.216.34
2023-01-20 | 93.184.216.34
2022-10-05 | 93.184.216.34
2022-05-12 | 93.184.216.34
```

## How It Works

1. Validates the user-provided domain name
2. Queries dnsarchive.net for historical data
3. Extracts dates and IP addresses using regular expressions
4. Formats and displays the results chronologically

## Notes

- The script marks the most recent entry as "Latest"
- Duplicate IP addresses for the same date are filtered out
- Results are sorted in reverse chronological order (newest first)
