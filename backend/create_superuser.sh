#!/bin/bash
# Script to create Django superuser

cd "$(dirname "$0")"

# Activate virtual environment
if [ -d ".venv" ]; then
    echo "🔹 Activating virtual environment..."
    source .venv/bin/activate
elif [ -d "venv" ]; then
    echo "🔹 Activating virtual environment..."
    source venv/bin/activate
else
    echo "⚠️  No virtual environment found. Please activate your virtual environment first."
    exit 1
fi

# Create superuser
echo "👤 Creating Django superuser..."
python3 manage.py createsuperuser

echo ""
echo "✅ Done! You can now login to /admin/ with the credentials you just created."
