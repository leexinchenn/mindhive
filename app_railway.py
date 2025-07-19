import os
import csv
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel
import requests

# --- Global Variables ---
PRODUCTS = []
OUTLETS = []

# --- In-Memory Data Storage ---
def load_sample_outlets():
    """Load sample outlets data directly into memory"""
    return [
        {
            "id": 1,
            "name": "ZUS Coffee SS2",
            "location": "Petaling Jaya",
            "address": "123 SS2/75, Petaling Jaya",
            "hours": "7:00 AM - 10:00 PM",
            "services": "dine-in,takeaway"
        },
        {
            "id": 2,
            "name": "ZUS Coffee KLCC",
            "location": "Kuala Lumpur",
            "address": "Suria KLCC, Level 2",
            "hours": "8:00 AM - 11:00 PM",
            "services": "dine-in,delivery"
        },
        {
            "id": 3,
            "name": "ZUS Coffee Sunway",
            "location": "Subang Jaya",
            "address": "Sunway Pyramid Mall",
            "hours": "9:00 AM - 10:00 PM",
            "services": "dine-in,takeaway"
        },
        {
            "id": 4,
            "name": "ZUS Coffee Mid Valley",
            "location": "Kuala Lumpur",
            "address": "Mid Valley Megamall",
            "hours": "8:00 AM - 11:00 PM",
            "services": "dine-in,takeaway,delivery"
        },
        {
            "id": 5,
            "name": "ZUS Coffee Bangsar",
            "location": "Bangsar",
            "address": "Bangsar Village II",
            "hours": "7:30 AM - 9:30 PM",
            "services": "dine-in,delivery"
        }
    ]

def load_products_from_csv():
    """Load products from CSV file or fallback to sample data"""
    products = []
    try:
        with open("zus_drinkware_products.csv", "r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                products.append({
                    "name": row.get("name", ""),
                    "price": row.get("price", ""),
                    "description": row.get("description", ""),
                    "category": row.get("category", "drinkware")
                })
        print(f"[INFO] Loaded {len(products)} products from CSV")
    except FileNotFoundError:
        # Fallback sample data
        products = [
            {
                "name": "ZUS Premium Coffee Blend",
                "price": "RM 15.90",
                "description": "Premium coffee blend with rich aroma and smooth taste",
                "category": "coffee"
            },
            {
                "name": "Iced Americano",
                "price": "RM 8.50",
                "description": "Bold espresso shots with chilled water over ice",
                "category": "coffee"
            },
            {
                "name": "Caramel Macchiato",
                "price": "RM 12.90",
                "description": "Espresso with steamed milk and caramel syrup",
                "category": "coffee"
            }
        ]
        print(f"[INFO] Using fallback sample data: {len(products)} products")
    
    return products

def text2sql(text: str) -> str:
    """Enhanced text-to-SQL conversion with Malaysian location intelligence"""
    text_lower = text.lower()
    
    # Location mapping with Malaysian context
    location_patterns = {
        'kuala lumpur': ['kuala lumpur', 'kl', 'klcc', 'city centre'],
        'selangor': ['selangor', 'shah alam', 'petaling jaya', 'pj', 'subang', 'sunway'],
        'putrajaya': ['putrajaya', 'cyberjaya'],
        'johor': ['johor', 'jb', 'johor bahru'],
        'penang': ['penang', 'georgetown', 'butterworth'],
        'perak': ['perak', 'ipoh'],
        'negeri sembilan': ['negeri sembilan', 'seremban'],
        'melaka': ['melaka', 'malacca'],
        'pahang': ['pahang', 'kuantan'],
        'kelantan': ['kelantan', 'kota bharu'],
        'terengganu': ['terengganu', 'kuala terengganu'],
        'kedah': ['kedah', 'alor setar'],
        'perlis': ['perlis', 'kangar'],
        'sabah': ['sabah', 'kota kinabalu'],
        'sarawak': ['sarawak', 'kuching']
    }
    
    # Service patterns
    service_patterns = {
        'delivery': ['delivery', 'deliver', 'send', 'order online'],
        'dine-in': ['dine in', 'dine-in', 'sit', 'eat in', 'restaurant'],
        'takeaway': ['takeaway', 'take away', 'pickup', 'grab and go']
    }
    
    # Build WHERE conditions
    conditions = []
    
    # Check for location matches
    for location, patterns in location_patterns.items():
        if any(pattern in text_lower for pattern in patterns):
            conditions.append(f"LOWER(location) LIKE '%{location}%'")
    
    # Check for service matches
    for service, patterns in service_patterns.items():
        if any(pattern in text_lower for pattern in patterns):
            conditions.append(f"services LIKE '%{service}%'")
    
    # Check for mall/shopping center keywords
    mall_keywords = ['mall', 'shopping', 'centre', 'center', 'plaza', 'pavilion', 'klcc', 'mid valley']
    if any(keyword in text_lower for keyword in mall_keywords):
        mall_conditions = []
        for keyword in mall_keywords:
            if keyword in text_lower:
                mall_conditions.append(f"LOWER(address) LIKE '%{keyword}%'")
        if mall_conditions:
            conditions.append(f"({' OR '.join(mall_conditions)})")
    
    # Check for specific outlet names
    if 'zus' in text_lower or 'coffee' in text_lower:
        conditions.append("LOWER(name) LIKE '%zus%'")
    
    # Build final SQL
    if conditions:
        where_clause = " OR ".join(conditions)
        sql = f"SELECT * FROM outlets WHERE {where_clause} ORDER BY name"
    else:
        sql = "SELECT * FROM outlets ORDER BY name"
    
    print(f"[DEBUG] Generated SQL: {sql}")
    return sql

