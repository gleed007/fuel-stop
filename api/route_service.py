import os
import requests
from geopy.distance import geodesic
from typing import List, Tuple, Dict
from .fuel_data_service import get_fuel_service

class RouteService:
    """Service to calculate routes and optimal fuel stops."""
    
    # Using OpenRouteService (free API - 2000 requests/day)
    ORS_BASE_URL = "https://api.openrouteservice.org/v2"
    
    # Vehicle parameters
    VEHICLE_RANGE_MILES = 500
    MPG = 10
    MILES_PER_GALLON = 10
    MILES_TO_KM = 1.60934
    
    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get("ORS_API_KEY", "")
        if not self.api_key:
            raise ValueError("ORS_API_KEY environment variable is not set. Get a free key at https://openrouteservice.org/dev/#/signup")
        self.fuel_service = get_fuel_service()
    
    def geocode_location(self, location: str) -> Tuple[float, float]:
        """Convert location string to coordinates."""
        coords = self.fuel_service.geocode_location(f"{location}, USA")
        if not coords:
            raise ValueError(f"Could not geocode location: {location}")
        return coords
    
    def get_route(self, start: str, end: str) -> Dict:
        """
        Get route from OpenRouteService.
        
        Returns:
            Dict with 'coordinates' (list of [lon, lat]), 'distance' (meters), 'duration' (seconds)
        """
        start_coords = self.geocode_location(start)
        end_coords = self.geocode_location(end)
        
        # OpenRouteService expects [lon, lat] format
        start_lonlat = [start_coords[1], start_coords[0]]
        end_lonlat = [end_coords[1], end_coords[0]]
        
        url = f"{self.ORS_BASE_URL}/directions/driving-car"
        
        headers = {
            'Authorization': self.api_key,
            'Content-Type': 'application/json'
        }
        
        body = {
            'coordinates': [start_lonlat, end_lonlat],
            'geometry_simplify': True,
        }
        response = requests.post(url, json=body, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        route = data['routes'][0]
        geometry = route['geometry']
        
        if isinstance(geometry, str):
            coordinates = self._decode_polyline(geometry)
        else:
            coordinates = geometry['coordinates']
        
        return {
            'coordinates': coordinates,
            'distance': route['summary']['distance'],
            'duration': route['summary']['duration'],
            'start_coords': start_coords,
            'end_coords': end_coords
        }
    
    def calculate_optimal_fuel_stops(self, start: str, end: str) -> Dict:
        """
        Calculate the route and optimal fuel stops.
        
        Returns:
            Dict with route info, fuel stops, and total cost
        """
        # Get the route (1 API call to OpenRouteService)
        route_data = self.get_route(start, end)
        
        # Convert route coordinates from [lon, lat] to (lat, lon) for geopy
        route_coords = [(lat_lon[1], lat_lon[0]) for lat_lon in route_data['coordinates']]
        
        # Calculate total distance in miles
        total_distance_miles = route_data['distance'] / 1000 / self.MILES_TO_KM
        
        # Find stations near the route
        nearby_stations = self.fuel_service.find_stations_along_route(route_coords, max_distance_km=80)
        
        if not nearby_stations:
            return {
                'error': 'No fuel stations found along the route',
                'route': None,
                'fuel_stops': [],
                'total_cost': 0
            }
        
        # Calculate optimal fuel stops
        fuel_stops = self._optimize_fuel_stops(
            route_coords,
            nearby_stations,
            total_distance_miles
        )
        
        # Calculate total fuel cost
        total_gallons = total_distance_miles / self.MPG
        total_cost = sum(stop['cost'] for stop in fuel_stops)
        
        return {
            'route': {
                'start': start,
                'end': end,
                'distance_miles': round(total_distance_miles, 2),
                'distance_km': round(route_data['distance'] / 1000, 2),
                'duration_hours': round(route_data['duration'] / 3600, 2),
                'coordinates': route_coords,
                'encoded_polyline': self._encode_polyline(route_coords)
            },
            'fuel_stops': fuel_stops,
            'total_fuel_gallons': round(total_gallons, 2),
            'total_fuel_cost': round(total_cost, 2),
            'vehicle_specs': {
                'mpg': self.MPG,
                'range_miles': self.VEHICLE_RANGE_MILES
            }
        }
    
    def _optimize_fuel_stops(
        self,
        route_coords: List[Tuple[float, float]],
        nearby_stations: List[Dict],
        total_distance_miles: float
    ) -> List[Dict]:
        """
        Determine optimal fuel stops based on vehicle range and fuel prices.
        Uses route_index to estimate each station's mile marker instead of
        computing geodesic distances for every segment.
        """
        if not nearby_stations:
            return []

        max_index = max(s['route_index'] for s in nearby_stations) or 1
        for s in nearby_stations:
            s['approx_mile'] = (s['route_index'] / max(len(route_coords) - 1, 1)) * total_distance_miles

        fuel_stops = []
        current_mile = 0.0
        remaining_range = self.VEHICLE_RANGE_MILES
        used_ids = set()

        while current_mile + remaining_range < total_distance_miles:
            need_stop_before = current_mile + remaining_range
            search_start = current_mile + remaining_range * 0.4

            candidates = [
                s for s in nearby_stations
                if s['id'] not in used_ids
                and search_start <= s['approx_mile'] <= need_stop_before
            ]

            if not candidates:
                candidates = [
                    s for s in nearby_stations
                    if s['id'] not in used_ids
                    and s['approx_mile'] > current_mile
                    and s['approx_mile'] <= need_stop_before
                ]
            if not candidates:
                break

            candidates.sort(key=lambda x: x['price'])
            best = candidates[0]

            gallons_to_buy = self.VEHICLE_RANGE_MILES / self.MPG

            fuel_stops.append({
                'station_name': best['name'],
                'address': f"{best['address']}, {best['city']}, {best['state']}",
                'city': best['city'],
                'state': best['state'],
                'price_per_gallon': round(best['price'], 2),
                'gallons': round(gallons_to_buy, 2),
                'cost': round(gallons_to_buy * best['price'], 2),
                'coordinates': best.get('coordinates'),
                'distance_from_start_miles': round(best['approx_mile'], 2),
            })

            used_ids.add(best['id'])
            current_mile = best['approx_mile']
            remaining_range = self.VEHICLE_RANGE_MILES

        return fuel_stops
    
    @staticmethod
    def _decode_polyline(encoded: str) -> List[List[float]]:
        """Decode a Google-encoded polyline string into a list of [lon, lat] pairs."""
        coords = []
        i, lat, lng = 0, 0, 0
        while i < len(encoded):
            for field in range(2):
                shift, result = 0, 0
                while True:
                    b = ord(encoded[i]) - 63
                    i += 1
                    result |= (b & 0x1F) << shift
                    shift += 5
                    if b < 0x20:
                        break
                delta = ~(result >> 1) if (result & 1) else (result >> 1)
                if field == 0:
                    lat += delta
                else:
                    lng += delta
            coords.append([lng / 1e5, lat / 1e5])
        return coords

    def _encode_polyline(self, coordinates: List[Tuple[float, float]]) -> str:
        """Simple polyline encoding for map display."""
        return ','.join([f"{lat},{lon}" for lat, lon in coordinates[::10]])
