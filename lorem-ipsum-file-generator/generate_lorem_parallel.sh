#!/bin/bash

# Directory to store the text files
output_dir="/tmp/lorem_ipsum_files"

# Create the output directory if it doesn't exist
mkdir -p "$output_dir"

# Function to generate a single file with 200 words of Lorem Ipsum text
generate_file() {
    local i=$1
    #local file_name= "$output_dir"
    local file_name="/tmp/lorem_ipsum_files/lorem_$i.txt"
    echo $file_name

    # Generate the Lorem Ipsum text and take the first 200 words
    lorem_text=$(curl -s https://baconipsum.com/api/?type=all-meat&paras=1 | jq -r '.[0]')
    if [[ "$lorem_text" == *"50"* ]]; then
        echo "Error with curl."
        sleep 2
        lorem_text=$(curl -s https://baconipsum.com/api/?type=all-meat&paras=1 | jq -r '.[0]')
        words=$(echo "$lorem_text" | tr ' ' '\n' | head -n 200 | tr '\n' ' ')
    else
        words=$(echo "$lorem_text" | tr ' ' '\n' | head -n 200 | tr '\n' ' ')
    fi
    

    # Write the words to the file
    echo "$words" > "$file_name"

    echo "Generated file: $file_name"
}

export -f generate_file

# Run the generation in parallel for 200 files
seq 1 200 | parallel -j 10 --delay .5s generate_file 

echo "200 Lorem Ipsum files generated successfully!"

