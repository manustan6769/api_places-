# Google Places API - Gluten Restaurant Finder

## Project Overview
Python application that:
- Searches restaurants using Google Places API (searchText endpoint)
- Filters results for restaurants mentioned in reviews containing "gluten"
- Stores up to 10 matching restaurants in SQLite database
- Displays formatted results with ratings and review information

## Setup Instructions

### 1. Prerequisites
- Python 3.8 or higher
- Google Places API key (with billing enabled)

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure API Key
Set the environment variable before running:

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

### 4. Run the Application
```bash
python main.py
```

## Project Structure
```
.
├── main.py              # Main application logic
├── requirements.txt     # Python dependencies
├── README.md           # Detailed documentation
├── .github/
│   └── copilot-instructions.md  # This file
└── restaurants.db      # SQLite database (created on first run)
```

## Key Features

- **RestaurantFinder Class**: Handles API calls and database operations
- **Search Functionality**: Query Google Places API with custom search terms
- **Gluten Filtering**: Analyzes reviews for gluten-related keywords
- **Database Storage**: SQLite with 10-field schema for restaurant data
- **Results Display**: Formatted table output with ratings and metadata

## Customization

Edit constants in `main.py`:
- `SEARCH_QUERY`: Modify search keywords
- `MAX_RESULTS`: Change limit (default: 10)
- `GLUTEN_KEYWORDS`: Add/remove search keywords
- `DB_NAME`: Change database filename

## Database Schema

Table: `restaurants`
- id (TEXT, PRIMARY KEY)
- name (TEXT)
- address (TEXT)
- latitude, longitude (REAL)
- rating, review_count (REAL/INTEGER)
- website, phone (TEXT)
- gluten_mention_count (INTEGER)
- reviews_with_gluten (JSON)
- created_at (TIMESTAMP)

## Troubleshooting

**"Please set your Google Places API key"**
- Ensure GOOGLE_PLACES_API_KEY environment variable is set

**"API Error"**
- Verify API key has Places API enabled in Google Cloud Console
- Check billing is enabled
- Confirm API quota hasn't been exceeded

**"No results found"**
- Try different SEARCH_QUERY terms
- Verify API key is valid

## Notes
- Application requires active internet connection
- First run creates restaurants.db file
- Reviews stored as JSON for flexibility
- Duplicate entries are replaced in database
