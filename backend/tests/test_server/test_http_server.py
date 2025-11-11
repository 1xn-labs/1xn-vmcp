#!/usr/bin/env python3
"""
Test HTTP Server
================

A comprehensive test HTTP server with various endpoints, authentication types,
and complexity for testing HTTP tool functionality.

Features:
- Multiple HTTP methods (GET, POST, PUT, PATCH, DELETE)
- Various authentication types (Bearer, API Key, Basic Auth, Custom)
- Complex request/response patterns
- Error handling scenarios
- File upload/download endpoints
- WebSocket support
- Rate limiting simulation
"""

import asyncio
import json
import base64
import hashlib
import hmac
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends, Request, Response, status
from fastapi.security import HTTPBearer, HTTPBasic, HTTPBasicCredentials
from fastapi.security.api_key import APIKeyHeader, APIKeyQuery
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field
from starlette.websockets import WebSocket, WebSocketDisconnect
import uvicorn


# ============================================================================
# DATA MODELS
# ============================================================================

class User(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    is_active: bool = True
    created_at: datetime
    last_login: Optional[datetime] = None

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., pattern=r'^[^@]+@[^@]+\.[^@]+$')
    full_name: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=8)

class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[str] = Field(None, pattern=r'^[^@]+@[^@]+\.[^@]+$')
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    is_active: Optional[bool] = None

class Product(BaseModel):
    id: int
    name: str
    description: str
    price: float
    category: str
    in_stock: bool
    tags: List[str] = []
    metadata: Dict[str, Any] = {}

class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., max_length=500)
    price: float = Field(..., gt=0)
    category: str = Field(..., min_length=1, max_length=50)
    in_stock: bool = True
    tags: List[str] = []
    metadata: Dict[str, Any] = {}

class Order(BaseModel):
    id: int
    user_id: int
    products: List[Dict[str, Any]]
    total_amount: float
    status: str
    created_at: datetime
    updated_at: datetime

class ApiResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None
    timestamp: datetime = Field(default_factory=datetime.now)

class ErrorResponse(BaseModel):
    error: str
    detail: str
    timestamp: datetime = Field(default_factory=datetime.now)


# ============================================================================
# IN-MEMORY DATABASE
# ============================================================================

class TestDatabase:
    def __init__(self):
        self.users: Dict[int, User] = {}
        self.products: Dict[int, Product] = {}
        self.orders: Dict[int, Order] = {}
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.rate_limits: Dict[str, List[float]] = {}
        self._initialize_data()
    
    def _initialize_data(self):
        # Initialize with sample data
        users_data = [
            {"id": 1, "username": "admin", "email": "admin@test.com", "full_name": "Admin User", "created_at": datetime.now() - timedelta(days=30)},
            {"id": 2, "username": "john_doe", "email": "john@test.com", "full_name": "John Doe", "created_at": datetime.now() - timedelta(days=15)},
            {"id": 3, "username": "jane_smith", "email": "jane@test.com", "full_name": "Jane Smith", "created_at": datetime.now() - timedelta(days=7)},
        ]
        
        for user_data in users_data:
            self.users[user_data["id"]] = User(**user_data)
        
        products_data = [
            {"id": 1, "name": "Laptop", "description": "High-performance laptop", "price": 999.99, "category": "Electronics", "in_stock": True, "tags": ["computer", "portable"], "metadata": {"brand": "TechCorp", "warranty": "2 years"}},
            {"id": 2, "name": "Mouse", "description": "Wireless mouse", "price": 29.99, "category": "Electronics", "in_stock": True, "tags": ["peripheral", "wireless"], "metadata": {"brand": "TechCorp", "battery_life": "6 months"}},
            {"id": 3, "name": "Book", "description": "Programming guide", "price": 49.99, "category": "Books", "in_stock": False, "tags": ["education", "programming"], "metadata": {"author": "Tech Author", "pages": 300}},
        ]
        
        for product_data in products_data:
            self.products[product_data["id"]] = Product(**product_data)

# Global database instance
db = TestDatabase()


# ============================================================================
# AUTHENTICATION
# ============================================================================

