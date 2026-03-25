# Google Places API - Gluten-Free Restaurant Finder

This Python application searches for restaurants mentioning "gluten" in their reviews using the Google Places API and stores the results in a SQLite database.

## Features

- Search restaurants using Google Places API (Text Search endpoint)
- Filter results by gluten mentions in customer reviews
- Store up to 10 restaurants with gluten mentions in SQLite database
- Display formatted results with ratings, review counts, and contact information
- Extract and save individual reviews mentioning gluten

## Prerequisites

- Python 3.8+
- Google Places API key (requires setup on Google Cloud)

## Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Get your Google Places API key:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project
   - Enable the "Places API" (New)
   - Create an API key under Credentials
   - You may need to enable billing

## Configuration

Set your Google Places API key as an environment variable:

**PowerShell:**
```powershell
$env:GOOGLE_PLACES_API_KEY = "your-api-key-here"
python main.py
```

**Command Prompt:**
```cmd
set GOOGLE_PLACES_API_KEY=your-api-key-here
python main.py
```

**Linux/macOS:**
```bash
export GOOGLE_PLACES_API_KEY="your-api-key-here"
python main.py
```

## Usage

Run the script:
```bash
python main.py
```

The program will prompt you to:
1. Enter a search term (e.g., "restaurants in New York", "gluten-free cafes in London")
   - Press Enter to use the default: "restaurants with gluten free options"
2. Enter maximum number of results to save (default: 10)
   - Press Enter to use the default

Then it will search the API, filter for gluten mentions in reviews, and display results.

### Customizing the Search

Edit `main.py` to modify:
- `SEARCH_QUERY`: Change the search keywords (default: "restaurants with gluten free options")
- `MAX_RESULTS`: Change the limit of restaurants to save (default: 10)
- `GLUTEN_KEYWORDS`: Add/remove keywords to search for in reviews

## Database Schema

The SQLite database (`restaurants.db`) contains a `restaurants` table with:

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT | Place ID (Primary Key) |
| name | TEXT | Restaurant name |
| address | TEXT | Formatted address |
| latitude | REAL | Latitude coordinate |
| longitude | REAL | Longitude coordinate |
| rating | REAL | Google rating (0-5) |
| review_count | INTEGER | Total number of reviews |
| website | TEXT | Website URL |
| phone | TEXT | Phone number |
| gluten_mention_count | INTEGER | Count of reviews mentioning gluten |
| reviews_with_gluten | TEXT | JSON array of review texts |
| created_at | TIMESTAMP | Record creation timestamp |

## Output Example

```
Searching for: restaurants with gluten free options
Looking for gluten mentions in reviews...

Found 20 restaurants. Processing...

✓ Restaurant A (3 gluten mentions)
✓ Restaurant B (2 gluten mentions)
...

10 restaurants with gluten mentions saved to database.

========================================================================================================================
Name                           Rating   Reviews    Gluten   Address
========================================================================================================================
Restaurant A                   4.5      125        3        123 Main St, City, State
Restaurant B                   4.2      98         2        456 Oak Ave, City, State
...
========================================================================================================================
```

## Error Handling

- API errors are caught and displayed without crashing
- Database errors are logged
- Missing API key is detected with helpful error message
- Invalid API responses are handled gracefully

## Notes

- The API key in environment variables is more secure than hardcoding
- Reviews are stored as JSON strings for flexibility
- Database uses REPLACE to avoid duplicate entries
- Restaurants are ordered by gluten mentions (descending) then rating (descending)

## Troubleshooting

**"No results found"**
- Check your API key is valid and billing is enabled
- Try changing the SEARCH_QUERY

**"API Error"**
- Verify your API key has Places API enabled
- Check your quota hasn't been exceeded
- Ensure the API key is for the correct Google Cloud project

**"Please set your Google Places API key"**
- Set the GOOGLE_PLACES_API_KEY environment variable before running

## License

Free to use and modify.