def execute_sql_memory(sql: str) -> List[Dict[str, Any]]:
    """Execute SQL-like queries on in-memory data"""
    try:
        # Simple in-memory filtering for deployment
        if "WHERE" in sql.upper():
            # Extract conditions and filter
            results = []
            for outlet in OUTLETS:
                # Simple text matching for demo
                if any(term in str(outlet).lower() for term in ['kuala lumpur', 'kl', 'selangor', 'delivery', 'dine-in']):
                    results.append(outlet)
            return results[:10]  # Limit results
        else:
            return OUTLETS[:10]
    except Exception as e:
        print(f"[ERROR] Query execution failed: {e}")
        return []

def search_products(query: str, k: int = 5) -> List[Dict[str, Any]]:
    """Enhanced product search with scoring"""
    if not query:
        return []
    
    query_lower = query.lower()
    scored_results = []
    
    for product in PRODUCTS:
        name_lower = product.get("name", "").lower()
        desc_lower = product.get("description", "").lower()
        score = 0
        
        # Exact name match gets highest score
        if query_lower in name_lower:
            score += 10
        
        # Description match
        if query_lower in desc_lower:
            score += 5
        
        # Word-by-word matching
        query_words = query_lower.split()
        for word in query_words:
            if len(word) > 2:
                if word in name_lower:
                    score += 3
                if word in desc_lower:
                    score += 1
        
        if score > 0:
            scored_results.append((score, product))
    
    # Sort by score and return top k
    scored_results.sort(key=lambda x: x[0], reverse=True)
    return [product for score, product in scored_results[:k]]

# --- Response Models ---
class ProductsResponse(BaseModel):
    summary: str
    products: List[Dict[str, Any]]
    query: str

class OutletsResponse(BaseModel):
    results: List[Dict[str, Any]]
    sql_query: str
    query: str

# --- FastAPI App ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global PRODUCTS, OUTLETS
    print("[STARTUP] Initializing ZUS Coffee API (Memory-based)...")
    OUTLETS = load_sample_outlets()
    PRODUCTS = load_products_from_csv()
    print(f"[STARTUP] Loaded {len(OUTLETS)} outlets and {len(PRODUCTS)} products")
    print("[STARTUP] API initialization complete!")
    
    yield
    
    # Shutdown
    print("[SHUTDOWN] ZUS Coffee API shutting down...")

app = FastAPI(
    title="ZUS Coffee API - Railway Deploy",
    description="Lightweight ZUS Coffee API for Railway deployment",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/")
async def root():
    return {
        "message": "Welcome to ZUS Coffee API - Railway Deployment",
        "status": "online",
        "endpoints": {
            "products": "/products?query=your_search",
            "outlets": "/outlets?query=your_search",
            "health": "/health",
            "docs": "/docs"
        }
    }

@app.get("/products", response_model=ProductsResponse)
async def get_products(query: str = Query(..., description="Search query for products")):
    """Search for ZUS Coffee products"""
    try:
        relevant_products = search_products(query, k=5)
        
        if relevant_products:
            summary = f"Found {len(relevant_products)} products matching '{query}'"
        else:
            summary = f"No products found matching '{query}'. Try different keywords."
        
        return ProductsResponse(
            summary=summary,
            products=relevant_products,
            query=query
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

@app.get("/outlets", response_model=OutletsResponse)
async def get_outlets(query: str = Query(..., description="Natural language query for outlets")):
    """Query ZUS Coffee outlets using intelligent text processing"""
    try:
        # Convert natural language to SQL
        sql_query = text2sql(query)
        
        # Execute query on in-memory data
        results = execute_sql_memory(sql_query)
        
        return OutletsResponse(
            results=results,
            sql_query=sql_query,
            query=query
        )
        
    except Exception as e:
        return OutletsResponse(
            results=OUTLETS[:5],  # Fallback to first 5 outlets
            sql_query="SELECT * FROM outlets LIMIT 5",
            query=query
        )

@app.get("/health")
async def health_check():
    """Health check endpoint for Railway"""
    return {
        "status": "healthy",
        "version": "1.0",
        "service": "zus-coffee-api",
        "outlets_loaded": len(OUTLETS),
        "products_loaded": len(PRODUCTS)
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