# API Keys for testing
VALID_API_KEYS = {
    "test-api-key-123": "admin",
    "test-api-key-456": "user",
    "test-api-key-789": "readonly"
}

# Bearer tokens for testing
VALID_TOKENS = {
    "bearer-token-admin": {"user_id": 1, "role": "admin", "expires": time.time() + 3600},
    "bearer-token-user": {"user_id": 2, "role": "user", "expires": time.time() + 3600},
    "bearer-token-readonly": {"user_id": 3, "role": "readonly", "expires": time.time() + 3600},
}

# Basic auth credentials
VALID_CREDENTIALS = {
    "admin": "admin123",
    "user": "user123",
    "readonly": "readonly123"
}

# Security schemes
bearer_scheme = HTTPBearer()
basic_scheme = HTTPBasic()
api_key_header = APIKeyHeader(name="X-API-Key")
api_key_query = APIKeyQuery(name="api_key")


def verify_api_key_header(api_key: str = Depends(api_key_header)):
    if api_key not in VALID_API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return {"api_key": api_key, "role": VALID_API_KEYS[api_key]}


def verify_api_key_query(api_key: str = Depends(api_key_query)):
    if api_key not in VALID_API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return {"api_key": api_key, "role": VALID_API_KEYS[api_key]}


def verify_bearer_token(token: str = Depends(bearer_scheme)):
    token_value = token.credentials
    if token_value not in VALID_TOKENS:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    token_data = VALID_TOKENS[token_value]
    if time.time() > token_data["expires"]:
        raise HTTPException(status_code=401, detail="Token expired")
    
    return token_data


def verify_basic_auth(credentials: HTTPBasicCredentials = Depends(basic_scheme)):
    if credentials.username not in VALID_CREDENTIALS:
        raise HTTPException(status_code=401, detail="Invalid username")
    
    if credentials.password != VALID_CREDENTIALS[credentials.username]:
        raise HTTPException(status_code=401, detail="Invalid password")
    
    return {"username": credentials.username, "role": credentials.username}


def verify_custom_auth(request: Request):
    # Custom authentication via custom header
    custom_token = request.headers.get("X-Custom-Token")
    if not custom_token:
        raise HTTPException(status_code=401, detail="Missing custom token")
    
    if custom_token != "custom-token-123":
        raise HTTPException(status_code=401, detail="Invalid custom token")
    
    return {"custom_token": custom_token, "role": "custom"}


# ============================================================================
# RATE LIMITING
# ============================================================================

def check_rate_limit(request: Request, limit: int = 10, window: int = 60):
    """Simple rate limiting implementation"""
    client_ip = request.client.host
    current_time = time.time()
    
    # Clean old entries
    if client_ip in db.rate_limits:
        db.rate_limits[client_ip] = [
            timestamp for timestamp in db.rate_limits[client_ip]
            if current_time - timestamp < window
        ]
    else:
        db.rate_limits[client_ip] = []
    
    # Check if limit exceeded
    if len(db.rate_limits[client_ip]) >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Maximum {limit} requests per {window} seconds."
        )
    
    # Add current request
    db.rate_limits[client_ip].append(current_time)


# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

app = FastAPI(
    title="Test HTTP Server",
    description="A comprehensive test server for HTTP tool testing",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]
)


# ============================================================================
# HEALTH AND INFO ENDPOINTS
# ============================================================================

@app.get("/", response_model=ApiResponse)
async def root():
    """Root endpoint with server information"""
    return ApiResponse(
        success=True,
        message="Test HTTP Server is running",
        data={
            "server": "Test HTTP Server",
            "version": "1.0.0",
            "endpoints": {
                "health": "/health",
                "docs": "/docs",
                "openapi": "/openapi.json",
                "users": "/users",
                "products": "/products",
                "orders": "/orders"
            },
            "authentication": {
                "bearer": "Authorization: Bearer <token>",
                "api_key_header": "X-API-Key: <key>",
                "api_key_query": "?api_key=<key>",
                "basic": "Authorization: Basic <base64>",
                "custom": "X-Custom-Token: <token>"
            }
        }
    )


