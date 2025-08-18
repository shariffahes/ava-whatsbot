from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from dotenv import load_dotenv


load_dotenv()

class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
    
    async def connect_to_server(self, command, args, env=None):
        """Connect to an MCP server

        Args:
            server_script_path: Path to the server script (.py or .js)
        """
 
        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=env
        )

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()
        print("\nConnected to server ")

    async def list_tools(self):
        return await self.session.list_tools() # type: ignore
  
    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()