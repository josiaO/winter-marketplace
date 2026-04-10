import os
import re

files_to_patch = [
    "accounts/views.py",
    "analytics/views.py",
    "insights/views.py",
    "marketplace/views.py",
    "sellers/views.py"
]

for f in files_to_patch:
    if not os.path.exists(f): continue
    with open(f, 'r') as fp:
        lines = fp.readlines()
    
    # Remove the first instance of "from rest_framework import serializers\n"
    new_lines = []
    removed = False
    for line in lines:
        if not removed and line == "from rest_framework import serializers\n":
            removed = True
            continue
        new_lines.append(line)
        
    with open(f, 'w') as fp:
        fp.write("".join(new_lines))

