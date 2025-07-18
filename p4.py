import sqlite3
import csv
from typing import List
from fastapi import FastAPI, Query
from pydantic import BaseModel
import requests
from sentence_transformers import SentenceTransformer
import faiss


class ProductDoc(BaseModel):
    id: str
    title: str
    description: str


PRODUCT_DOCS = []
EMBEDDING_MODEL = None
FAISS_INDEX = None
DOC_EMBEDS = None


def ingest_product_docs_from_csv(csv_file="zus_drinkware_products.csv"):
    global PRODUCT_DOCS, EMBEDDING_MODEL, FAISS_INDEX, DOC_EMBEDS
    
    print(f"[INFO] Loading products from {csv_file}...")
    PRODUCT_DOCS = []
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                tags = row.get('tags', '').lower()
                if any(tag in tags for tag in ['tumbler', 'mug', 'cup', 'flask', 'bottle']):
                    description = ' '.join(row.get('description', '').split())
                    
                    product_doc = ProductDoc(
                        id=row.get('id', ''),
                        title=row.get('title', ''),
                        description=description
                    )
                    PRODUCT_DOCS.append(product_doc)
        
        print(f"[INFO] Loaded {len(PRODUCT_DOCS)} drinkware products")
        
        if not PRODUCT_DOCS:
            print("[WARNING] No products loaded! Check CSV file and filtering criteria.")
            return
        
        print("[INFO] Initializing sentence transformer model...")
        EMBEDDING_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
        
        print("[INFO] Creating embeddings for products...")
        texts = []
        for doc in PRODUCT_DOCS:
            combined_text = f"{doc.title}. {doc.description}"
            texts.append(combined_text)
        
        DOC_EMBEDS = EMBEDDING_MODEL.encode(texts, convert_to_numpy=True)
        
        print("[INFO] Building FAISS index...")
        dim = DOC_EMBEDS.shape[1]
        FAISS_INDEX = faiss.IndexFlatL2(dim)
        FAISS_INDEX.add(DOC_EMBEDS)
        
        print(f"[SUCCESS] Vector store initialized with {len(PRODUCT_DOCS)} products")
        
        for i, doc in enumerate(PRODUCT_DOCS[:3]):
            print(f"[DEBUG] Product {i+1}: {doc.title[:50]}...")
            
    except FileNotFoundError:
        print(f"[ERROR] CSV file {csv_file} not found!")
        EMBEDDING_MODEL = None
        FAISS_INDEX = None
        DOC_EMBEDS = None
    except Exception as e:
        print(f"[ERROR] Failed to load products: {e}")
        EMBEDDING_MODEL = None
        FAISS_INDEX = None
        DOC_EMBEDS = None


def ingest_product_docs_from_web(
    url="https://shop.zuscoffee.com/collections/drinkware",
):
    print("[INFO] Web scraping is challenging due to JavaScript rendering.")
    print("[INFO] Using CSV file as primary data source...")
    ingest_product_docs_from_csv()


def search_products(query: str, k: int = 2) -> List[ProductDoc]:
    global EMBEDDING_MODEL, FAISS_INDEX, PRODUCT_DOCS
    
    if EMBEDDING_MODEL is None or FAISS_INDEX is None or not PRODUCT_DOCS:
        print("[INFO] Initializing product search system...")
        ingest_product_docs_from_csv()
        
        if EMBEDDING_MODEL is None or FAISS_INDEX is None or not PRODUCT_DOCS:
            print("[ERROR] Failed to initialize product search system")
            return []
    
    try:
        query_vec = EMBEDDING_MODEL.encode([query], convert_to_numpy=True)
        distances, indices = FAISS_INDEX.search(query_vec, min(k, len(PRODUCT_DOCS)))
        
        relevance_threshold = 1.5
        results = []
        
        for i, (distance, idx) in enumerate(zip(distances[0], indices[0])):
            if distance < relevance_threshold and idx < len(PRODUCT_DOCS):
                results.append(PRODUCT_DOCS[idx])
                print(f"[DEBUG] Found match: {PRODUCT_DOCS[idx].title} (distance: {distance:.3f})")
        
        print(f"[INFO] Found {len(results)} relevant products for query: '{query}'")
        return results
        
    except Exception as e:
        print(f"[ERROR] Search failed: {e}")
        return []


