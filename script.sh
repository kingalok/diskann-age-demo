#!/bin/bash

pattern_file="keyword.txt"
pattern=$(awk '{print}' "$pattern_file" ORS='\\n' | sed 's/\\n$//')

find . -type f -iname '*DINE*' | while read -r file; do
  awk -v pat="$pattern" '
    BEGIN {
      block = "";
      inblock = 0;
      found_diff = 0;
      n = split(pat, p_lines, "\\n");
    }
    {
      # Detect block start line (adjust to your exact pattern start)
      if (match($0, /^listofallowedenvironment: *\{/)) {
        block = $0 "\n";
        inblock = 1;
        next;
      }
      if (inblock) {
        block = block $0 "\n";
        if ($0 ~ /^\}/) {
          inblock = 0;
          # Remove trailing newline
          sub(/\n$/, "", block);
          if (block != pat) {
            found_diff = 1;
            exit;
          }
          block = "";
        }
      }
    }
    END {
      if (found_diff) {
        print FILENAME;
        exit 0;
      }
      exit 1;
    }
  ' "$file" && echo "$file"
done
