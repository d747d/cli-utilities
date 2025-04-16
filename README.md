This is a store for useful CLI utilities


dnshistory: Checks historical IP's of requested Domain Name on CLI

═════════════════════════════════════

# CVE Checker Tool
This script scans files for CVE (Common Vulnerabilities and Exposures) references and automatically checks Oracle Linux and Red Hat security databases for detailed information about these vulnerabilities.
Features

Finds CVE references in various file formats (text, JSON, CSV)
Checks Oracle Linux and Red Hat security databases
Identifies Windows-only vulnerabilities
Extracts affected package names and version information
Exports results to CSV for easy analysis

Requirements

Python 3.6+
Required Python packages:

requests
beautifulsoup4



Installation

Clone or download this repository
Install required packages:

pip install requests beautifulsoup4
Usage
Basic usage:
python cve_checker_new.py --input <file_or_directory> --output <output_file.csv>
Examples:
# Check a single file
python cve_checker_new.py --input security_report.txt --output cve_results.csv

# Check all files in a directory
python cve_checker_new.py --input /path/to/logs/ --output cve_results.csv
Output
The script generates a CSV file with the following columns:

CVE: The identified CVE number
Oracle_URL: Link to Oracle Linux's information about the CVE (if available)
RedHat_URL: Link to Red Hat's information about the CVE (if Oracle info not available)
Windows_Only: Indicates if the vulnerability only affects Windows systems
Version: The affected package version
Package: The affected package name

Notes

The script includes rate limiting to avoid overloading vendor servers
For large files or directories, the script may take some time to complete
Internet connectivity is required to fetch CVE information

═════════════════════════════════════

check_ip: Log your public IP to a csv file

lorem-ipsum-file-generator: bulk generate lorem ipsum text into files. Parallel sometimes goes to fast for the API lorem upsum generator and you'll get 500 errors in those text files...

postgres-visualizer: Quick check a postgres db with cstore and creat html visualizations to help find problems
