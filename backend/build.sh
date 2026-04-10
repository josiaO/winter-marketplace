#!/usr/bin/env bash

# Exit immediately if a command fails
set -euo pipefail
cd "$(dirname "$0")"

echo "🚀 Starting Django build process..."

# ---------------------------
# 1. Activate virtualenv (if exists)
# ---------------------------
if [ -d "venv" ]; then
  echo "🔹 Activating virtual environment (venv)"
  source venv/bin/activate
elif [ -d ".venv" ]; then
  echo "🔹 Activating virtual environment (.venv)"
  source .venv/bin/activate
else
  echo "⚠️ No virtual environment found, continuing..."
fi

# ---------------------------
# 2. Install Python dependencies
# ---------------------------
echo "Upgrade pip and install backend requirements..."
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
# ---------------------------
# 3. Django checks
# ---------------------------
echo "🧪 Running Django system checks..."
python3 manage.py check

# ---------------------------
# 4. Database migrations
# ---------------------------
echo "🗄️ Running database migrations..."
python manage.py migrate --noinput

# ---------------------------
# 5. Collect static files
# ---------------------------
echo "🎨 Collecting static files..."
python manage.py collectstatic --noinput

# ---------------------------
# 6. Optional: Create superuser
# ---------------------------
if [ "${CREATE_SUPERUSER:-false}" = "true" ]; then
    echo "👤 Creating superuser..."
    python manage.py shell <<EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='$DJANGO_SUPERUSER_USERNAME').exists():
    User.objects.create_superuser('$DJANGO_SUPERUSER_USERNAME', '$DJANGO_SUPERUSER_EMAIL', '$DJANGO_SUPERUSER_PASSWORD')
    print('✅ Superuser created successfully.')
else:
    print('ℹ️ Superuser already exists.')
EOF
fi

echo "✅ Build completed successfully!"
