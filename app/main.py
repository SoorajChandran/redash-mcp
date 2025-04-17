from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import os
import logging
from dotenv import load_dotenv
from .redash_client import RedashClient

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize FastAPI app with metadata
app = FastAPI(
    title="MCP Server",
    description="""
    A conversational interface for Redash that allows:
    - Natural language queries to be converted to SQL
    - Direct SQL query execution
    - Predefined query execution with parameters
    """,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Initialize Redash client
try:
    redash_client = RedashClient()
except ValueError as e:
    logger.error(f"Failed to initialize RedashClient: {str(e)}")
    raise

class QueryRequest(BaseModel):
    """
    Request model for query execution.
    """
    question: str = Field(..., description="Natural language question or SQL query")
    sql_query: Optional[str] = Field(None, description="Direct SQL query to execute (optional)")

    class Config:
        schema_extra = {
            "example": {
                "question": "Show me the last 10 orders",
                "sql_query": "SELECT * FROM orders ORDER BY created_at DESC LIMIT 10"
            }
        }

class PredefinedQueryRequest(BaseModel):
    """
    Request model for predefined query execution.
    """
    parameters: Optional[Dict[str, Any]] = Field(
        None,
        description="Parameters to pass to the predefined query"
    )

    class Config:
        schema_extra = {
            "example": {
                "parameters": {
                    "start_date": "2024-01-01",
                    "end_date": "2024-12-31"
                }
            }
        }

class QueryResponse(BaseModel):
    """
    Response model for query results.
    """
    answer: str = Field(..., description="Human-readable response message")
    sql_query: Optional[str] = Field(None, description="Executed SQL query")
    data: Optional[Dict[str, Any]] = Field(None, description="Query results data")

@app.get("/", status_code=status.HTTP_200_OK)
async def root():
    """
    Root endpoint to check if the server is running.
    
    Returns:
        dict: Status message
    """
    return {
        "status": "ok",
        "message": "MCP Server is running",
        "version": app.version
    }

@app.get("/data-sources", status_code=status.HTTP_200_OK)
async def get_data_sources() -> Dict[str, List[Dict[str, Any]]]:
    """
    List all available Redash data sources.
    
    Returns:
        Dict[str, List[Dict[str, Any]]]: List of data sources and their configurations
        
    Raises:
        HTTPException: If there's an error fetching data sources
    """
    try:
        data_sources = redash_client.list_data_sources()
        return {"data_sources": data_sources}
    except Exception as e:
        logger.error(f"Error getting data sources: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch data sources: {str(e)}"
        )

@app.post("/ask", response_model=QueryResponse, status_code=status.HTTP_200_OK)
async def ask_question(request: QueryRequest) -> QueryResponse:
    """
    Execute a natural language question or direct SQL query.
    
    Args:
        request (QueryRequest): Query request containing question and optional SQL
        
    Returns:
        QueryResponse: Query results and metadata
        
    Raises:
        HTTPException: If query execution fails
    """
    try:
        # Use provided SQL or treat question as SQL (future: add NL->SQL conversion)
        sql_query = request.sql_query or request.question
        logger.info(f"Executing query: {sql_query}")
        
        # Execute query
        result = redash_client.execute_query(sql_query)
        logger.info("Query executed successfully")
        
        if not isinstance(result, dict) or "query_result" not in result:
            raise ValueError("Invalid response format from Redash")
        
        return QueryResponse(
            answer="Here are the results from your query",
            sql_query=sql_query,
            data=result["query_result"]
        )
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query execution failed: {str(e)}"
        )

@app.post(
    "/ask/predefined/{query_id}",
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK
)
async def ask_predefined_question(
    query_id: int,
    request: PredefinedQueryRequest
) -> QueryResponse:
    """
    Execute a predefined query with optional parameters.
    
    Args:
        query_id (int): ID of the predefined query in Redash
        request (PredefinedQueryRequest): Optional parameters for the query
        
    Returns:
        QueryResponse: Query results and metadata
        
    Raises:
        HTTPException: If query execution fails
    """
    try:
        # Execute predefined query
        result = redash_client.execute_predefined_query(query_id, request.parameters)
        logger.info(f"Executed predefined query {query_id}")
        
        # Extract query result data
        query_result = result.get("query_result", {})
        if not query_result:
            raise ValueError("No query result in response")
        
        return QueryResponse(
            answer="Here are the results from your query",
            sql_query=query_result.get("query", ""),
            data=query_result
        )
    except Exception as e:
        logger.error(f"Error processing predefined query: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        ) 