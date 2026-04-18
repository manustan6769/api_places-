import requests
import psycopg2
import json
import math
import time
from typing import List, Dict, Optional, Tuple
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
GOOGLE_PLACES_API_URL = "https://places.googleapis.com/v1/places:searchText"
API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "YOUR_API_KEY_HERE")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "api_places")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

SEARCH_QUERY = "gluten free restaurant"
DEFAULT_CELL_RADIUS = int(os.getenv("DEFAULT_CELL_RADIUS", "3000"))  # 3 km per cell
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


def geocode_city(city: str) -> Optional[Tuple[float, float]]:
    """Resolve city name to (latitude, longitude) using Nominatim (free, no key needed)."""
    try:
        response = requests.get(
            NOMINATIM_URL,
            params={"q": city, "format": "json", "limit": 1},
            headers={"User-Agent": "GlutenFreeFinder/1.0"},
            timeout=10
        )
        response.raise_for_status()
        results = response.json()
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
    except requests.exceptions.RequestException as e:
        print(f"Geocoding error: {e}")
    return None


def build_spiral_grid(center_lat: float, center_lng: float, cell_radius_m: int) -> List[Tuple[float, float]]:
    """
    Generate grid points in an expanding spiral starting from center.
    Yields rings 0, 1, 2, ... — caller stops when a full ring returns no new results.
    Each ring is a generator of (lat, lng) center points for that ring.
    """
    # Convert radius to degrees (approximate)
    lat_step = (cell_radius_m / 1000) / 111.0        # 1 degree lat ≈ 111 km
    lng_step = (cell_radius_m / 1000) / (111.0 * math.cos(math.radians(center_lat)))

    ring = 0
    while True:
        if ring == 0:
            yield ring, [(center_lat, center_lng)]
        else:
            cells = []
            # Top row: left to right
            for x in range(-ring, ring + 1):
                cells.append((center_lat + ring * lat_step, center_lng + x * lng_step))
            # Bottom row: right to left
            for x in range(ring, -ring - 1, -1):
                cells.append((center_lat - ring * lat_step, center_lng + x * lng_step))
            # Left column (excluding corners)
            for y in range(ring - 1, -ring + 1, -1):
                cells.append((center_lat + y * lat_step, center_lng - ring * lng_step))
            # Right column (excluding corners)
            for y in range(-ring + 1, ring):
                cells.append((center_lat + y * lat_step, center_lng + ring * lng_step))
            yield ring, cells
        ring += 1


