import os
from langchain_openai import ChatOpenAI
import openai
from typing import Literal
from langchain_ollama import ChatOllama
from tavily import TavilyClient
from deepagents import create_deep_agent
from tools.web import internet_search
from dotenv import load_dotenv
load_dotenv()

# System prompt to steer the agent to be an expert researcher
research_instructions = """You are an expert researcher. Your job is to conduct thorough research and then write a polished report.

You have access to an internet search tool as your primary means of gathering information.

## `internet_search`

Use this to run an internet search for a given query. You can specify the max number of results to return, the topic, and whether raw content should be included.
"""


## Initialize model

from langchain_ollama import ChatOllama

# llm = ChatOllama(
#     model="qwen3.5:9b",
#     validate_model_on_init=True,
#     temperature=0.8,
#     num_predict=-1,
#     reasoning=False
#     # other params ...
# )

llm = ChatOpenAI(
    base_url = os.getenv("CAMPUSAI_API_URL"),
    model = os.getenv("CAMPUSAI_MODEL"),
    api_key = os.getenv("CAMPUSAI_API_KEY")
)

agent = create_deep_agent(
    model=llm,
    tools=[internet_search],
    system_prompt=research_instructions,
    memory=["./AGENTS.md"],
    skills=["./skills/"],
)

result = agent.invoke({"messages": [{"role": "user", "content": "What are the 3 most famous tourist spots in Denmark ??"}]})

# Print the agent's response

print("\nFull response:\n", result)

print("\nOUTPUT\n")
print(result["messages"][-1].content)