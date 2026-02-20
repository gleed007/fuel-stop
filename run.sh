#!/bin/bash

echo "Starting Fuel Route Optimizer API..."

# Install dependencies if not already installed
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

echo "Installing dependencies..."
pip install -q -r requirements.txt

echo "Starting Django server on port 8000..."
python manage.py runserver 0.0.0.0:8000
