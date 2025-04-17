#!/bin/bash

# Check if the output file name is provided as an argument
if [ $# -ne 1 ]; then
    echo "Usage: $0 <output_file.csv>"
    exit 1
fi

# Define the output file name
OUTPUT_FILE=$1

# Use curl to fetch the public IP address and write it to a CSV file with timestamp
public_ip=$(curl -s ifconfig.me)
timestamp=$(date +"%Y-%m-%d %H:%M:%S")

# Append the IP address along with the timestamp to the CSV file
echo "$timestamp, $public_ip" >> $OUTPUT_FILE

# Check if the script ran successfully
if [ $? -eq 0 ]; then
    echo "Public IP address and timestamp have been written to $OUTPUT_FILE"
else
    echo "Failed to retrieve public IP address"
fi

