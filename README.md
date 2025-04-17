#This is a store for useful CLI utilities

═════════════════════════════════════

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

═════════════════════════════════════

# CVE Checker

A tool for scanning files for CVE references and retrieving vulnerability data from Oracle Linux and Red Hat.

## Installation
```
pip install requests beautifulsoup4
```

## Usage
```
python cve_checker_new.py --input <file_or_directory> --output <output_file.csv>
```

### Examples
```
# Single file
python cve_checker_new.py --input security_report.txt --output results.csv

# Directory
python cve_checker_new.py --input /path/to/logs/ --output results.csv
```

## Features
### Core Capabilities
- Scans text, JSON, and CSV files for CVE references
- Queries Oracle Linux and Red Hat security databases
- Identifies Windows-only vulnerabilities
- Extracts package names and version information
- Exports results to CSV

### Output Format
CSV file with columns:
- **CVE**: Vulnerability identifier
- **Oracle_URL**: Oracle Linux information link
- **RedHat_URL**: Red Hat information link
- **Windows_Only**: Windows-specific flag
- **Version**: Affected package version
- **Package**: Affected package name

## Technical Notes
- Includes rate limiting to prevent server overload
- Internet connection required
- Processing time varies with file/directory size
  
═════════════════════════════════════

check_ip: Log your public IP to a csv file

lorem-ipsum-file-generator: bulk generate lorem ipsum text into files. Parallel sometimes goes to fast for the API lorem upsum generator and you'll get 500 errors in those text files...

postgres-visualizer: Quick check a postgres db with cstore and creat html visualizations to help find problems
