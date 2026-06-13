# API Conventions

## Local API Design
Since this is a local-first system, APIs are internal service boundaries rather than remote endpoints.

### Naming
- Use RESTful naming for any HTTP-based local services
- Endpoints use plural nouns: `/api/notes`, `/api/tasks`
- Use kebab-case for multi-word resources: `/api/knowledge-graphs`

### Request/Response Format
- Always use JSON for request and response bodies
- Include a `status` field in all responses: `"success"` or `"error"`
- Use ISO 8601 for all date/time fields
- Include pagination for list endpoints: `{ page, limit, total, data }`

### Error Handling
- Return structured error objects:
  ```json
  {
    "status": "error",
    "code": "NOT_FOUND",
    "message": "Resource not found",
    "details": {}
  }
  ```
- Use meaningful error codes, not just HTTP status numbers
- Never expose stack traces in production responses

### Versioning
- Prefix API routes with version: `/api/v1/...`
- Support at least one previous version during migration

### Security
- All local APIs bind to `127.0.0.1` only (no external exposure)
- Validate and sanitize all inputs even for local services
- Use CORS headers even locally for browser-based clients

### Data Contracts
- Define TypeScript interfaces for all API payloads
- Keep request/response types in a shared `types/` directory
- Document all endpoints with JSDoc or OpenAPI spec
