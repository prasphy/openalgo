"""
OpenAlgo WebSocket Market Depth Example
"""

from openalgo import api
import time

# Initialize feed client with explicit parameters
client = api(
    api_key="14ec9b904ad5ff8e15769510881ebed4f4add0c74e5c046dda690582cf49e906",  # Replace with your API key
    host="http://127.0.0.1:5000",  # Replace with your API host
    ws_url="ws://127.0.0.1:8765"  # Explicit WebSocket URL (can be different from REST API host)
)

# MCX instruments for testing
instruments_list = [

    {"exchange": "NSE", "symbol": "NIFTY"}
]

def on_data_received(data):
    print("Market Depth Update:")
    print(data)

# Connect and subscribe
client.connect()
client.subscribe_depth(instruments_list, on_data_received=on_data_received)

# Poll Market Depth data a few times
for i in range(100):
    print(f"\nPoll {i+1}:")
    print(client.get_depth())
    time.sleep(0.5)

# Cleanup
client.unsubscribe_depth(instruments_list)
client.disconnect()