class RestaurantFinder:
    """Handles Google Places API calls and PostgreSQL database operations."""

    def __init__(self):
        self.api_key = API_KEY
        self.session = requests.Session()
        self.init_database()

    def init_database(self):
        """Initialize PostgreSQL database with required tables."""
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS restaurants (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    address TEXT,
                    latitude REAL,
                    longitude REAL,
                    rating REAL,
                    review_count INTEGER,
                    website TEXT,
                    phone TEXT,
                    google_maps_type_label TEXT,
                    city TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            conn.close()
        except psycopg2.Error as e:
            print(f"Database init error: {e}")

    def _connect(self):
        return psycopg2.connect(
            host=DB_HOST, port=DB_PORT,
            database=DB_NAME, user=DB_USER, password=DB_PASSWORD
        )

    def search_places(self, query: str, latitude: float, longitude: float, radius: int) -> List[Dict]:
        """Call Google Places searchText API for a single cell."""
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": (
                "places.id,places.displayName,places.formattedAddress,"
                "places.location,places.rating,places.userRatingCount,"
                "places.websiteUri,places.internationalPhoneNumber,"
                "places.primaryTypeDisplayName,places.types"
            )
        }
        payload = {
            "textQuery": query,
            "maxResultCount": 20,
            "locationBias": {
                "circle": {
                    "center": {"latitude": latitude, "longitude": longitude},
                    "radius": radius
                }
            }
        }
        try:
            response = self.session.post(
                GOOGLE_PLACES_API_URL, json=payload, headers=headers, timeout=10
            )
            response.raise_for_status()
            return response.json().get("places", [])
        except requests.exceptions.RequestException as e:
            print(f"API error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"API response body: {e.response.text}")
            return []

    def save_restaurant(self, place: Dict, city: str):
        """Save or update a restaurant in the database."""
        SPECIFIC_TYPES = {
            "gluten_free_restaurant": "Gluten-free Restaurant",
            "vegan_restaurant": "Vegan Restaurant",
            "vegetarian_restaurant": "Vegetarian Restaurant",
            "organic_restaurant": "Organic Restaurant",
            "italian_restaurant": "Italian Restaurant",
            "japanese_restaurant": "Japanese Restaurant",
            "chinese_restaurant": "Chinese Restaurant",
            "french_restaurant": "French Restaurant",
            "mediterranean_restaurant": "Mediterranean Restaurant",
            "turkish_restaurant": "Turkish Restaurant",
            "bakery": "Bakery",
            "cafe": "Cafe",
        }
        all_types = place.get("types", [])
        type_label = next(
            (SPECIFIC_TYPES[t] for t in all_types if t in SPECIFIC_TYPES),
            place.get("primaryTypeDisplayName", {}).get("text", "")
        )

        location = place.get("location", {})
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO restaurants
                (id, name, address, latitude, longitude, rating, review_count,
                 website, phone, google_maps_type_label, city)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    address = EXCLUDED.address,
                    latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude,
                    rating = EXCLUDED.rating,
                    review_count = EXCLUDED.review_count,
                    website = EXCLUDED.website,
                    phone = EXCLUDED.phone,
                    google_maps_type_label = EXCLUDED.google_maps_type_label,
                    city = EXCLUDED.city
            """, (
                place.get("id"),
                place.get("displayName", {}).get("text", "Unknown"),
                place.get("formattedAddress", ""),
                location.get("latitude"),
                location.get("longitude"),
                place.get("rating"),
                place.get("userRatingCount", 0),
                place.get("websiteUri", ""),
                place.get("internationalPhoneNumber", ""),
                type_label,
                city
            ))
            conn.commit()
            conn.close()
            return True
        except psycopg2.Error as e:
            print(f"Database error: {e}")
            return False

    def search_city(self, city: str, query: str = SEARCH_QUERY, cell_radius: int = DEFAULT_CELL_RADIUS) -> List[Dict]:
        """
        Full adaptive spiral search for a city.
        Geocodes the city, then expands outward ring by ring until a ring returns no new results.
        Returns list of unique places.
        """
        coords = geocode_city(city)
        if not coords:
            raise ValueError(f"Could not geocode city: {city}")

        center_lat, center_lng = coords
        full_query = f"{query} in {city}"
        seen_ids = set()
        all_results = []

        print(f"Searching '{full_query}' from center ({center_lat:.4f}, {center_lng:.4f})")

        for ring, cells in build_spiral_grid(center_lat, center_lng, cell_radius):
            new_in_ring = 0

            for lat, lng in cells:
                places = self.search_places(full_query, lat, lng, cell_radius)
                time.sleep(0.1)  # be polite to the API

                for place in places:
                    pid = place.get("id")
                    if pid and pid not in seen_ids:
                        seen_ids.add(pid)
                        self.save_restaurant(place, city)
                        all_results.append(place)
                        new_in_ring += 1

            print(f"  Ring {ring}: {len(cells)} cells, {new_in_ring} new places")

            if ring > 0 and new_in_ring == 0:
                print(f"  No new results in ring {ring} — search complete.")
                break

        return all_results


def format_results(places: List[Dict], city: str) -> List[Dict]:
    """Format raw Places API results into clean JSON for API responses."""
    SPECIFIC_TYPES = {
        "gluten_free_restaurant": "Gluten-free Restaurant",
        "vegan_restaurant": "Vegan Restaurant",
        "vegetarian_restaurant": "Vegetarian Restaurant",
        "organic_restaurant": "Organic Restaurant",
        "italian_restaurant": "Italian Restaurant",
        "japanese_restaurant": "Japanese Restaurant",
        "chinese_restaurant": "Chinese Restaurant",
        "french_restaurant": "French Restaurant",
        "mediterranean_restaurant": "Mediterranean Restaurant",
        "turkish_restaurant": "Turkish Restaurant",
        "bakery": "Bakery",
        "cafe": "Cafe",
    }
    output = []
    for place in places:
        all_types = place.get("types", [])
        type_label = next(
            (SPECIFIC_TYPES[t] for t in all_types if t in SPECIFIC_TYPES),
            place.get("primaryTypeDisplayName", {}).get("text", "")
        )
        location = place.get("location", {})
        output.append({
            "id": place.get("id"),
            "name": place.get("displayName", {}).get("text", "Unknown"),
            "address": place.get("formattedAddress", ""),
            "city": city,
            "latitude": location.get("latitude"),
            "longitude": location.get("longitude"),
            "rating": place.get("rating"),
            "review_count": place.get("userRatingCount", 0),
            "website": place.get("websiteUri", ""),
            "phone": place.get("internationalPhoneNumber", ""),
            "type": type_label,
        })
    return output
