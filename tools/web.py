import os
from typing import Literal
from dotenv import load_dotenv
load_dotenv()

from tavily import TavilyClient
from deepagents import create_deep_agent

api_key = os.getenv("TAVILY_API_KEY")
tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

def internet_search(
    query: str,
    max_results: int = 3,
    # topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = False,
):
    """Run a web search"""

    print("\nWeb search called.....\n")
    search = tavily_client.search(
        query,
        max_results=max_results,
        include_raw_content=include_raw_content,
        # topic=topic,
    )
    print("\nWeb search completed !\n")
    
    return search

if __name__ == "__main__":
    out = internet_search("Bagels", 1, False)
    print(out)