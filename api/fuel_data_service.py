import csv
from pathlib import Path
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
from functools import lru_cache

STATE_COORDS = {
    'AL': (32.3182, -86.9023), 'AK': (63.5888, -154.4931), 'AZ': (34.0489, -111.0937),
    'AR': (35.2010, -91.8318), 'CA': (36.7783, -119.4179), 'CO': (39.5501, -105.7821),
    'CT': (41.6032, -73.0877), 'DE': (38.9108, -75.5277), 'FL': (27.9944, -81.7603),
    'GA': (32.1656, -82.9001), 'HI': (19.8968, -155.5828), 'ID': (44.0682, -114.7420),
    'IL': (40.6331, -89.3985), 'IN': (40.2672, -86.1349), 'IA': (41.8780, -93.0977),
    'KS': (39.0119, -98.4842), 'KY': (37.8393, -84.2700), 'LA': (30.9843, -91.9623),
    'ME': (45.2538, -69.4455), 'MD': (39.0458, -76.6413), 'MA': (42.4072, -71.3824),
    'MI': (44.3148, -85.6024), 'MN': (46.7296, -94.6859), 'MS': (32.3547, -89.3985),
    'MO': (37.9643, -91.8318), 'MT': (46.8797, -110.3626), 'NE': (41.4925, -99.9018),
    'NV': (38.8026, -116.4194), 'NH': (43.1939, -71.5724), 'NJ': (40.0583, -74.4057),
    'NM': (34.5199, -105.8701), 'NY': (42.1657, -74.9481), 'NC': (35.7596, -79.0193),
    'ND': (47.5515, -101.0020), 'OH': (40.4173, -82.9071), 'OK': (35.4676, -97.5164),
    'OR': (43.8041, -120.5542), 'PA': (41.2033, -77.1945), 'RI': (41.5801, -71.4774),
    'SC': (33.8361, -81.1637), 'SD': (43.9695, -99.9018), 'TN': (35.5175, -86.5804),
    'TX': (31.9686, -99.9018), 'UT': (39.3210, -111.0937), 'VT': (44.5588, -72.5778),
    'VA': (37.4316, -78.6569), 'WA': (47.7511, -120.7401), 'WV': (38.5976, -80.4549),
    'WI': (43.7844, -88.7879), 'WY': (43.0760, -107.2903), 'DC': (38.9072, -77.0369),
}

def _deterministic_hash(s: str) -> int:
    h = 0
    for ch in s:
        h = ((h * 31) + ord(ch)) & 0xFFFFFFFF
    return h


class FuelDataService:
    """Service to load and query fuel station data efficiently."""
    
    def __init__(self):
        self.stations = []
        self.geocoder = Nominatim(user_agent="fuel_route_api")
        self._load_fuel_data()
    
    def _load_fuel_data(self):
        """Load fuel prices from CSV file with deterministic coordinates."""
        csv_path = Path(__file__).parent / 'fuel_prices.csv'
        
        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                try:
                    city = row['City'].strip()
                    state = row['State'].strip()
                    station_id = row['OPIS Truckstop ID']

                    base = STATE_COORDS.get(state, (39.8283, -98.5795))
                    h = _deterministic_hash(f"{city}-{state}-{station_id}")
                    lat_offset = ((h % 400) - 200) / 100
                    lng_offset = (((h >> 8) % 600) - 300) / 100

                    station = {
                        'id': station_id,
                        'name': row['Truckstop Name'].strip(),
                        'address': row['Address'].strip(),
                        'city': city,
                        'state': state,
                        'price': float(row['Retail Price']),
                        'coordinates': (base[0] + lat_offset, base[1] + lng_offset),
                    }
                    self.stations.append(station)
                except (ValueError, KeyError):
                    continue
    
    @lru_cache(maxsize=1000)
    def geocode_location(self, location_string):
        """Geocode a location string to coordinates with caching."""
        try:
            location = self.geocoder.geocode(location_string, country_codes=['us'])
            if location:
                return (location.latitude, location.longitude)
        except Exception as e:
            print(f"Geocoding error for {location_string}: {e}")
        return None
    
    def get_station_coordinates(self, station):
        """Get coordinates for a station (already assigned at load time)."""
        return station['coordinates']
    
    def find_stations_along_route(self, route_coordinates, max_distance_km=50):
        """
        Find fuel stations near the route using bounding-box pre-filter.
        
        Args:
            route_coordinates: List of (lat, lon) tuples representing the route
            max_distance_km: Maximum distance from route to consider a station
        """
        deg_margin = max_distance_km / 111.0

        sample_step = max(1, len(route_coordinates) // 80)
        sampled = [route_coordinates[i] for i in range(0, len(route_coordinates), sample_step)]

        min_lat = min(p[0] for p in sampled) - deg_margin
        max_lat = max(p[0] for p in sampled) + deg_margin
        min_lon = min(p[1] for p in sampled) - deg_margin
        max_lon = max(p[1] for p in sampled) + deg_margin

        bbox_stations = [
            s for s in self.stations
            if s['coordinates']
            and min_lat <= s['coordinates'][0] <= max_lat
            and min_lon <= s['coordinates'][1] <= max_lon
        ]

        nearby_stations = []
        found_ids = set()

        for station in bbox_stations:
            if station['id'] in found_ids:
                continue

            coords = station['coordinates']
            min_distance = float('inf')
            closest_route_index = 0

            for i, route_point in enumerate(sampled):
                dlat = abs(coords[0] - route_point[0])
                dlon = abs(coords[1] - route_point[1])
                if dlat > deg_margin or dlon > deg_margin:
                    continue
                dist = geodesic(coords, route_point).kilometers
                if dist < min_distance:
                    min_distance = dist
                    closest_route_index = i * sample_step

            if min_distance <= max_distance_km:
                station_copy = station.copy()
                station_copy['distance_from_route'] = min_distance
                station_copy['route_index'] = closest_route_index
                nearby_stations.append(station_copy)
                found_ids.add(station['id'])

        nearby_stations.sort(key=lambda x: x['route_index'])
        return nearby_stations


_fuel_service_instance = None

def get_fuel_service():
    """Get or create the global fuel service instance."""
    global _fuel_service_instance
    if _fuel_service_instance is None:
        _fuel_service_instance = FuelDataService()
    return _fuel_service_instance
