"""Web scraping and search function implementations"""
import json
import os


# TODO: Need to cleanup content before returning
# def firecrawl_scrape(url: str) -> str:
#     """Scrape content from a website using Firecrawl
#     
#     Args:
#         url: The URL to scrape
#     
#     Returns:
#         JSON with scraped content or error
#     """
#     # Get API key from parameter or environment
#     key = os.getenv("FIRECRAWL_API_KEY")
#     
#     if not key:
#         return json.dumps({
#             "success": False,
#             "error": "No API key provided. Please set FIRECRAWL_API_KEY environment variable."
#         })
#     
#     try:
#         from firecrawl import Firecrawl
#         
#         app = Firecrawl(api_key=key)
#         result = app.scrape(url)
#         
#         return json.dumps({
#             "success": True,
#             "url": url,
#             "data": result
#         })
#     except ImportError:
#         return json.dumps({
#             "success": False,
#             "error": "firecrawl-py is not installed. Install with: pip install firecrawl-py"
#         })
#     except Exception as e:
#         return json.dumps({
#             "success": False,
#             "error": f"Firecrawl scrape failed: {str(e)}"
#         })


def firecrawl_search(query: str, limit: int = 5) -> str:
    """Search the web using Firecrawl
    
    Args:
        query: Search query
        limit: Maximum number of results (default: 5)
    
    Returns:
        JSON with search results or error
    """
    # Get API key from parameter or environment
    key = os.getenv("FIRECRAWL_API_KEY")
    
    if not key:
        return json.dumps({
            "success": False,
            "error": "No API key provided. Please set FIRECRAWL_API_KEY environment variable."
        })
    
    try:
        from firecrawl import Firecrawl
        
        app = Firecrawl(api_key=key)
        search_result = app.search(query, limit=limit)
        
        # Convert SearchData object to dict if needed
        if hasattr(search_result, 'model_dump'):
            search_data = search_result.model_dump()
        elif hasattr(search_result, 'dict'):
            search_data = search_result.dict()
        elif hasattr(search_result, '__dict__'):
            search_data = search_result.__dict__
        else:
            search_data = search_result
        
        return json.dumps({
            "success": True,
            "query": query,
            "limit": limit,
            "results": search_data
        })
    except ImportError:
        return json.dumps({
            "success": False,
            "error": "firecrawl-py is not installed. Install with: pip install firecrawl-py"
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Firecrawl search failed: {str(e)}"
        })


def tavily_search(query: str) -> str:
    """Search the web using Tavily
    
    Args:
        query: Search query
    
    Returns:
        JSON with search results or error
    """
    # Get API key from parameter or environment
    key = os.getenv("TAVILY_API_KEY")
    
    if not key:
        return json.dumps({
            "success": False,
            "error": "No API key provided. Please set TAVILY_API_KEY environment variable."
        })
    
    try:
        from tavily import TavilyClient
        
        tavily_client = TavilyClient(api_key=key)
        response = tavily_client.search(query)
        
        return json.dumps({
            "success": True,
            "query": query,
            "results": response
        })
    except ImportError:
        return json.dumps({
            "success": False,
            "error": "tavily-python is not installed. Install with: pip install tavily-python"
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Tavily search failed: {str(e)}"
        })


# TODO: Need to cleanup content before returning
# def tavily_extract(url: str) -> str:
#     """Extract content from a URL using Tavily
#     
#     Args:
#         url: The URL to extract content from
#     
#     Returns:
#         JSON with extracted content or error
#     """
#     # Get API key from parameter or environment
#     key = os.getenv("TAVILY_API_KEY")
#     
#     if not key:
#         return json.dumps({
#             "success": False,
#             "error": "No API key provided. Please set TAVILY_API_KEY environment variable."
#         })
#     
#     try:
#         from tavily import TavilyClient
#         
#         tavily_client = TavilyClient(api_key=key)
#         response = tavily_client.extract(url)
#         
#         return json.dumps({
#             "success": True,
#             "url": url,
#             "content": response
#         })
#     except ImportError:
#         return json.dumps({
#             "success": False,
#             "error": "tavily-python is not installed. Install with: pip install tavily-python"
#         })
#     except Exception as e:
#         return json.dumps({
#             "success": False,
#             "error": f"Tavily extract failed: {str(e)}"
#         })
