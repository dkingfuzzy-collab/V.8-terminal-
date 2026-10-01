import requests
import pandas as pd
import time
import os

# Get your API key from Render Environment Variables (or paste it here for testing)
API_KEY = os.getenv("TWELVEDATA_API_KEY", "YOUR_API_KEY_HERE")
BASE_URL = "https://api.twelvedata.com/time_series"

def fetch_candles(symbol="XAU/USD", interval="15min", outputsize=100):
    """
    Fetches historical candles from TwelveData.
    """
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": API_KEY,
        "format": "JSON"
    }
    
    try:
        response = requests.get(BASE_URL, params=params, timeout=10)
        data = response.json()
        
        # Check for API errors (like invalid API key or rate limits)
        if "code" in data and data["code"] != 200:
            print(f"API Error: {data.get('message')}")
            return None
            
        if "values" not in data:
            print("No candle data returned.")
            return None
            
        # Convert to Pandas DataFrame for easier analysis
        df = pd.DataFrame(data["values"])
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.sort_values('datetime').reset_index(drop=True)
        
        # Convert strings to floats
        for col in ['open', 'high', 'low', 'close']:
            df[col] = df[col].astype(float)
            
        return df

    except Exception as e:
        print(f"Network or parsing error: {e}")
        return None

def get_safe_candles(symbol="XAU/USD", interval="15min"):
    """
    Wrapper with Retry Logic. This is the fix for 'Insufficient Candles'.
    """
    MIN_CANDLES_NEEDED = 50
    MAX_RETRIES = 3
    
    for attempt in range(MAX_RETRIES):
        df = fetch_candles(symbol, interval, outputsize=100)
        
        if df is not None and len(df) >= MIN_CANDLES_NEEDED:
            return df # Success!
            
        print(f"Attempt {attempt+1}: Insufficient candles. Retrying in 3 seconds...")
        time.sleep(3)
        
    return None # All retries failed
