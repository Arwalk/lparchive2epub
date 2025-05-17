#!/bin/bash

# Check if directory argument is provided
if [ $# -ne 1 ]; then
    echo "Usage: $0 <directory>"
    exit 1
fi

directory="$1"

# Check if directory exists
if [ ! -d "$directory" ]; then
    echo "Error: Directory '$directory' does not exist"
    exit 1
fi

# Initialize JSON array
echo "["

# Find all epub files and calculate their b3sum
first=true
find "$directory" -type f -name "*.epub" | while read -r file; do
    # Calculate b3sum and md5
    checksum=$(b3sum "$file" | cut -d' ' -f1)
    md5sum=$(md5 -q "$file")
    
    # Get filename without path and extension
    filename=$(basename "$file" .epub)
    
    # Add comma if not first item
    if [ "$first" = true ]; then
        first=false
    else
        echo ","
    fi
    
    # Output JSON object
    echo -n "  {\"lp\": \"$filename\", \"b3sum\": \"$checksum\", \"md5\": \"$md5sum\"}"
done

# Close JSON array
echo -e "\n]" 