def generate_product_summary(products: List[ProductDoc], query: str) -> str:
    if not products:
        return "No relevant products found."
    
    if len(products) == 1:
        product = products[0]
        return f"Found 1 product: {product.title}. {product.description[:100]}{'...' if len(product.description) > 100 else ''}"
    
    product_names = [p.title for p in products]
    summary = f"Top {len(products)} products: {', '.join(product_names)}"
    
    query_lower = query.lower()
    if any(word in query_lower for word in ['cold', 'iced', 'cool']):
        summary += ". Great for cold beverages and iced drinks."
    elif any(word in query_lower for word in ['hot', 'warm', 'coffee']):
        summary += ". Perfect for hot beverages like coffee and tea."
    elif 'travel' in query_lower or 'portable' in query_lower:
        summary += ". Ideal for on-the-go lifestyle."
    
    return summary


# --- Outlets Text2SQL Setup ---
DB_PATH = "zus_outlets.db"


def ingest_outlets_from_csv(csv_file="zus_outlets_kl_selangor.csv"):
    print(f"[INFO] Loading outlets from {csv_file}...")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS outlets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            location TEXT,
            address TEXT,
            hours TEXT,
            services TEXT,
            direction_link TEXT
        )
        """
    )
    
    try:
        c.execute("SELECT address FROM outlets LIMIT 1")
    except sqlite3.OperationalError:
        print("[INFO] Adding missing address column to outlets table...")
        c.execute("ALTER TABLE outlets ADD COLUMN address TEXT")
    
    try:
        c.execute("SELECT direction_link FROM outlets LIMIT 1")
    except sqlite3.OperationalError:
        print("[INFO] Adding missing direction_link column to outlets table...")
        c.execute("ALTER TABLE outlets ADD COLUMN direction_link TEXT")
    
    c.execute("DELETE FROM outlets")
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            outlets_data = []
            
            for row in reader:
                outlets_data.append((
                    row.get('name', '').strip(),
                    row.get('location', '').strip(),
                    row.get('address', '').strip(),
                    row.get('hours', 'Not specified').strip(),
                    row.get('services', 'Coffee, Food, Beverages').strip(),
                    row.get('direction_link', '').strip()
                ))
        
        c.executemany(
            "INSERT INTO outlets (name, location, address, hours, services, direction_link) VALUES (?, ?, ?, ?, ?, ?)",
            outlets_data
        )
        
        conn.commit()
        
        c.execute("SELECT COUNT(*) FROM outlets")
        count = c.fetchone()[0]
        
        print(f"[SUCCESS] Loaded {count} outlets into database")
        
        c.execute("SELECT name, location FROM outlets LIMIT 3")
        samples = c.fetchall()
        for i, (name, location) in enumerate(samples, 1):
            print(f"[DEBUG] Outlet {i}: {name} ({location})")
            
    except FileNotFoundError:
        print(f"[ERROR] CSV file {csv_file} not found!")
        ingest_outlets_from_web_fallback()
    except Exception as e:
        print(f"[ERROR] Failed to load outlets from CSV: {e}")
        ingest_outlets_from_web_fallback()
    finally:
        conn.close()


def ingest_outlets_from_web_fallback():
    print("[INFO] Using fallback sample data...")
    
    sample_data = [
        ("SS 2", "Petaling Jaya", "SS 2 Petaling Jaya, Selangor", "9AM-9PM", "Dine-in, Takeaway, Delivery", ""),
        ("1 Utama", "Bandar Utama", "1 Utama Shopping Centre, Petaling Jaya, Selangor", "10AM-10PM", "Dine-in, Takeaway", ""),
        ("KLCC", "Kuala Lumpur", "Suria KLCC, Kuala Lumpur", "10AM-10PM", "Dine-in, Takeaway, Delivery", ""),
        ("Sunway Pyramid", "Bandar Sunway", "Sunway Pyramid Shopping Mall, Bandar Sunway, Selangor", "10AM-10PM", "Dine-in, Takeaway, Delivery", ""),
        ("IOI City Mall", "Putrajaya", "IOI City Mall, Putrajaya", "10AM-10PM", "Dine-in, Takeaway", "")
    ]
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    try:
        c.executemany(
            "INSERT INTO outlets (name, location, address, hours, services, direction_link) VALUES (?, ?, ?, ?, ?, ?)",
            sample_data
        )
        conn.commit()
        print(f"[INFO] Added {len(sample_data)} sample outlets as fallback")
    except Exception as e:
        print(f"[ERROR] Failed to add sample data: {e}")
    finally:
        conn.close()


def ingest_outlets_from_web(
    url="https://zuscoffee.com/category/store/kuala-lumpur-selangor/",
):
    print("[INFO] Initializing outlets database...")
    ingest_outlets_from_csv()


def text2sql(nl_query: str) -> str:
    q = nl_query.lower().strip()
    
    if any(word in q for word in ['all', 'show all', 'list all', 'every']):
        return "SELECT * FROM outlets ORDER BY name"
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT DISTINCT name FROM outlets")
    outlet_names = [row[0].lower() for row in c.fetchall()]
    conn.close()
    
    conditions = []
    
    for outlet_name in outlet_names:
        if outlet_name in q:
            conditions.append(f"LOWER(name) LIKE '%{outlet_name}%'")
            break
    
    location_patterns = {
        'kuala lumpur': ['kl', 'kuala lumpur', 'wilayah persekutuan'],
        'selangor': ['selangor', 'shah alam', 'petaling jaya', 'pj'],
        'putrajaya': ['putrajaya'],
        'klang': ['klang'],
        'ampang': ['ampang'],
        'cheras': ['cheras'],
        'bangsar': ['bangsar'],
        'mont kiara': ['mont kiara'],
        'damansara': ['damansara'],
        'subang': ['subang'],
        'bangi': ['bangi'],
        'cyberjaya': ['cyberjaya'],
        'setapak': ['setapak'],
        'kepong': ['kepong'],
        'puchong': ['puchong']
    }
    
    for location, keywords in location_patterns.items():
        if any(keyword in q for keyword in keywords):
            conditions.append(f"LOWER(location) LIKE '%{location.split()[0]}%' OR LOWER(address) LIKE '%{location.split()[0]}%'")
            break
    
    if any(word in q for word in ['delivery', 'deliver']):
        conditions.append("LOWER(services) LIKE '%delivery%'")
    elif any(word in q for word in ['dine-in', 'dine in', 'sit in']):
        conditions.append("LOWER(services) LIKE '%dine%'")
    elif any(word in q for word in ['takeaway', 'take away', 'pickup', 'take out']):
        conditions.append("LOWER(services) LIKE '%takeaway%'")
    
    if any(word in q for word in ['open late', 'late night', '24 hour', '24/7']):
        conditions.append("LOWER(hours) LIKE '%24%' OR LOWER(hours) LIKE '%late%' OR LOWER(hours) LIKE '%11pm%' OR LOWER(hours) LIKE '%12am%'")
    elif any(word in q for word in ['morning', 'early', 'breakfast']):
        conditions.append("LOWER(hours) LIKE '%6am%' OR LOWER(hours) LIKE '%7am%' OR LOWER(hours) LIKE '%8am%'")
    
    mall_keywords = ['mall', 'shopping', 'centre', 'center', 'plaza', 'complex']
    if any(keyword in q for keyword in mall_keywords):
        mall_condition = " OR ".join([f"LOWER(address) LIKE '%{keyword}%'" for keyword in mall_keywords])
        conditions.append(f"({mall_condition})")
    
    if conditions:
        where_clause = " OR ".join(conditions)
        sql = f"SELECT * FROM outlets WHERE {where_clause} ORDER BY name"
    else:
        search_terms = q.split()
        fuzzy_conditions = []
        for term in search_terms:
            if len(term) > 2:
                fuzzy_conditions.append(f"(LOWER(name) LIKE '%{term}%' OR LOWER(location) LIKE '%{term}%' OR LOWER(address) LIKE '%{term}%')")
        
        if fuzzy_conditions:
            where_clause = " OR ".join(fuzzy_conditions)
            sql = f"SELECT * FROM outlets WHERE {where_clause} ORDER BY name"
        else:
            return ""
    
    print(f"[DEBUG] Generated SQL: {sql}")
    return sql


def execute_sql(sql: str) -> List[dict]:
    if not sql:
        return []
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute(sql)
        rows = c.fetchall()
        columns = [desc[0] for desc in c.description]
        results = [dict(zip(columns, row)) for row in rows]
    except Exception:
        results = []
    conn.close()
    return results


# --- FastAPI App ---
app = FastAPI(
    title="ZUS Coffee API",
    description="Product KB and Outlets Text2SQL endpoints",
    version="1.0",
)


@app.on_event("startup")
def startup_event():
    print("[STARTUP] Initializing ZUS Coffee API...")
    ingest_product_docs_from_csv()
    ingest_outlets_from_web()
    print("[STARTUP] API initialization complete!")


@app.get("/products")
def get_products(
    query: str = Query(..., description="User question about drinkware"), 
    k: int = Query(2, description="Number of top products to return")
):
    try:
        results = search_products(query, k)
        
        if not results:
            return {
                "summary": "No relevant drinkware products found for your query.",
                "results": [],
                "query": query,
                "total_found": 0
            }
        
        summary = generate_product_summary(results, query)
        
        product_results = []
        for doc in results:
            product_results.append({
                "id": doc.id,
                "title": doc.title,
                "description": doc.description
            })
        
        return {
            "summary": summary,
            "results": product_results,
            "query": query,
            "total_found": len(results)
        }
        
    except Exception as e:
        print(f"[ERROR] Product search failed: {e}")
        return {
            "summary": "An error occurred while searching for products.",
            "results": [],
            "query": query,
            "error": str(e),
            "total_found": 0
        }


@app.get("/outlets")
def get_outlets(
    query: str = Query(..., description="Natural language query about outlets")
):
    try:
        sql = text2sql(query)
        
        if not sql:
            return {
                "results": [],
                "error": "Could not translate query to SQL. Try queries like 'outlets in KL', 'SS 2', or 'all outlets'.",
                "query": query,
                "total_found": 0,
                "suggestions": [
                    "all outlets",
                    "outlets in Kuala Lumpur", 
                    "stores in Selangor",
                    "outlets with delivery",
                    "SS 2",
                    "KLCC"
                ]
            }
        
        results = execute_sql(sql)
        
        if not results:
            return {
                "results": [],
                "error": "No outlets found for your query.",
                "query": query,
                "sql_executed": sql,
                "total_found": 0
            }
        
        formatted_results = []
        for outlet in results:
            formatted_outlet = {
                "id": outlet.get("id"),
                "name": outlet.get("name"),
                "location": outlet.get("location"),
                "address": outlet.get("address"),
                "hours": outlet.get("hours"),
                "services": outlet.get("services")
            }
            if outlet.get("direction_link"):
                formatted_outlet["direction_link"] = outlet.get("direction_link")
            
            formatted_results.append(formatted_outlet)
        
        return {
            "results": formatted_results,
            "query": query,
            "sql_executed": sql,
            "total_found": len(results)
        }
        
    except Exception as e:
        print(f"[ERROR] Outlets query failed: {e}")
        return {
            "results": [],
            "error": f"An error occurred while processing your query: {str(e)}",
            "query": query,
            "total_found": 0
        }


# --- Example Chatbot Integration ---
def chatbot_call_products(user_query):
    resp = requests.get("http://localhost:8000/products", params={"query": user_query})
    try:
        return resp.json()
    except Exception as e:
        print(f"[ERROR] Could not decode JSON from /products endpoint. Status: {resp.status_code}")
        print(f"Response text: {resp.text}")
        print(f"Exception: {e}")
        return {"error": "Invalid response from /products endpoint", "details": str(e), "response_text": resp.text}


def chatbot_call_outlets(user_query):
    resp = requests.get("http://localhost:8000/outlets", params={"query": user_query})
    return resp.json()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("p4:app", host="0.0.0.0", port=8000, reload=True)
