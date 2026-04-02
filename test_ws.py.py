import asyncio
import websockets
import json

# Make sure this matches your CURRENT active ngrok URL!
WS_URL = "wss://3ed0-178-209-155-47.ngrok-free.app/ws/TestUser"

async def test_connection():
    headers = {
        "ngrok-skip-browser-warning": "true",
        "User-Agent": "Mozilla/5.0"
    }
    
    print(f"Attempting to connect to: {WS_URL}...")
    try:
        async with websockets.connect(WS_URL, additional_headers=headers) as ws:
            print("🟢 SUCCESS! WebSocket is connected to Ngrok.")
            
            # Try sending a test ping
            await ws.send(json.dumps({"type": "ping", "content": "Hello Server!"}))
            print("🟢 SUCCESS! Message sent through the tunnel.")
            
    except Exception as e:
        print(f"🔴 FAILED TO CONNECT! Error details: {e}")

asyncio.run(test_connection())