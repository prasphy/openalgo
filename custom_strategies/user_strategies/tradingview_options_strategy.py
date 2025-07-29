"""
TradingView Options Strategy

This strategy implements the Trading Algorithm Pseudocode for processing TradingView signals
to trade options based on open interest analysis using real OpenAlgo depth API.

The strategy:
1. Receives BUY/SELL signals from TradingView webhooks
2. Gets current index price using OpenAlgo API
3. Accesses real option chain data using depth API for ATM ±2 strikes
4. Finds strike with highest OI within the range
5. Selects appropriate option (call for BUY, put for SELL) 
6. Checks open interest to ensure sufficient liquidity
7. Returns trading signals for execution

Configuration Parameters:
- index_symbol: The underlying index (e.g., NIFTY, BANKNIFTY)
- exchange: Options exchange (e.g., NFO)
- expiry_date: Option expiry date (DDMMMYY format), optional
- oi_threshold: Minimum open interest required (default: 1000)
- default_quantity: Number of option contracts to trade (default: 1)
- strike_range: Number of strikes to check above/below ATM (default: 2)
- step_size: Strike price step size (default: 100 for NIFTY, 500 for BANKNIFTY)
"""

from custom_strategies.base_strategy import BaseStrategy
import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional


class TradingViewOptionsStrategy(BaseStrategy):
    """
    TradingView Options Strategy following the Trading Algorithm Pseudocode
    """
    
    def __init__(self, api_key: str, strategy_config: Dict[str, Any], base_url: str = "http://127.0.0.1:5000"):
        super().__init__(api_key, strategy_config, base_url)
        
        # Initialize configuration with defaults
        self.index_symbol = self.get_config_value('index_symbol', 'NIFTY')
        self.exchange = self.get_config_value('exchange', 'NFO')
        self.expiry_date = self.get_config_value('expiry_date', None)
        self.oi_threshold = int(self.get_config_value('oi_threshold', 1000))
        self.default_quantity = int(self.get_config_value('default_quantity', 1))
        self.strike_range = int(self.get_config_value('strike_range', 2))  # ATM ±2
        
        # Set step size based on index
        if self.index_symbol.upper() == 'BANKNIFTY':
            self.step_size = int(self.get_config_value('step_size', 100))
        else:  # NIFTY and others
            self.step_size = int(self.get_config_value('step_size', 50))
        
        # Symbol parsing regex (from NiftyOI.ipynb)
        self._sym_rx = re.compile(r"^[A-Z]+(\d{2}[A-Z]{3}\d{2})(\d+)(CE|PE)$")
        
        self.log_info(f"Initialized TradingView Options Strategy for {self.index_symbol}")
        self.log_info(f"Step size: {self.step_size}, Strike range: ±{self.strike_range}")
    
    def execute(self) -> List[str]:
        """
        Execute the strategy following the Trading Algorithm Pseudocode steps
        
        Returns:
            List of option symbols to trade
        """
        try:
            self.log_info("Starting TradingView Options Strategy execution")
            
            # Step 1: Parse webhook signal (simulate receiving from TradingView)
            signal, expiry = self._parse_alert_message()
            if not signal:
                self.log_error("No valid signal found")
                return []
            
            # Step 2: Get current index price
            current_price = self._get_current_index_price()
            if not current_price:
                self.log_error("Failed to get current index price")
                return []
            
            # Step 3: Get ATM strike
            atm_strike = self._get_atm_strike(current_price)
            self.log_info(f"ATM strike: {atm_strike}")
            
            # Step 4: Access option chain using real depth API
            option_chain_data = self._get_option_chain_data(atm_strike, expiry)
            if not option_chain_data:
                self.log_error("Failed to get option chain data")
                return []
            
            # Step 5: Find strike with highest OI
            best_strike = self._find_highest_oi_strike(option_chain_data, signal)
            if not best_strike:
                self.log_error("Failed to find strike with sufficient OI")
                return []
            
            # Step 6: Generate option symbol
            option_symbol = self._generate_option_symbol(best_strike, signal, expiry)
            if not option_symbol:
                self.log_error("Failed to generate option symbol")
                return []
            
            # Step 7: Validate final OI check
            strike_data = option_chain_data.get(best_strike, {})
            option_type = 'CE' if signal == 'BUY' else 'PE'
            final_oi = strike_data.get(option_type, {}).get('oi', 0)
            
            if final_oi < self.oi_threshold:
                self.log_error(f"Final OI check failed: {final_oi} < {self.oi_threshold}")
                return []
            
            # Step 8: Return signal for execution
            self.log_info(f"Generated signal: {option_symbol} ({signal}) with OI: {final_oi}")
            return [option_symbol]
            
        except Exception as e:
            self.log_error(f"Error in strategy execution: {str(e)}")
            return []
    
    def _parse_alert_message(self) -> tuple:
        """
        Step 2: Parse Alert Message from configuration
        
        Expected format: "BUY NIFTY [DDMMMYY]" or "SELL BANKNIFTY"
        
        Returns:
            tuple: (signal, expiry_date)
        """
        try:
            # Get signal from configuration or use default for testing
            alert_message = self.get_config_value('alert_message', f'BUY {self.index_symbol}')
            
            parts = alert_message.strip().upper().split()
            if len(parts) < 2:
                self.log_error(f"Invalid alert message format: {alert_message}")
                return None, None
            
            signal = parts[0]
            index = parts[1]
            expiry = parts[2] if len(parts) > 2 else self.expiry_date
            
            # Validate signal
            if signal not in ['BUY', 'SELL']:
                self.log_error(f"Invalid signal: {signal}")
                return None, None
            
            # Update index symbol if provided in message
            if index != self.index_symbol:
                self.log_info(f"Using index from alert: {index}")
                self.index_symbol = index
            
            # Use default expiry if not provided
            if not expiry:
                expiry = self._get_default_expiry()
            
            self.log_info(f"Parsed alert: Signal={signal}, Index={index}, Expiry={expiry}")
            return signal, expiry
            
        except Exception as e:
            self.log_error(f"Error parsing alert message: {str(e)}")
            return None, None
    
    def _get_current_index_price(self) -> Optional[float]:
        """
        Step 3: Get Current Index Price
        
        Returns:
            Current price of the index
        """
        try:
            self.log_info(f"Getting current price for {self.index_symbol}")
            
            # Use quotes API to get current price (use NSE_INDEX for indices)
            exchange = 'NSE_INDEX' if self.index_symbol in ['NIFTY', 'BANKNIFTY'] else 'NSE'
            response = self.get_quotes(self.index_symbol, exchange)
            
            if response.get('status') == 'success':
                data = response.get('data', {})
                current_price = float(data.get('ltp', 0))
                
                if current_price > 0:
                    self.log_info(f"Current {self.index_symbol} price: {current_price}")
                    return current_price
                else:
                    self.log_error("Invalid price received from API")
                    return None
            else:
                self.log_error(f"Failed to get quotes: {response.get('message', 'Unknown error')}")
                return None
                
        except Exception as e:
            self.log_error(f"Error getting current price: {str(e)}")
            return None
    
    def _get_atm_strike(self, current_price: float) -> int:
        """
        Get ATM (At The Money) strike price based on current price and step size
        
        Args:
            current_price: Current index price
            
        Returns:
            ATM strike price
        """
        try:
            atm_strike = int(round(current_price / self.step_size) * self.step_size)
            return atm_strike
        except Exception as e:
            self.log_error(f"Error calculating ATM strike: {str(e)}")
            return int(current_price)
    
    def _get_option_chain_data(self, atm_strike: int, expiry: str) -> Optional[Dict]:
        """
        Step 4: Access Option Chain using real OpenAlgo depth API
        
        Args:
            atm_strike: ATM strike price
            expiry: Expiry date in DDMMMYY format
            
        Returns:
            Option chain data with OI information
        """
        try:
            self.log_info(f"Getting option chain for {self.index_symbol} ATM={atm_strike}, expiry={expiry}")
            
            # Generate strikes around ATM (±strike_range)
            strikes = []
            for i in range(-self.strike_range, self.strike_range + 1):
                strike = atm_strike + (i * self.step_size)
                strikes.append(strike)
            
            self.log_info(f"Checking strikes: {strikes}")
            
            option_chain = {}
            
            # Fetch data for each strike (both CE and PE)
            for strike in strikes:
                option_chain[strike] = {'CE': {}, 'PE': {}}
                
                # Fetch CE (Call) data
                ce_symbol = f"{self.index_symbol}{expiry}{strike}CE"
                ce_data = self._fetch_option_depth(ce_symbol)
                if ce_data:
                    option_chain[strike]['CE'] = ce_data
                
                # Fetch PE (Put) data  
                pe_symbol = f"{self.index_symbol}{expiry}{strike}PE"
                pe_data = self._fetch_option_depth(pe_symbol)
                if pe_data:
                    option_chain[strike]['PE'] = pe_data
            
            # Filter out strikes with no data
            valid_chain = {k: v for k, v in option_chain.items() 
                          if v['CE'] or v['PE']}
            
            if valid_chain:
                self.log_info(f"Retrieved option chain with {len(valid_chain)} valid strikes")
                return valid_chain
            else:
                self.log_error("No valid option data found")
                return None
                
        except Exception as e:
            self.log_error(f"Error getting option chain: {str(e)}")
            return None
    
    def _fetch_option_depth(self, symbol: str) -> Optional[Dict]:
        """
        Fetch option depth data using OpenAlgo depth API
        
        Args:
            symbol: Option symbol (e.g., NIFTY15AUG2524500CE)
            
        Returns:
            Option depth data with OI, LTP, etc.
        """
        try:
            response = self.get_depth(symbol, self.exchange)
            
            if response.get('status') == 'success':
                data = response.get('data', {})
                
                # Check if OI data is available
                if 'oi' not in data:
                    self.log_warning(f"Missing OI data for {symbol}")
                    return None
                
                return {
                    'oi': data.get('oi', 0),
                    'ltp': data.get('ltp', 0),
                    'volume': data.get('volume', 0),
                    'symbol': symbol
                }
            else:
                self.log_warning(f"Failed to get depth for {symbol}: {response.get('message', 'Unknown error')}")
                return None
                
        except Exception as e:
            self.log_warning(f"Error fetching depth for {symbol}: {str(e)}")
            return None
    
    def _find_highest_oi_strike(self, option_chain: Dict, signal: str) -> Optional[int]:
        """
        Step 5: Find strike with highest OI for the given signal type
        
        Args:
            option_chain: Option chain data
            signal: BUY or SELL signal
            
        Returns:
            Strike price with highest OI
        """
        try:
            option_type = 'CE' if signal == 'BUY' else 'PE'
            self.log_info(f"Finding highest OI strike for {option_type} options")
            
            best_strike = None
            highest_oi = 0
            
            for strike, data in option_chain.items():
                option_data = data.get(option_type, {})
                oi = option_data.get('oi', 0)
                
                self.log_info(f"Strike {strike} {option_type}: OI={oi}")
                
                # Check if this strike meets minimum threshold and has higher OI
                if oi >= self.oi_threshold and oi > highest_oi:
                    highest_oi = oi
                    best_strike = strike
            
            if best_strike:
                self.log_info(f"Best strike found: {best_strike} with OI: {highest_oi}")
                return best_strike
            else:
                self.log_error(f"No strike found with OI >= {self.oi_threshold}")
                return None
                
        except Exception as e:
            self.log_error(f"Error finding highest OI strike: {str(e)}")
            return None
    
    def _generate_option_symbol(self, strike: int, signal: str, expiry: str) -> Optional[str]:
        """
        Step 6: Generate option symbol
        
        Args:
            strike: Strike price
            signal: BUY or SELL signal
            expiry: Expiry date in DDMMMYY format
            
        Returns:
            Option symbol
        """
        try:
            # For BUY signal, select call option
            # For SELL signal, select put option
            option_type = 'CE' if signal == 'BUY' else 'PE'
            
            # Create option symbol in NSE format
            # Example: NIFTY15AUG2524500CE
            option_symbol = f"{self.index_symbol}{expiry}{strike}{option_type}"
            
            self.log_info(f"Generated option symbol: {option_symbol}")
            return option_symbol
            
        except Exception as e:
            self.log_error(f"Error generating option symbol: {str(e)}")
            return None
    
    def _get_default_expiry(self) -> str:
        """
        Get default expiry date in DDMMMYY format (next Thursday for weekly, last Thursday for monthly)
        
        Returns:
            Expiry date in DDMMMYY format
        """
        try:
            today = datetime.now()
            
            # Find next Thursday
            days_ahead = 3 - today.weekday()  # Thursday is weekday 3
            if days_ahead <= 0:  # Target day already happened this week
                days_ahead += 7
            
            next_thursday = today + timedelta(days=days_ahead)
            
            # Format as DDMMMYY
            months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
                     'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
            
            day = next_thursday.strftime('%d')
            month = months[next_thursday.month - 1]
            year = next_thursday.strftime('%y')
            
            expiry_formatted = f"{day}{month}{year}"
            self.log_info(f"Using default expiry: {expiry_formatted}")
            return expiry_formatted
            
        except Exception as e:
            self.log_error(f"Error getting default expiry: {str(e)}")
            return "15AUG25"  # Default fallback
    
    def set_webhook_data(self, signal: str, expiry: str = None):
        """
        Set webhook data for processing (used when called via webhook)
        
        Args:
            signal: BUY or SELL signal
            expiry: Optional expiry date
        """
        self.webhook_signal = signal
        self.webhook_expiry = expiry
        self.log_info(f"Set webhook data: signal={signal}, expiry={expiry}")
    
    def process_tradingview_webhook(self, webhook_data: Dict[str, Any]) -> List[str]:
        """
        Process TradingView webhook data
        
        Args:
            webhook_data: Webhook payload from TradingView
            
        Returns:
            List of option symbols to trade
        """
        try:
            # Extract signal from webhook data
            # TradingView webhook format may vary, this is a common structure
            action = webhook_data.get('action', '').upper()
            symbol = webhook_data.get('symbol', self.index_symbol)
            expiry = webhook_data.get('expiry')
            
            if action in ['BUY', 'SELL']:
                # Update configuration with webhook data
                alert_message = f"{action} {symbol}"
                if expiry:
                    # Convert YYYY-MM-DD to DDMMMYY if needed
                    if '-' in expiry:
                        expiry_formatted = self._convert_expiry_format(expiry)
                        alert_message += f" {expiry_formatted}"
                    else:
                        alert_message += f" {expiry}"
                
                self.config['alert_message'] = alert_message
                
                # Execute strategy
                return self.execute()
            else:
                self.log_error(f"Invalid action in webhook: {action}")
                return []
                
        except Exception as e:
            self.log_error(f"Error processing webhook: {str(e)}")
            return []
    
    def _convert_expiry_format(self, expiry_date: str) -> str:
        """
        Convert expiry from YYYY-MM-DD to DDMMMYY format
        
        Args:
            expiry_date: Date in YYYY-MM-DD format
            
        Returns:
            Date in DDMMMYY format
        """
        try:
            date_obj = datetime.strptime(expiry_date, '%Y-%m-%d')
            months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
                     'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
            
            day = date_obj.strftime('%d')
            month = months[date_obj.month - 1]
            year = date_obj.strftime('%y')
            
            return f"{day}{month}{year}"
        except Exception as e:
            self.log_error(f"Error converting expiry format: {str(e)}")
            return self._get_default_expiry()
    
    def get_option_chain_summary(self, atm_strike: int, expiry: str) -> Dict:
        """
        Get a summary of option chain data for analysis
        
        Args:
            atm_strike: ATM strike price
            expiry: Expiry date
            
        Returns:
            Summary of option chain data
        """
        try:
            option_chain = self._get_option_chain_data(atm_strike, expiry)
            if not option_chain:
                return {}
            
            summary = {
                'atm_strike': atm_strike,
                'expiry': expiry,
                'strikes_analyzed': len(option_chain),
                'call_oi_total': 0,
                'put_oi_total': 0,
                'max_call_oi': {'strike': None, 'oi': 0},
                'max_put_oi': {'strike': None, 'oi': 0},
                'strikes_detail': {}
            }
            
            for strike, data in option_chain.items():
                ce_oi = data.get('CE', {}).get('oi', 0)
                pe_oi = data.get('PE', {}).get('oi', 0)
                
                summary['call_oi_total'] += ce_oi
                summary['put_oi_total'] += pe_oi
                
                if ce_oi > summary['max_call_oi']['oi']:
                    summary['max_call_oi'] = {'strike': strike, 'oi': ce_oi}
                
                if pe_oi > summary['max_put_oi']['oi']:
                    summary['max_put_oi'] = {'strike': strike, 'oi': pe_oi}
                
                summary['strikes_detail'][strike] = {
                    'CE_OI': ce_oi,
                    'PE_OI': pe_oi,
                    'CE_LTP': data.get('CE', {}).get('ltp', 0),
                    'PE_LTP': data.get('PE', {}).get('ltp', 0)
                }
            
            return summary
            
        except Exception as e:
            self.log_error(f"Error generating option chain summary: {str(e)}")
            return {}


# Example usage and testing
if __name__ == "__main__":
    # Example configuration for testing
    test_config = {
        'index_symbol': 'NIFTY',
        'exchange': 'NFO',
        'oi_threshold': 1000,
        'default_quantity': 1,
        'strike_range': 2,
        'step_size': 100,
        'alert_message': 'BUY NIFTY 15AUG25'  # Example TradingView signal
    }
    
    # This would normally be provided by the OpenAlgo framework
    api_key = "test_api_key"
    
    # Create and test the strategy
    strategy = TradingViewOptionsStrategy(api_key, test_config)
    
    # Test execution
    signals = strategy.execute()
    print(f"Generated signals: {signals}")
    
    # Test webhook processing
    webhook_payload = {
        'action': 'BUY',
        'symbol': 'NIFTY',
        'expiry': '2025-08-15'
    }
    
    webhook_signals = strategy.process_tradingview_webhook(webhook_payload)
    print(f"Webhook signals: {webhook_signals}")