@app.get("/health", response_model=ApiResponse)
async def health_check():
    """Health check endpoint"""
    return ApiResponse(
        success=True,
        message="Server is healthy",
        data={
            "status": "healthy",
            "timestamp": datetime.now(),
            "uptime": "running",
            "database": "connected",
            "memory_usage": "normal"
        }
    )


@app.get("/info", response_model=ApiResponse)
async def server_info():
    """Detailed server information"""
    return ApiResponse(
        success=True,
        message="Server information",
        data={
            "server": "Test HTTP Server",
            "version": "1.0.0",
            "python_version": "3.10+",
            "fastapi_version": "0.104.0+",
            "features": [
                "Multiple authentication methods",
                "Rate limiting",
                "WebSocket support",
                "File upload/download",
                "Complex data models",
                "Error handling",
                "CORS support"
            ],
            "endpoints_count": 25,
            "authentication_methods": 5
        }
    )


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@app.post("/auth/login", response_model=ApiResponse)
async def login(username: str, password: str):
    """Login endpoint to get bearer token"""
    if username not in VALID_CREDENTIALS:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if VALID_CREDENTIALS[username] != password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Generate token
    token = f"bearer-token-{username}"
    session_id = str(uuid.uuid4())
    
    db.sessions[session_id] = {
        "user_id": 1 if username == "admin" else 2 if username == "user" else 3,
        "username": username,
        "role": username,
        "created_at": datetime.now(),
        "expires_at": datetime.now() + timedelta(hours=1)
    }
    
    return ApiResponse(
        success=True,
        message="Login successful",
        data={
            "token": token,
            "session_id": session_id,
            "expires_in": 3600,
            "user": {
                "username": username,
                "role": username
            }
        }
    )


@app.post("/auth/logout", response_model=ApiResponse)
async def logout(session_id: str):
    """Logout endpoint"""
    if session_id in db.sessions:
        del db.sessions[session_id]
        return ApiResponse(success=True, message="Logout successful")
    else:
        raise HTTPException(status_code=404, detail="Session not found")


