from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Math")

@mcp.tool
def add(a: int, b: int) -> int:
    """Adds two numbers"""
    return a + b


@mcp.tool
def subtract(a: int, b: int) -> int:
    """Subtracts two numbers"""
    return a - b


@mcp.tool
def multiply(a: int, b: int) -> int:
    """Multiplies two numbers"""
    return a * b


@mcp.tool
def divide(a: int, b: int) -> int:
    """Divides two numbers"""
    return a / b