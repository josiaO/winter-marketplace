FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Create a non-root user
RUN addgroup --system app && adduser --system --group app

WORKDIR /app

# Install system dependencies for packages like lxml
RUN apt-get update && apt-get install -y \
    build-essential \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt ./requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy project files
COPY . .

# Create entrypoint
COPY build.sh /build.sh
RUN chmod +x /build.sh

# Chown the application directory
RUN chown -R app:app /app

# Switch to the non-root user
USER app

EXPOSE 8000

CMD ["/build.sh"]
