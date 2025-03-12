#!/bin/bash

# Directory to store the text files
output_dir="./lorem_ipsum_files"

# Create the output directory if it doesn't exist
mkdir -p "$output_dir"

# Generate 200 text files with 200 words of Lorem Ipsum each
for i in {1..200}
do
    # Define the file name
    file_name="$output_dir/lorem_$i.txt"
    
    # Generate the Lorem Ipsum text and save it to the file
    # 'lorem' command can generate lorem ipsum text, use 'shuf' for shuffling words if needed
    lorem_text=$(curl -s https://baconipsum.com/api/?type=all-meat&paras=1 | jq -r '.[0]')
    
    # Take the first 200 words
    words=$(echo "$lorem_text" | tr ' ' '\n' | head -n 200 | tr '\n' ' ')

    # Write the words to the file
    echo "$words" > "$file_name"
    
    echo "Generated file: $file_name"
done

echo "200 Lorem Ipsum files generated successfully!"

