import httpx
import json
import os
import pandas as pd
from datetime import datetime, timedelta
import urllib.parse
from database.token_db import get_token, get_br_symbol, get_oa_symbol
from utils.httpx_client import get_httpx_client
from utils.logging import get_logger

logger = get_logger(__name__)


def get_api_response(endpoint, auth, method="POST", payload=None):
    """
    Common function to make API calls to Flattrade using httpx with connection pooling
    """
    AUTH_TOKEN = auth
    full_api_key = os.getenv('BROKER_API_KEY')
    api_key = full_api_key.split(':::')[0]

    if payload is None:
        data = {
            "uid": api_key,
            "actid": api_key
        }
    else:
        data = payload
        data["uid"] = api_key
        data["actid"] = api_key

    payload_str = "jData=" + json.dumps(data) + "&jKey=" + AUTH_TOKEN

    # Get the shared httpx client
    client = get_httpx_client()
    
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    url = f"https://piconnect.flattrade.in{endpoint}"

    response = client.request(method, url, content=payload_str, headers=headers)
    data = response.text
    
    # Print raw response for debugging
    logger.info(f"Raw Response: {data}")
    
    try:
        return json.loads(data)
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON: {e}")
        logger.info(f"Response data: {data}")
        raise

class BrokerData:
    def __init__(self, auth_token):
        """Initialize Flattrade data handler with authentication token"""
        self.auth_token = auth_token
        # Map common timeframe format to Flattrade resolutions
        self.timeframe_map = {
            # Minutes
            '1m': '1',    # 1 minute
            '3m': '3',    # 3 minutes
            '5m': '5',    # 5 minutes
            '10m': '10',  # 10 minutes
            '15m': '15',  # 15 minutes
            '30m': '30',  # 30 minutes
            # Hours
            '1h': '60',   # 1 hour (60 minutes)
            '2h': '120',  # 2 hours (120 minutes)
            # Daily
            'D': 'D'      # Daily data
        }

    def get_quotes(self, symbol: str, exchange: str) -> dict:
        """
        Get real-time quotes for given symbol
        Args:
            symbol: Trading symbol
            exchange: Exchange (e.g., NSE, BSE)
        Returns:
            dict: Simplified quote data with required fields including OI
        """
        try:
            # Convert symbol to broker format and get token
            br_symbol = get_br_symbol(symbol, exchange)
            token = get_token(symbol, exchange)

            if(exchange=="NSE_INDEX"):
                exchange="NSE"  
            elif(exchange=="BSE_INDEX"):
                exchange="BSE"

            payload = {
                "uid": os.getenv('BROKER_API_KEY').split(':::')[0],
                "exch": exchange,
                "token": token
            }
                
            response = get_api_response("/PiConnectTP/GetQuotes", self.auth_token, payload=payload)
                
            if response.get('stat') != 'Ok':
                raise Exception(f"Error from Flattrade API: {response.get('emsg', 'Unknown error')}")
            
            # Return simplified quote data as dict (not list) - NOW INCLUDING OI
            return {
                'bid': float(response.get('bp1', 0)),
                'ask': float(response.get('sp1', 0)), 
                'open': float(response.get('o', 0)),
                'high': float(response.get('h', 0)),
                'low': float(response.get('l', 0)),
                'ltp': float(response.get('lp', 0)),
                'prev_close': float(response.get('c', 0)) if 'c' in response else 0,
                'volume': int(float(response.get('v', 0))),
                'oi': int(response.get('oi', 0))  # 🔥 ADDED OPEN INTEREST
            }
            
        except Exception as e:
            raise Exception(f"Error fetching quotes: {str(e)}")


    def get_depth(self, symbol: str, exchange: str) -> dict:
        """
        Get market depth for given symbol
        Args:
            symbol: Trading symbol
            exchange: Exchange (e.g., NSE, BSE)
        Returns:
            dict: Market depth data with bids, asks and other details
        """
        try:
            # Convert symbol to broker format and get token
            br_symbol = get_br_symbol(symbol, exchange)
            token = get_token(symbol, exchange)

            if(exchange=="NSE_INDEX"):
                exchange="NSE"  
            elif(exchange=="BSE_INDEX"):
                exchange="BSE"
            
            payload = {
                "uid": os.getenv('BROKER_API_KEY').split(':::')[0],
                "exch": exchange,
                "token": token
            }
            
            response = get_api_response("/PiConnectTP/GetQuotes", self.auth_token, payload=payload)
            
            if response.get('stat') != 'Ok':
                raise Exception(f"Error from Flattrade API: {response.get('emsg', 'Unknown error')}")
            
            # Format bids and asks data
            bids = []
            asks = []
            
            # Process top 5 bids and asks
            for i in range(1, 6):
                bids.append({
                    'price': float(response.get(f'bp{i}', 0)),
                    'quantity': int(response.get(f'bq{i}', 0))
                })
                asks.append({
                    'price': float(response.get(f'sp{i}', 0)),
                    'quantity': int(response.get(f'sq{i}', 0))
                })
            
            # Return depth data
            return {
                'bids': bids,
                'asks': asks,
                'totalbuyqty': sum(bid['quantity'] for bid in bids),
                'totalsellqty': sum(ask['quantity'] for ask in asks),
                'high': float(response.get('h', 0)),
                'low': float(response.get('l', 0)),
                'ltp': float(response.get('lp', 0)),
                'ltq': int(response.get('ltq', 0)),  # Last Traded Quantity
                'open': float(response.get('o', 0)),
                'prev_close': float(response.get('c', 0)) if 'c' in response else 0,
                'volume': int(float(response.get('v', 0))),
                'oi': int(response.get('oi', 0))  # Open Interest
            }
            
        except Exception as e:
            raise Exception(f"Error fetching market depth: {str(e)}")

    def get_history(self, symbol: str, exchange: str, interval: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Get historical data for given symbol
        Args:
            symbol: Trading symbol
            exchange: Exchange (e.g., NSE, BSE)
            interval: Candle interval in common format:
                     Minutes: 1m, 5m, 15m, 30m
                     Hours: 1h
                     Days: D
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        Returns:
            pd.DataFrame: Historical data with columns [timestamp, open, high, low, close, volume, oi]
        """
        try:
            # Check if interval is supported
            if interval not in self.timeframe_map:
                supported = list(self.timeframe_map.keys())
                raise Exception(f"Unsupported interval '{interval}'. Supported intervals are: {', '.join(supported)}")

            # Convert symbol to broker format and get token
            br_symbol = get_br_symbol(symbol, exchange)
            token = get_token(symbol, exchange)

            if(exchange=="NSE_INDEX"):
                exchange="NSE"  
            elif(exchange=="BSE_INDEX"):
                exchange="BSE"
            
            # Convert dates to epoch timestamps
            start_ts = int(datetime.strptime(start_date + " 00:00:00", '%Y-%m-%d %H:%M:%S').timestamp())
            end_ts = int(datetime.strptime(end_date + " 23:59:59", '%Y-%m-%d %H:%M:%S').timestamp())

            # For daily data, use EODChartData endpoint
            if interval == 'D':
                # Format symbol as NSE:SYMBOL
                formatted_symbol = f"{exchange}:{br_symbol}"
                payload = {
                    "sym": formatted_symbol,
                    "from": str(start_ts),  # Use epoch timestamp
                    "to": str(end_ts)       # Use epoch timestamp
                }
                logger.debug(f"EOD Payload: {payload}")  # Debug print
                try:
                    response = get_api_response("/PiConnectTP/EODChartData", self.auth_token, payload=payload)
                    logger.debug(f"EOD Response: {response}")  # Debug print
                except Exception as e:
                    logger.error(f"Error in EOD request: {e}")
                    response = []  # Continue with empty response to try quotes
            else:
                # For intraday data, use TPSeries endpoint
                payload = {
                    "uid": os.getenv('BROKER_API_KEY').split(':::')[0],
                    "exch": exchange,
                    "token": token,
                    "st": str(start_ts),  # Start time in epoch
                    "et": str(end_ts),    # End time in epoch
                    "intrv": self.timeframe_map[interval]  # Changed to intrv
                }
                logger.debug(f"Intraday Payload: {payload}")  # Debug print
                response = get_api_response("/PiConnectTP/TPSeries", self.auth_token, payload=payload)
                logger.debug(f"Intraday Response: {response}")  # Debug print
           
            # Check if response is a dict (error case) or list (success case)
            if isinstance(response, dict):
                if response.get('stat') == 'Not_Ok':
                    raise Exception(f"Error from Flattrade API: {response.get('emsg', 'Unknown error')}")
            elif not isinstance(response, list):
                raise Exception("Invalid response format from Flattrade API")
            
            # Convert response to DataFrame
            data = []
            for candle in response:
                if isinstance(candle, str):
                    candle = json.loads(candle)
                
                try:
                    # Parse timestamp based on interval
                    if interval == 'D':
                        # EOD data format: "21-SEP-2022"
                        timestamp = int(candle.get('ssboe', 0))  # Use ssboe for timestamp
                        data.append({
                            'timestamp': timestamp,
                            'open': float(candle.get('into', 0)),   # EOD uses 'into' for open
                            'high': float(candle.get('inth', 0)),   # EOD uses 'inth' for high
                            'low': float(candle.get('intl', 0)),    # EOD uses 'intl' for low
                            'close': float(candle.get('intc', 0)),  # EOD uses 'intc' for close
                            'volume': int(float(candle.get('intv', 0))),  # EOD uses 'intv' for volume
                            'oi': int(float(candle.get('oi', 0)))   # Open Interest
                        })
                    else:
                        # Intraday format: "02-06-2020 15:46:23"
                        try:
                            timestamp = int(datetime.strptime(candle['time'], '%d-%m-%Y %H:%M:%S').timestamp())
                        except ValueError:
                            logger.info(f"Error parsing timestamp: {candle['time']}")
                            continue

                        # Skip candles with all zero values
                        if (float(candle.get('into', 0)) == 0 and 
                            float(candle.get('inth', 0)) == 0 and 
                            float(candle.get('intl', 0)) == 0 and 
                            float(candle.get('intc', 0)) == 0):
                            continue

                        data.append({
                            'timestamp': timestamp,
                            'open': float(candle.get('into', 0)),   # Intraday also uses 'into' for open
                            'high': float(candle.get('inth', 0)),   # Intraday also uses 'inth' for high
                            'low': float(candle.get('intl', 0)),    # Intraday also uses 'intl' for low
                            'close': float(candle.get('intc', 0)),  # Intraday also uses 'intc' for close
                            'volume': int(float(candle.get('intv', 0))),  # Intraday also uses 'intv' for volume
                            'oi': int(float(candle.get('oi', 0)))   # Open Interest
                        })
                except (KeyError, ValueError) as e:
                    logger.error(f"Error parsing candle data: {e}, Candle: {candle}")
                    continue
            df = pd.DataFrame(data)
            if df.empty:
                df = pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'oi'])
            
            # For daily data, append today's data from quotes if it's missing
            if interval == 'D':
                # Create today's timestamp at 00:00:00 UTC then add 5:30 hours for IST (to match Angel's format)
                # This ensures daily candles align with IST trading hours
                utc_today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                ist_today = utc_today + timedelta(hours=5, minutes=30)
                today_ts = int(ist_today.timestamp())
                
                # Only get today's data if it's within the requested range
                if today_ts >= start_ts and today_ts <= end_ts:
                    if df.empty or df['timestamp'].max() < today_ts:
                        try:
                            # Get today's data from quotes
                            quotes = self.get_quotes(symbol, exchange)
                            
                            if quotes:
                                today_data = {
                                    'timestamp': today_ts,
                                    'open': float(quotes.get('open', 0)),
                                    'high': float(quotes.get('high', 0)),
                                    'low': float(quotes.get('low', 0)),
                                    'close': float(quotes.get('ltp', 0)),  # Use LTP as close
                                    'volume': int(float(quotes.get('volume', 0))),
                                    'oi': 0  # OI not available in quotes data
                                }
                                logger.info(f"Today's quote data: {today_data}")
                                # Append today's data
                                df = pd.concat([df, pd.DataFrame([today_data])], ignore_index=True)
                                logger.info("Added today's data from quotes", )
                        except Exception as e:
                            logger.info(f"Error fetching today's data from quotes: {e}")
                else:
                    logger.info(f"Today ({today_ts}) is outside requested range ({start_ts} to {end_ts})")
            
            # Sort by timestamp
            df = df.sort_values('timestamp')
            
            # Reorder columns to match Angel format
            df = df[['close', 'high', 'low', 'open', 'timestamp', 'volume', 'oi']]
            
            return df
            
        except Exception as e:
            raise Exception(f"Error fetching historical data: {str(e)}")

    def get_intervals(self) -> list:
        """
        Get list of supported intervals
        Returns:
            list: List of supported intervals
        """
        return list(self.timeframe_map.keys())
