from buspal_backend.services.ai.mcp.client import MCPClient
import json

with open('buspal_backend/config/mcp.json', 'r') as file:
    mcp_config = json.load(file)

class MCPManager:
    def __init__(self):
        self.mcps = []

    async def connect_servers(self):    
      for _, mcp_server in mcp_config.items():
        mcp_client = MCPClient()
        command = mcp_server.get("command", "")
        args = mcp_server.get("args", "")
        env = mcp_server.get("env", None)
        await mcp_client.connect_to_server(command, args, env)
        self.mcps.append(mcp_client)
      self.connected = True

    async def cleanup(self):
      """Clean up resources"""
      for mcp in self.mcps:
          await mcp.cleanup()
      self.mcps = []

mcp_manager = MCPManager()