@app.get("/auth/me", response_model=ApiResponse)
async def get_current_user(auth_data: dict = Depends(verify_bearer_token)):
    """Get current user information"""
    user_id = auth_data["user_id"]
    user = db.users.get(user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return ApiResponse(
        success=True,
        message="User information retrieved",
        data=user.dict()
    )


# ============================================================================
# USER ENDPOINTS
# ============================================================================

@app.get("/users", response_model=ApiResponse)
async def get_users(
    skip: int = 0,
    limit: int = 10,
    search: Optional[str] = None,
    auth_data: dict = Depends(verify_api_key_header)
):
    """Get all users with pagination and search"""
    users = list(db.users.values())
    
    if search:
        users = [u for u in users if search.lower() in u.username.lower() or search.lower() in u.full_name.lower()]
    
    total = len(users)
    users = users[skip:skip + limit]
    
    return ApiResponse(
        success=True,
        message=f"Retrieved {len(users)} users",
        data={
            "users": [user.dict() for user in users],
            "pagination": {
                "skip": skip,
                "limit": limit,
                "total": total,
                "has_more": skip + limit < total
            }
        }
    )


@app.get("/users/{user_id}", response_model=ApiResponse)
async def get_user(user_id: int, auth_data: dict = Depends(verify_bearer_token)):
    """Get user by ID"""
    user = db.users.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return ApiResponse(
        success=True,
        message="User retrieved successfully",
        data=user.dict()
    )


@app.post("/users", response_model=ApiResponse)
async def create_user(
    user_data: UserCreate,
    auth_data: dict = Depends(verify_basic_auth),
    request: Request = None
):
    """Create a new user"""
    # Check rate limit
    check_rate_limit(request, limit=5, window=60)
    
    # Check if username already exists
    for user in db.users.values():
        if user.username == user_data.username:
            raise HTTPException(status_code=400, detail="Username already exists")
    
    # Create new user
    new_id = max(db.users.keys()) + 1 if db.users else 1
    new_user = User(
        id=new_id,
        username=user_data.username,
        email=user_data.email,
        full_name=user_data.full_name,
        created_at=datetime.now()
    )
    
    db.users[new_id] = new_user
    
    return ApiResponse(
        success=True,
        message="User created successfully",
        data=new_user.dict()
    )


@app.put("/users/{user_id}", response_model=ApiResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    auth_data: dict = Depends(verify_bearer_token)
):
    """Update user by ID"""
    user = db.users.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update fields
    update_data = user_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    
    user.last_login = datetime.now()
    
    return ApiResponse(
        success=True,
        message="User updated successfully",
        data=user.dict()
    )


@app.delete("/users/{user_id}", response_model=ApiResponse)
async def delete_user(
    user_id: int,
    auth_data: dict = Depends(verify_bearer_token)
):
    """Delete user by ID"""
    if user_id not in db.users:
        raise HTTPException(status_code=404, detail="User not found")
    
    del db.users[user_id]
    
    return ApiResponse(
        success=True,
        message="User deleted successfully"
    )


# ============================================================================
# PRODUCT ENDPOINTS
# ============================================================================

@app.get("/products", response_model=ApiResponse)
async def get_products(
    category: Optional[str] = None,
    in_stock: Optional[bool] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    tags: Optional[str] = None,
    auth_data: dict = Depends(verify_api_key_query)
):
    """Get products with filtering"""
    products = list(db.products.values())
    
    # Apply filters
    if category:
        products = [p for p in products if p.category.lower() == category.lower()]
    
    if in_stock is not None:
        products = [p for p in products if p.in_stock == in_stock]
    
    if min_price is not None:
        products = [p for p in products if p.price >= min_price]
    
    if max_price is not None:
        products = [p for p in products if p.price <= max_price]
    
    if tags:
        tag_list = [tag.strip() for tag in tags.split(",")]
        products = [p for p in products if any(tag in p.tags for tag in tag_list)]
    
    return ApiResponse(
        success=True,
        message=f"Retrieved {len(products)} products",
        data=[product.dict() for product in products]
    )


@app.get("/products/{product_id}", response_model=ApiResponse)
async def get_product(product_id: int, auth_data: dict = Depends(verify_custom_auth)):
    """Get product by ID"""
    product = db.products.get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    return ApiResponse(
        success=True,
        message="Product retrieved successfully",
        data=product.dict()
    )


@app.post("/products", response_model=ApiResponse)
async def create_product(
    product_data: ProductCreate,
    auth_data: dict = Depends(verify_bearer_token)
):
    """Create a new product"""
    new_id = max(db.products.keys()) + 1 if db.products else 1
    new_product = Product(
        id=new_id,
        name=product_data.name,
        description=product_data.description,
        price=product_data.price,
        category=product_data.category,
        in_stock=product_data.in_stock,
        tags=product_data.tags,
        metadata=product_data.metadata
    )
    
    db.products[new_id] = new_product
    
    return ApiResponse(
        success=True,
        message="Product created successfully",
        data=new_product.dict()
    )


@app.patch("/products/{product_id}", response_model=ApiResponse)
async def update_product(
    product_id: int,
    product_data: dict,
    auth_data: dict = Depends(verify_bearer_token)
):
    """Partially update product"""
    product = db.products.get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Update fields
    for field, value in product_data.items():
        if hasattr(product, field):
            setattr(product, field, value)
    
    return ApiResponse(
        success=True,
        message="Product updated successfully",
        data=product.dict()
    )


# ============================================================================
# COMPLEX ENDPOINTS
# ============================================================================

@app.post("/orders", response_model=ApiResponse)
async def create_order(
    user_id: int,
    products: List[Dict[str, Any]],
    auth_data: dict = Depends(verify_bearer_token)
):
    """Create a new order"""
    # Validate user exists
    if user_id not in db.users:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Validate products
    total_amount = 0
    for product_info in products:
        product_id = product_info.get("product_id")
        quantity = product_info.get("quantity", 1)
        
        if product_id not in db.products:
            raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
        
        product = db.products[product_id]
        if not product.in_stock:
            raise HTTPException(status_code=400, detail=f"Product {product_id} is out of stock")
        
        total_amount += product.price * quantity
    
    # Create order
    order_id = max(db.orders.keys()) + 1 if db.orders else 1
    order = Order(
        id=order_id,
        user_id=user_id,
        products=products,
        total_amount=total_amount,
        status="pending",
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    db.orders[order_id] = order
    
    return ApiResponse(
        success=True,
        message="Order created successfully",
        data=order.dict()
    )


@app.get("/search", response_model=ApiResponse)
async def search(
    q: str,
    type: str = "all",
    limit: int = 10,
    auth_data: dict = Depends(verify_api_key_header)
):
    """Complex search endpoint"""
    results = {"users": [], "products": [], "orders": []}
    
    if type in ["all", "users"]:
        for user in db.users.values():
            if q.lower() in user.username.lower() or q.lower() in user.full_name.lower():
                results["users"].append(user.dict())
    
    if type in ["all", "products"]:
        for product in db.products.values():
            if (q.lower() in product.name.lower() or 
                q.lower() in product.description.lower() or
                any(q.lower() in tag.lower() for tag in product.tags)):
                results["products"].append(product.dict())
    
    if type in ["all", "orders"]:
        for order in db.orders.values():
            if str(order.id) == q or str(order.user_id) == q:
                results["orders"].append(order.dict())
    
    # Limit results
    for key in results:
        results[key] = results[key][:limit]
    
    return ApiResponse(
        success=True,
        message=f"Search completed for '{q}'",
        data=results
    )


# ============================================================================
# ERROR TESTING ENDPOINTS
# ============================================================================

@app.get("/errors/400")
async def error_400():
    """Test 400 Bad Request error"""
    raise HTTPException(status_code=400, detail="This is a test 400 error")


@app.get("/errors/401")
async def error_401():
    """Test 401 Unauthorized error"""
    raise HTTPException(status_code=401, detail="This is a test 401 error")


@app.get("/errors/403")
async def error_403():
    """Test 403 Forbidden error"""
    raise HTTPException(status_code=403, detail="This is a test 403 error")


@app.get("/errors/404")
async def error_404():
    """Test 404 Not Found error"""
    raise HTTPException(status_code=404, detail="This is a test 404 error")


@app.get("/errors/429")
async def error_429():
    """Test 429 Too Many Requests error"""
    raise HTTPException(status_code=429, detail="This is a test 429 error")


@app.get("/errors/500")
async def error_500():
    """Test 500 Internal Server Error"""
    raise HTTPException(status_code=500, detail="This is a test 500 error")


# ============================================================================
# WEBSOCKET ENDPOINTS
# ============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time communication"""
    await websocket.accept()
    
    try:
        while True:
            # Wait for message from client
            data = await websocket.receive_text()
            
            # Echo back with timestamp
            response = {
                "message": f"Echo: {data}",
                "timestamp": datetime.now().isoformat(),
                "server": "Test HTTP Server"
            }
            
            await websocket.send_text(json.dumps(response))
            
    except WebSocketDisconnect:
        print("WebSocket disconnected")


# ============================================================================
# FILE ENDPOINTS
# ============================================================================

@app.post("/upload")
async def upload_file(file: bytes = None, filename: str = "test.txt"):
    """File upload endpoint"""
    if not file:
        raise HTTPException(status_code=400, detail="No file provided")
    
    # Save file (in real implementation)
    file_size = len(file)
    file_hash = hashlib.md5(file).hexdigest()
    
    return ApiResponse(
        success=True,
        message="File uploaded successfully",
        data={
            "filename": filename,
            "size": file_size,
            "hash": file_hash,
            "uploaded_at": datetime.now().isoformat()
        }
    )


@app.get("/download/{filename}")
async def download_file(filename: str):
    """File download endpoint"""
    # Create a simple test file
    content = f"This is a test file: {filename}\nGenerated at: {datetime.now()}\n"
    
    return Response(
        content=content,
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point for the test server"""
    print("🚀 Starting Test HTTP Server...")
    print("📊 Server: http://localhost:8002")
    print("📚 Docs: http://localhost:8002/docs")
    print("🔧 OpenAPI: http://localhost:8002/openapi.json")
    print("=" * 60)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8002,
        log_level="info"
    )


if __name__ == "__main__":
    main()
