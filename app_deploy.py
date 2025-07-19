import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import sqlite3
import csv
import requests
from typing import List, Dict, Any
import json


# --- Database Operations ---
def init_database():
    """Initialize the database and create tables"""
    conn = sqlite3.connect("zus_outlets.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS outlets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location TEXT,
            address TEXT,
            phone TEXT,
            opening_hours TEXT
        )
    """)
    
    conn.commit()
    conn.close()


def execute_sql(query: str) -> List[Dict[str, Any]]:
    """Execute SQL query and return results"""
    try:
        conn = sqlite3.connect("zus_outlets.db")
        cursor = conn.cursor()
        cursor.execute(query)
        
        # Get column names
        columns = [description[0] for description in cursor.description] if cursor.description else []
        
        # Fetch results
        rows = cursor.fetchall()
        
        # Convert to list of dictionaries
        results = [dict(zip(columns, row)) for row in rows]
        
        conn.close()
        return results
        
    except Exception as e:
        print(f"Database error: {e}")
        return []


def text2sql(query: str) -> str:
    """Convert natural language to SQL (simplified version)"""
    query_lower = query.lower()
    
    # Basic text2sql logic for demo
    if "all" in query_lower or "list" in query_lower:
        return "SELECT * FROM outlets ORDER BY name"
    elif "count" in query_lower:
        return "SELECT COUNT(*) as total_outlets FROM outlets"
    else:
        # Search for outlets containing keywords
        words = query_lower.split()
        conditions = []
        for word in words:
            if len(word) > 2:  # Skip short words
                condition = f"(LOWER(name) LIKE '%{word}%' OR LOWER(location) LIKE '%{word}%' OR LOWER(address) LIKE '%{word}%')"
                conditions.append(condition)
        
        if conditions:
            where_clause = " OR ".join(conditions)
            return f"SELECT * FROM outlets WHERE {where_clause} ORDER BY name"
        else:
            return "SELECT * FROM outlets ORDER BY name"


def ingest_outlets_from_web():
    """Load outlets data from web scraping (simplified)"""
    sample_outlets = [
        ("ZUS Coffee SS2", "Petaling Jaya", "123 SS2/75, Petaling Jaya", "03-12345678", "7:00 AM - 10:00 PM"),
        ("ZUS Coffee KLCC", "Kuala Lumpur", "Suria KLCC, Level 2", "03-87654321", "8:00 AM - 11:00 PM"),
        ("ZUS Coffee Sunway", "Subang Jaya", "Sunway Pyramid Mall", "03-11223344", "9:00 AM - 10:00 PM"),
        ("ZUS Coffee Mid Valley", "Kuala Lumpur", "Mid Valley Megamall", "03-55667788", "8:00 AM - 11:00 PM"),
        ("ZUS Coffee Bangsar", "Bangsar", "Bangsar Village II", "03-99887766", "7:30 AM - 9:30 PM"),
    ]
    
    conn = sqlite3.connect("zus_outlets.db")
    cursor = conn.cursor()
    
    # Clear existing data
    cursor.execute("DELETE FROM outlets")
    
    # Insert sample data
    for outlet in sample_outlets:
        cursor.execute("""
            INSERT INTO outlets (name, location, address, phone, opening_hours)
            VALUES (?, ?, ?, ?, ?)
        """, outlet)
    
    conn.commit()
    conn.close()
    print("[INFO] Sample outlets data loaded successfully")


def load_products_from_csv():
    """Load products from CSV file"""
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
        print("[WARNING] CSV file not found, using sample products")
        products = [
            {"name": "OG CUP 2.0 With Screw-On Lid 500ml", "price": "RM45.00", "description": "Durable coffee cup", "category": "drinkware"},
            {"name": "All-Can Tumbler 600ml", "price": "RM55.00", "description": "Insulated tumbler", "category": "drinkware"},
            {"name": "ZUS Travel Mug", "price": "RM35.00", "description": "Perfect for travel", "category": "drinkware"}
        ]
    
    return products


# Global products list
PRODUCTS = []


def search_products(query: str, k: int = 5) -> List[Dict[str, Any]]:
    """Simple text search in products"""
    if not query:
        return []
    
    query_lower = query.lower()
    results = []
    
    for product in PRODUCTS:
        name_lower = product.get("name", "").lower()
        desc_lower = product.get("description", "").lower()
        
        if query_lower in name_lower or query_lower in desc_lower:
            results.append(product)
    
    return results[:k]


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
    global PRODUCTS
    print("[STARTUP] Initializing ZUS Coffee API...")
    init_database()
    ingest_outlets_from_web()
    PRODUCTS = load_products_from_csv()
    print("[STARTUP] API initialization complete!")
    yield
    # Shutdown (if needed)


app = FastAPI(
    title="ZUS Coffee API",
    description="Product KB and Outlets Text2SQL endpoints - Demo Version",
    version="1.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    return {
        "message": "Welcome to ZUS Coffee API - Demo Version",
        "endpoints": {
            "products": "/products?query=your_search",
            "outlets": "/outlets?query=your_search",
            "docs": "/docs"
        }
    }


@app.get("/products", response_model=ProductsResponse)
async def get_products(query: str = Query(..., description="Search query for products")):
    """Search for ZUS Coffee products using RAG"""
    try:
        # Search products
        relevant_products = search_products(query, k=5)
        
        # Generate summary
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
    """Query ZUS Coffee outlets using Text2SQL"""
    try:
        # Convert natural language to SQL
        sql_query = text2sql(query)
        
        # Execute SQL query
        results = execute_sql(sql_query)
        
        return OutletsResponse(
            results=results,
            sql_query=sql_query,
            query=query
        )
        
    except Exception as e:
        return OutletsResponse(
            results=[],
            sql_query="",
            query=query
        )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "version": "1.0"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
