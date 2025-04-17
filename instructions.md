# MCP Server Query Functions

This document outlines the two main ways to execute queries through the MCP server.

## 1. Execute a New Query

Use this endpoint to run a new SQL query directly.

### Endpoint
```
POST /ask
```

### Request Format
```json
{
    "question": "Natural language description of the query (optional)",
    "sql_query": "Your SQL query here"
}
```

### Example
```bash
curl -X POST "http://localhost:8000/ask" \
     -H "Content-Type: application/json" \
     -d '{
         "question": "Show me Mexican members start dates",
         "sql_query": "SELECT DISTINCT ID, VALID_START FROM INTL_EOR.MEMBERS WHERE WORK_COUNTRY = '\''MX'\'' ORDER BY VALID_START DESC"
     }'
```

### Response Format
```json
{
    "answer": "Here are the results from your query",
    "sql_query": "The executed SQL query",
    "data": {
        "id": "Query result ID",
        "query": "The executed SQL query",
        "data": {
            "columns": [
                {"name": "Column1", "friendly_name": "Column1", "type": "string"},
                {"name": "Column2", "friendly_name": "Column2", "type": "datetime"}
            ],
            "rows": [
                {"Column1": "value1", "Column2": "2024-01-01T00:00:00"}
            ]
        },
        "data_source_id": 6,
        "runtime": 2.1664481163024902,
        "retrieved_at": "2025-04-17T14:24:52.903Z"
    }
}
```

## 2. Execute a Predefined Query

Use this endpoint to run a query that has been previously saved in Redash.

### Endpoint
```
POST /ask/predefined/{query_id}
```

### Request Format
```json
{
    "parameters": {
        "param1": "value1",
        "param2": "value2"
    }
}
```

### Example
```bash
curl -X POST "http://localhost:8000/ask/predefined/13273" \
     -H "Content-Type: application/json" \
     -d '{
         "parameters": {
             "query": "SELECT DISTINCT ID, VALID_START FROM INTL_EOR.MEMBERS WHERE WORK_COUNTRY = '\''MX'\'' ORDER BY VALID_START DESC"
         }
     }'
```

### Response Format
Same as the new query response format.

## Notes

1. **Query Parameters**:
   - For predefined queries, parameters are optional
   - The `question` field in new queries is optional
   - The `sql_query` field is required for new queries

2. **Error Handling**:
   - Both endpoints return appropriate HTTP status codes
   - Error messages are included in the response detail

3. **Authentication**:
   - Ensure the server has the correct Redash API key and base URL configured
   - These are set in the `.env` file

4. **Best Practices**:
   - Use predefined queries for frequently used queries
   - Use new queries for one-off or exploratory queries
   - Always include proper error handling in your client code
