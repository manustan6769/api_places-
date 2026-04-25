from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import os
from dotenv import load_dotenv

from main import RestaurantFinder, format_results, geocode_city, SEARCH_QUERY, DEFAULT_CELL_RADIUS

load_dotenv()

API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "YOUR_API_KEY_HERE")

app = FastAPI(
    title="Gluten-Free Restaurant Finder API",
    description="Search for gluten-free restaurants in any city using Google Places API with adaptive spiral coverage.",
    version="1.1.0"
)


class SearchRequest(BaseModel):
    city: str
    query: Optional[str] = SEARCH_QUERY
    cell_radius: Optional[int] = DEFAULT_CELL_RADIUS  # meters per search cell


class SearchResponse(BaseModel):
    city: str
    total_found: int
    results: list


@app.get("/health")
def health():
    """Health check — use this in n8n to verify the service is running."""
    return {"status": "ok"}


@app.post("/search", response_model=SearchResponse)
def search(req: SearchRequest):
    """
    Search for gluten-free restaurants in a given city.

    - **city**: City name (e.g. "Munich", "Berlin", "Vienna")
    - **query**: Search query (default: "gluten free restaurant")
    - **cell_radius**: Search radius per cell in meters (default: 3000)

    The search automatically expands outward from the city center
    and stops when no new results are found.

    Returns:
    - Restaurant details including picture_url (small preview image)
    """
    if API_KEY == "YOUR_API_KEY_HERE":
        raise HTTPException(status_code=500, detail="GOOGLE_PLACES_API_KEY not configured.")

    coords = geocode_city(req.city)
    if not coords:
        raise HTTPException(status_code=400, detail=f"Could not geocode city: '{req.city}'")

    finder = RestaurantFinder()
    places = finder.search_city(
        city=req.city,
        query=req.query,
        cell_radius=req.cell_radius
    )

    formatted = format_results(places, req.city)

    return {
        "city": req.city,
        "total_found": len(formatted),
        "results": formatted
    }


@app.get("/results/{city}")
def get_saved_results(city: str, limit: int = 100):
    """
    Retrieve previously saved results for a city from the database.
    Useful in n8n to fetch results without re-running the search.

    Returns restaurant details including picture_url.
    """
    import psycopg2
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", "5432"))
    DB_NAME = os.getenv("DB_NAME", "api_places")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

    try:
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT,
            database=DB_NAME, user=DB_USER, password=DB_PASSWORD
        )
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, address, city, latitude, longitude,
                   rating, review_count, website, phone, google_maps_type_label,
                   picture_url, opening_hours, price_level
            FROM restaurants
            WHERE LOWER(city) = LOWER(%s)
            ORDER BY rating DESC NULLS LAST
            LIMIT %s
        """, (city, limit))
        columns = [d[0] for d in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        return {"city": city, "total_found": len(rows), "results": rows}
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
