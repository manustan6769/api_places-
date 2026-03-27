import requests
import psycopg2
import json
from typing import List, Dict, Optional
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
SEARCH_QUERY = "restaurants with gluten free options"
MAX_RESULTS = 100
GLUTEN_KEYWORDS = ["gluten", "gluten-free", "celiac", "gf"]


class RestaurantFinder:
    """Handles Google Places API calls and PostgreSQL database operations."""
    
    def __init__(self, api_key: str, db_host: str, db_port: int, db_name: str, db_user: str, db_password: str):
        self.api_key = api_key
        self.db_host = db_host
        self.db_port = db_port
        self.db_name = db_name
        self.db_user = db_user
        self.db_password = db_password
        self.session = requests.Session()
        self.init_database()
    
    def init_database(self):
        """Initialize PostgreSQL database with required tables."""
        try:
            conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.db_user,
                password=self.db_password
            )
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
                    gluten_mention_count INTEGER DEFAULT 0,
                    reviews_with_gluten TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
            conn.close()
        except psycopg2.Error as e:
            print(f"Database connection error: {e}")
    
    def search_restaurants(self, query: str) -> Optional[Dict]:
        """Search restaurants using Google Places API."""
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.location,places.rating,places.userRatingCount,places.websiteUri,places.internationalPhoneNumber,places.reviews"
        }
        
        payload = {
            "textQuery": query,
            "maxResultCount": 20  # Fetch more to filter by gluten mentions
        }
        
        try:
            response = self.session.post(
                GOOGLE_PLACES_API_URL,
                json=payload,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API Error: {e}")
            return None
    
    def has_gluten_mention(self, reviews: List[Dict]) -> tuple[int, List[str]]:
        """Check if reviews mention gluten-related keywords.
        
        Returns:
            tuple: (count of reviews with gluten mention, list of review texts)
        """
        gluten_reviews = []
        count = 0
        
        if not reviews:
            return count, gluten_reviews
        
        for review in reviews:
            # Handle nested text structure from Places API
            text_obj = review.get("text", {})
            if isinstance(text_obj, dict):
                text = text_obj.get("text", "").lower()
            else:
                text = str(text_obj).lower()
            
            if any(keyword in text for keyword in GLUTEN_KEYWORDS):
                count += 1
                gluten_reviews.append(text)
        
        return count, gluten_reviews
    
    def save_restaurant(self, place: Dict):
        """Save restaurant data to PostgreSQL database."""
        try:
            conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.db_user,
                password=self.db_password
            )
            cursor = conn.cursor()
        except psycopg2.Error as e:
            print(f"Database connection error: {e}")
            return False
        
        place_id = place.get("id", "")
        name = place.get("displayName", {}).get("text", "Unknown")
        address = place.get("formattedAddress", "")
        rating = place.get("rating", None)
        review_count = place.get("userRatingCount", 0)
        website = place.get("websiteUri", "")
        phone = place.get("internationalPhoneNumber", "")
        
        # Extract coordinates
        location = place.get("location", {})
        latitude = location.get("latitude", None)
        longitude = location.get("longitude", None)
        
        # Check for gluten mentions in reviews
        reviews = place.get("reviews", [])
        gluten_count, gluten_reviews = self.has_gluten_mention(reviews)
        gluten_reviews_json = json.dumps(gluten_reviews)
        
        try:
            cursor.execute("""
                INSERT INTO restaurants 
                (id, name, address, latitude, longitude, rating, review_count, 
                 website, phone, gluten_mention_count, reviews_with_gluten)
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
                    gluten_mention_count = EXCLUDED.gluten_mention_count,
                    reviews_with_gluten = EXCLUDED.reviews_with_gluten
            """, (
                place_id, name, address, latitude, longitude, rating, 
                review_count, website, phone, gluten_count, gluten_reviews_json
            ))
            conn.commit()
            return True
        except psycopg2.Error as e:
            print(f"Database Error: {e}")
            return False
        finally:
            conn.close()
    
    def get_gluten_restaurants(self, limit: int = 10) -> List[Dict]:
        """Retrieve restaurants with gluten mentions from database."""
        try:
            conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.db_user,
                password=self.db_password
            )
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, name, address, rating, review_count, website, phone, 
                       gluten_mention_count, reviews_with_gluten
                FROM restaurants
                WHERE gluten_mention_count > 0
                ORDER BY gluten_mention_count DESC, rating DESC
                LIMIT %s
            """, (limit,))
            
            columns = [description[0] for description in cursor.description]
            results = []
            
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
            
            conn.close()
            return results
        except psycopg2.Error as e:
            print(f"Database Error: {e}")
            return []
    
    def run(self, query: str = SEARCH_QUERY, limit: int = MAX_RESULTS):
        """Execute full workflow: search, filter, and save."""
        print(f"Searching for: {query}")
        print(f"Looking for gluten mentions in reviews...\n")
        
        # Search for restaurants
        results = self.search_restaurants(query)
        
        if not results or "places" not in results:
            print("No results found.")
            return
        
        places = results.get("places", [])
        print(f"Found {len(places)} restaurants. Processing...\n")
        
        gluten_count = 0
        for place in places:
            reviews = place.get("reviews", [])
            mention_count, _ = self.has_gluten_mention(reviews)
            
            if mention_count > 0:
                self.save_restaurant(place)
                gluten_count += 1
                print(f"✓ {place.get('displayName', {}).get('text', 'Unknown')} ({mention_count} gluten mentions)")
            
            if gluten_count >= limit:
                break
        
        print(f"\n{gluten_count} restaurants with gluten mentions saved to database.\n")
        
        # Display results
        self.display_results(limit)
    
    def display_results(self, limit: int = 10):
        """Display restaurants from database in formatted table."""
        restaurants = self.get_gluten_restaurants(limit)
        
        if not restaurants:
            print("No restaurants with gluten mentions found.")
            return
        
        print("=" * 120)
        print(f"{'Name':<30} {'Rating':<8} {'Reviews':<10} {'Gluten':<8} {'Address':<50}")
        print("=" * 120)
        
        for rest in restaurants:
            name = rest["name"][:27] + "..." if len(rest["name"]) > 30 else rest["name"]
            rating = f"{rest['rating']}" if rest['rating'] else "N/A"
            reviews = rest["review_count"]
            gluten = rest["gluten_mention_count"]
            address = rest["address"][:47] + "..." if len(rest["address"]) > 50 else rest["address"]
            
            print(f"{name:<30} {rating:<8} {reviews:<10} {gluten:<8} {address:<50}")
        
        print("=" * 120)


def main():
    """Main entry point."""
    # Verify API key
    if API_KEY == "YOUR_API_KEY_HERE":
        print("ERROR: Please set your Google Places API key.")
        print("Set the environment variable: GOOGLE_PLACES_API_KEY")
        print("\nExample (PowerShell):")
        print('  $env:GOOGLE_PLACES_API_KEY = "your-api-key"')
        print("\nExample (Command Prompt):")
        print('  set GOOGLE_PLACES_API_KEY=your-api-key')
        return
    
    # Get user input for search query
    print("=" * 60)
    print("Gluten-Free Restaurant Finder")
    print("=" * 60)
    user_query = input(f"\nEnter search term (default: '{SEARCH_QUERY}'): ").strip()
    
    if not user_query:
        user_query = SEARCH_QUERY
    
    user_limit = input(f"Enter maximum results to save (default: {MAX_RESULTS}): ").strip()
    
    try:
        limit = int(user_limit) if user_limit else MAX_RESULTS
    except ValueError:
        print(f"Invalid input. Using default: {MAX_RESULTS}")
        limit = MAX_RESULTS
    
    print()
    finder = RestaurantFinder(
        api_key=API_KEY,
        db_host=DB_HOST,
        db_port=DB_PORT,
        db_name=DB_NAME,
        db_user=DB_USER,
        db_password=DB_PASSWORD
    )
    finder.run(query=user_query, limit=limit)


if __name__ == "__main__":
    main()
