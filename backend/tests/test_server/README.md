# Test HTTP Server

A comprehensive test HTTP server designed for testing HTTP tool functionality with various authentication methods, request types, and response patterns.

## Features

- **Multiple HTTP Methods**: GET, POST, PUT, PATCH, DELETE
- **Authentication Types**: Bearer Token, API Key (Header/Query), Basic Auth, Custom Auth
- **Complex Endpoints**: Search, filtering, pagination, file operations
- **Error Testing**: Various HTTP error codes (400, 401, 403, 404, 429, 500)
- **WebSocket Support**: Real-time communication testing
- **Rate Limiting**: Built-in rate limiting simulation
- **File Operations**: Upload and download endpoints
- **OpenAPI Specification**: Complete API documentation
- **Postman Collection**: Ready-to-use API collection

## Quick Start

### Start the Server

```bash
# Using uv run
uv run start_test_server

# Using uvx
uvx vmcp start_test_server

# Direct execution
cd test_server
python test_http_server.py
```

The server will start on `http://localhost:8002`

### Access Documentation

- **API Docs**: http://localhost:8002/docs
- **ReDoc**: http://localhost:8002/redoc
- **OpenAPI JSON**: http://localhost:8002/openapi.json

## Authentication Methods

### 1. Bearer Token
```bash
Authorization: Bearer bearer-token-admin
Authorization: Bearer bearer-token-user
Authorization: Bearer bearer-token-readonly
```

### 2. API Key (Header)
```bash
X-API-Key: test-api-key-123
X-API-Key: test-api-key-456
X-API-Key: test-api-key-789
```

### 3. API Key (Query Parameter)
```bash
?api_key=test-api-key-123
?api_key=test-api-key-456
?api_key=test-api-key-789
```

### 4. Basic Authentication
```bash
Username: admin, Password: admin123
Username: user, Password: user123
Username: readonly, Password: readonly123
```

### 5. Custom Authentication
```bash
X-Custom-Token: custom-token-123
```

## API Endpoints

### Health & Info
- `GET /` - Root endpoint with server information
- `GET /health` - Health check
- `GET /info` - Detailed server information

### Authentication
- `POST /auth/login` - Login to get bearer token
- `GET /auth/me` - Get current user (requires Bearer token)
- `POST /auth/logout` - Logout

### Users
- `GET /users` - Get all users (requires API key)
- `GET /users/{id}` - Get user by ID (requires Bearer token)
- `POST /users` - Create user (requires Basic auth)
- `PUT /users/{id}` - Update user (requires Bearer token)
- `DELETE /users/{id}` - Delete user (requires Bearer token)

### Products
- `GET /products` - Get products with filtering (requires API key query)
- `GET /products/{id}` - Get product by ID (requires Custom auth)
- `POST /products` - Create product (requires Bearer token)
- `PATCH /products/{id}` - Update product (requires Bearer token)

### Orders & Search
- `POST /orders` - Create order (requires Bearer token)
- `GET /search` - Complex search (requires API key)

### Error Testing
- `GET /errors/400` - Test 400 Bad Request
- `GET /errors/401` - Test 401 Unauthorized
- `GET /errors/403` - Test 403 Forbidden
- `GET /errors/404` - Test 404 Not Found
- `GET /errors/429` - Test 429 Too Many Requests
- `GET /errors/500` - Test 500 Internal Server Error

### File Operations
- `POST /upload` - Upload file
- `GET /download/{filename}` - Download file

### WebSocket
- `WS /ws` - WebSocket endpoint

## Test Data

The server comes with pre-populated test data:

### Users
- **admin** (ID: 1) - Admin user with full access
- **john_doe** (ID: 2) - Regular user
- **jane_smith** (ID: 3) - Regular user

### Products
- **Laptop** (ID: 1) - Electronics, $999.99, in stock
- **Mouse** (ID: 2) - Electronics, $29.99, in stock
- **Book** (ID: 3) - Books, $49.99, out of stock

## Testing with HTTP Tools

This server is designed to test HTTP tool functionality. Here are some example configurations:

### Simple GET Request
```json
{
  "name": "health_check",
  "api_config": {
    "url": "http://localhost:8002/health",
    "method": "GET"
  }
}
```

### Bearer Token Authentication
```json
{
  "name": "get_current_user",
  "api_config": {
    "url": "http://localhost:8002/auth/me",
    "method": "GET",
    "auth": {
      "type": "bearer",
      "token": "bearer-token-admin"
    }
  }
}
```

### API Key Authentication
```json
{
  "name": "get_users",
  "api_config": {
    "url": "http://localhost:8002/users",
    "method": "GET",
    "auth": {
      "type": "apikey",
      "apiKey": "test-api-key-123",
      "keyName": "X-API-Key"
    }
  }
}
```

### POST with JSON Body
```json
{
  "name": "create_product",
  "api_config": {
    "url": "http://localhost:8002/products",
    "method": "POST",
    "auth": {
      "type": "bearer",
      "token": "bearer-token-admin"
    },
    "headers": {
      "Content-Type": "application/json"
    },
    "body_parsed": {
      "name": "Test Product",
      "description": "A test product",
      "price": 99.99,
      "category": "Test",
      "in_stock": true
    }
  }
}
```

## Running Tests

The server includes comprehensive integration tests:

```bash
# Run all tests
uv run pytest test_server/test_http_tool_integration.py

# Run specific test categories
uv run pytest test_server/test_http_tool_integration.py::TestHTTPToolIntegration
uv run pytest test_server/test_http_tool_integration.py::TestHTTPToolVariableSubstitution

# Run integration tests (requires server to be running)
uv run pytest test_server/test_http_tool_integration.py -m integration
```

## Files

- `test_http_server.py` - Main server implementation
- `generate_openapi.py` - Script to generate OpenAPI specification
- `openapi.json` - Generated OpenAPI specification
- `postman_collection.json` - Postman collection for API testing
- `test_http_tool_integration.py` - Comprehensive integration tests
- `README.md` - This documentation

## Development

To modify the server:

1. Edit `test_http_server.py`
2. Regenerate OpenAPI spec: `python generate_openapi.py`
3. Update Postman collection if needed
4. Run tests to verify changes

## Integration with HTTP Tool Engine

This server is specifically designed to test the HTTP tool engine functionality in the vMCP system. It provides:

- All authentication methods supported by the HTTP tool engine
- Complex request/response patterns
- Error scenarios for robust testing
- Variable substitution testing
- File upload/download testing
- WebSocket support for advanced testing

The server runs on port 8002 to avoid conflicts with other services and provides comprehensive logging for debugging HTTP tool interactions.
