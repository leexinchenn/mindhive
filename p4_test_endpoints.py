#!/usr/bin/env python3
"""
Test script to validate both Product-KB and Outlets Text2SQL endpoints
"""

import requests
import json
from typing import List, Dict

BASE_URL = "http://localhost:8000"

def test_products_endpoint():
    """Test the Product-KB Retrieval Endpoint"""
    print("Testing Product-KB Retrieval Endpoint...")
    
    test_queries = [
        "tumbler",
        "cold drink container", 
        "travel mug",
        "stainless steel",
        "ceramic"
    ]
    
    for query in test_queries:
        try:
            response = requests.get(f"{BASE_URL}/products", params={"query": query})
            if response.status_code == 200:
                data = response.json()
                print(f"PASS Query: '{query}' -> Found {data.get('total_found', 0)} products")
                if data.get('results'):
                    print(f"   Top result: {data['results'][0]['title']}")
            else:
                print(f"FAIL Query: '{query}' -> HTTP {response.status_code}")
        except Exception as e:
            print(f"FAIL Query: '{query}' -> Error: {e}")
    
    print()

def test_outlets_endpoint():
    """Test the Outlets Text2SQL Endpoint"""
    print("Testing Outlets Text2SQL Endpoint...")
    
    test_queries = [
        "all outlets",
        "outlets in KL", 
        "outlets in Selangor",
        "Sunway",
        "Petaling Jaya",
        "stores with delivery",
        "dine-in",
        "1 Utama"
    ]
    
    for query in test_queries:
        try:
            response = requests.get(f"{BASE_URL}/outlets", params={"query": query})
            if response.status_code == 200:
                data = response.json()
                if data.get('error'):
                    print(f"WARN Query: '{query}' -> {data['error']}")
                else:
                    print(f"PASS Query: '{query}' -> Found {data.get('total_found', 0)} outlets")
                    if data.get('results'):
                        print(f"   Sample result: {data['results'][0]['name']} ({data['results'][0]['location']})")
            else:
                print(f"FAIL Query: '{query}' -> HTTP {response.status_code}")
        except Exception as e:
            print(f"FAIL Query: '{query}' -> Error: {e}")
    
    print()

def test_api_documentation():
    """Test API documentation endpoints"""
    print("Testing API Documentation...")
    
    try:
        response = requests.get(f"{BASE_URL}/docs")
        if response.status_code == 200:
            print("PASS API docs available at /docs")
        else:
            print(f"FAIL API docs -> HTTP {response.status_code}")
            
        response = requests.get(f"{BASE_URL}/openapi.json")
        if response.status_code == 200:
            print("PASS OpenAPI spec available at /openapi.json")
        else:
            print(f"FAIL OpenAPI spec -> HTTP {response.status_code}")
    except Exception as e:
        print(f"FAIL API documentation -> Error: {e}")
    
    print()

def main():
    """Run all tests"""
    print("ZUS Coffee API Test Suite")
    print("=" * 50)
    
    # Test server availability
    try:
        response = requests.get(f"{BASE_URL}/docs", timeout=5)
        print(f"Server Status: {'Online' if response.status_code == 200 else 'Offline'}")
    except Exception:
        print("Server Status: Offline")
        print("Please ensure the server is running: python -m uvicorn p4:app --host 0.0.0.0 --port 8000")
        return
    
    print()
    
    # Run tests
    test_products_endpoint()
    test_outlets_endpoint() 
    test_api_documentation()
    
    print("Test suite completed!")

if __name__ == "__main__":
    main()
