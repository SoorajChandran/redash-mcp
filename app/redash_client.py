import os
import requests
from typing import Dict, Any, Optional, List
import time
import hashlib
import logging
import json
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Constants
QUERY_STATUS = {
    'COMPLETED': 3,
    'FAILED': 4
}

POLL_INTERVAL = 1  # seconds

class RedashClient:
    """
    A client for interacting with the Redash API.
    
    This client provides methods to:
    - List available data sources
    - Execute ad-hoc SQL queries
    - Execute predefined queries with parameters
    
    Attributes:
        base_url (str): The base URL of the Redash instance
        api_key (str): API key for authentication
        data_source_id (int): Default data source ID for queries
        headers (Dict[str, str]): HTTP headers for API requests
    """

    def __init__(self):
        """Initialize the RedashClient with configuration from environment variables."""
        self.base_url = os.getenv("REDASH_BASE_URL")
        self.api_key = os.getenv("REDASH_API_KEY")
        self.data_source_id = int(os.getenv("REDASH_DATA_SOURCE_ID", "6"))
        
        if not all([self.base_url, self.api_key]):
            raise ValueError("Missing required environment variables: REDASH_BASE_URL or REDASH_API_KEY")
        
        self.headers = {
            "Authorization": f"Key {self.api_key}",
            "Content-Type": "application/json"
        }
        logger.info(f"Initialized RedashClient with base_url: {self.base_url}")

    def list_data_sources(self) -> List[Dict[str, Any]]:
        """
        Retrieve all available data sources from Redash.
        
        Returns:
            List[Dict[str, Any]]: List of data source configurations
            
        Raises:
            requests.exceptions.RequestException: If the API request fails
        """
        url = f"{self.base_url}/api/data_sources"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def _get_query_hash(self, query: str) -> str:
        """
        Generate a unique MD5 hash for a query string.
        
        Args:
            query (str): SQL query string
            
        Returns:
            str: MD5 hash of the query
        """
        return hashlib.md5(query.encode()).hexdigest()

    def _poll_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Poll the status of a query job until completion or failure.
        
        Args:
            job_id (str): ID of the job to poll
            
        Returns:
            Dict[str, Any]: Job status data including result ID
            
        Raises:
            Exception: If the query execution fails
        """
        while True:
            job_status = requests.get(f"{self.base_url}/api/jobs/{job_id}", headers=self.headers)
            job_status.raise_for_status()
            status_data = job_status.json()
            logger.debug(f"Job status: {json.dumps(status_data, indent=2)}")
            
            status = status_data["job"]["status"]
            if status == QUERY_STATUS['COMPLETED']:
                return status_data["job"]
            elif status == QUERY_STATUS['FAILED']:
                error = status_data["job"].get("error", "Unknown error")
                raise Exception(f"Query execution failed: {error}")
            
            time.sleep(POLL_INTERVAL)

    def _format_query_result(self, result: Dict[str, Any], query: str) -> Dict[str, Any]:
        """
        Format the query result into a standardized structure.
        
        Args:
            result (Dict[str, Any]): Raw query result from Redash
            query (str): Original SQL query
            
        Returns:
            Dict[str, Any]: Formatted query result
            
        Raises:
            Exception: If the result format is invalid
        """
        # Handle both direct query_result and nested query_result cases
        query_result = result.get("query_result", result)
        if not query_result:
            raise Exception("No query result in response")
            
        return {
            "query_result": {
                "id": query_result.get("id"),
                "query": query or query_result.get("query", ""),
                "data": {
                    "columns": query_result.get("data", {}).get("columns", []),
                    "rows": query_result.get("data", {}).get("rows", [])
                },
                "data_source_id": query_result.get("data_source_id"),
                "runtime": query_result.get("runtime", 0),
                "retrieved_at": query_result.get("retrieved_at")
            }
        }

    def execute_query(self, query: str, data_source_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Execute an ad-hoc SQL query on Redash.
        
        Args:
            query (str): SQL query to execute
            data_source_id (Optional[int]): Data source ID to use, defaults to instance default
            
        Returns:
            Dict[str, Any]: Query results in standardized format
            
        Raises:
            Exception: If query creation or execution fails
        """
        data_source_id = data_source_id or self.data_source_id
        
        try:
            # Create new query
            query_data = {
                "query": query,
                "data_source_id": data_source_id,
                "name": f"MCP Query - {self._get_query_hash(query)[:8]}"
            }
            response = requests.post(f"{self.base_url}/api/queries", json=query_data, headers=self.headers)
            response.raise_for_status()
            query_id = response.json()["id"]
            logger.info(f"Created query ID: {query_id}")

            # Execute query
            job_response = requests.post(f"{self.base_url}/api/queries/{query_id}/results", headers=self.headers)
            job_response.raise_for_status()
            
            job_data = job_response.json()
            logger.info(f"Job response data: {json.dumps(job_data, indent=2)}")
            
            # Handle both immediate results and job-based results
            if "query_result" in job_data:
                # Query result is already available
                logger.info("Got immediate query result")
                return self._format_query_result(job_data, query)
            elif "job" in job_data:
                # Need to wait for job completion
                logger.info("Waiting for job completion")
                job_id = job_data["job"]["id"]
                logger.info(f"Started job ID: {job_id}")

                # Wait for completion
                job_result = self._poll_job_status(job_id)
                result_id = job_result["query_result_id"]

                # Fetch results
                result_response = requests.get(f"{self.base_url}/api/query_results/{result_id}", headers=self.headers)
                result_response.raise_for_status()
                result_data = result_response.json()
                logger.info(f"Result data: {json.dumps(result_data, indent=2)}")
                
                return self._format_query_result(result_data, query)
            else:
                raise Exception(f"Invalid response format. Keys: {list(job_data.keys())}")
            
        except Exception as e:
            logger.error(f"Error executing query: {str(e)}")
            raise

    def execute_predefined_query(self, query_id: int, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a predefined query with optional parameters.
        
        Args:
            query_id (int): ID of the predefined query
            parameters (Optional[Dict[str, Any]]): Parameters to pass to the query
            
        Returns:
            Dict[str, Any]: Query results in standardized format
            
        Raises:
            Exception: If query execution fails
        """
        try:
            # Execute query with parameters
            job_data = {"parameters": parameters} if parameters else {}
            job_response = requests.post(
                f"{self.base_url}/api/queries/{query_id}/results",
                json=job_data,
                headers=self.headers
            )
            job_response.raise_for_status()
            
            if "job" not in job_response.json():
                raise Exception(f"Invalid response format: {job_response.json()}")
                
            job_id = job_response.json()["job"]["id"]
            logger.info(f"Started job ID: {job_id}")

            # Wait for completion
            job_result = self._poll_job_status(job_id)
            result_id = job_result["query_result_id"]

            # Fetch results
            result_response = requests.get(f"{self.base_url}/api/query_results/{result_id}", headers=self.headers)
            result_response.raise_for_status()
            
            return self._format_query_result(result_response.json(), "")
            
        except Exception as e:
            logger.error(f"Error executing predefined query: {str(e)}")
            raise 