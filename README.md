# Fuel Route Optimizer API

A Django-based API that calculates optimal fuel stops along a route based on fuel prices and vehicle range.

## Features

- Calculate routes between any two locations in the USA
- Find optimal fuel stops based on cost-effectiveness
- Account for 500-mile vehicle range and 10 MPG fuel efficiency
- Interactive map visualization of route and fuel stops
- Real-time fuel price data from CSV database

## API Endpoints

### POST /api/route

Calculate optimal route and fuel stops.

**Request:**
```json
{
  "start": "New York, NY",
  "end": "Los Angeles, CA"
}
```

**Response:**
```json
{
  "route": {
    "start": "New York, NY",
    "end": "Los Angeles, CA",
    "distance_miles": 2789.5,
    "distance_km": 4489.2,
    "duration_hours": 41.2,
    "coordinates": [[lat, lon], ...],
    "encoded_polyline": "..."
  },
  "fuel_stops": [
    {
      "station_name": "PILOT TRAVEL CENTER",
      "address": "I-80, Exit 123, City, State",
      "city": "City",
      "state": "State",
      "price_per_gallon": 3.45,
      "gallons": 50.0,
      "cost": 172.50,
      "coordinates": [lat, lon],
      "distance_from_start_miles": 450.2
    }
  ],
  "total_fuel_gallons": 278.95,
  "total_fuel_cost": 963.45,
  "vehicle_specs": {
    "mpg": 10,
    "range_miles": 500
  }
}
```

### GET /api/health

Health check endpoint.

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file in the project root with your OpenRouteService API key:
```
ORS_API_KEY=your_api_key_here
```
You can get a free key (2,000 requests/day) at https://openrouteservice.org/dev/#/signup

3. Run the server:
```bash
python manage.py runserver
```

4. Open browser to `http://localhost:8000`

## Technical Details

### Route API
Uses OpenRouteService (free tier) for routing:
- 2000 requests per day limit
- Single API call per route calculation
- Efficient geocoding with caching

### Fuel Stop Algorithm
1. Geocodes start/end locations via Nominatim (OpenStreetMap)
2. Gets driving route coordinates from OpenRouteService
3. Filters 8,000+ fuel stations to those within a bounding box of the route
4. Narrows down to stations within 80km using geodesic distance
5. Estimates each station's mile marker along the route
6. Simulates driving with a 500-mile tank, picking the cheapest station in the upcoming range window

### Performance Optimizations
- Station coordinates assigned deterministically at load time (no live geocoding per station)
- Bounding-box pre-filter before expensive geodesic calculations
- Geocoding results cached with LRU cache
- Fuel price data loaded once at startup
- Minimal external API calls (1 ORS call + 2 Nominatim calls per route)

## Configuration

### Environment Variables
- `ORS_API_KEY` - OpenRouteService API key (required)
- `DJANGO_SECRET_KEY` - Django secret key (optional, has dev default)
- `DEBUG` - Debug mode (default: True)

### Vehicle Parameters (configurable in route_service.py)
- `VEHICLE_RANGE_MILES`: 500 miles
- `MPG`: 10 miles per gallon

## Data

Fuel prices are loaded from `api/fuel_prices.csv` containing:
- Station ID, name, and address
- City and state
- Retail fuel prices per gallon

## Frontend

Interactive web interface at `http://localhost:8000` featuring:
- Route input form
- Leaflet.js map visualization
- Real-time route calculation
- Fuel stop details and costs
- Responsive design
