#!/bin/bash

# Function to check if a file is ignored by git
is_ignored() {
    git check-ignore -q "$1"
    return $?
}

# Function to print file contents with a simple header
print_file_contents() {
    echo "=== $1 ==="
    cat "$1"
    echo ""
}

# Create or clear the context.txt file
> context.txt

# Print the tree structure
echo "Directory Structure:" >> context.txt
tree -I ".git|__pycache__|*.pyc|*.pyo|*.pyd|*.so|*.dll|*.class" -L 2 >> context.txt
echo "" >> context.txt

# Print the contents of each file
find . -type f | while read -r file; do
    # Skip common ignored patterns and use git check-ignore
    if [[ "$file" != ./.git/* ]] && \
       [[ "$file" != ./__pycache__/* ]] && \
       [[ "$file" != *.pyc ]] && \
       [[ "$file" != *.pyo ]] && \
       [[ "$file" != *.pyd ]] && \
       [[ "$file" != *.so ]] && \
       [[ "$file" != *.dll ]] && \
       [[ "$file" != *.class ]] && \
       ! is_ignored "$file"; then
        print_file_contents "$file" >> context.txt
    fi
done

echo "Context generated in context.txt"