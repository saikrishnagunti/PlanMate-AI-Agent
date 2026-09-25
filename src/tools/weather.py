import requests
from src.config import DEFAULT_LAT, DEFAULT_LON

WMO_CODE_MAP = {
    0: "Clear Sky", 1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast",
    45: "Foggy", 51: "Light Drizzle", 61: "Slight Rain", 63: "Moderate Rain",
    65: "Heavy Rain", 80: "Rain Showers", 95: "Thunderstorm"
}

def fetch_weather(lat: float = DEFAULT_LAT, lon: float = DEFAULT_LON, locality_name: str = "your area") -> dict:
    """Fetches real-time weather metrics from Open-Meteo with no API key requirement."""
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,weather_code,precipitation&timezone=auto"
    )
    try:
        res = requests.get(url, timeout=5).json()
        curr = res.get("current", {})
        temp = curr.get("temperature_2m", 28.0)
        humidity = curr.get("relative_humidity_2m", 55)
        code = curr.get("weather_code", 0)
        precip = curr.get("precipitation", 0.0)

        condition = WMO_CODE_MAP.get(code, "Clear")
        is_rainy = precip > 0.1 or code in [51, 61, 63, 65, 80, 95]

        if is_rainy:
            verdict = f"Precipitation detected ({condition}). An indoor venue is strongly recommended."
        elif temp > 36:
            verdict = f"High temperatures ({temp}°C). Outdoor activities are best reserved for later in the evening."
        else:
            verdict = f"Pleasant conditions ({condition}, {temp}°C). Great weather to step out!"

        return {
            "locality": locality_name,
            "temperature": f"{temp}°C",
            "condition": condition,
            "humidity": f"{humidity}%",
            "verdict": verdict,
            "outdoor_suitable": not is_rainy and temp <= 36
        }
    except Exception:
        return {
            "locality": locality_name,
            "temperature": "28°C",
            "condition": "Pleasant",
            "humidity": "55%",
            "verdict": "Pleasant ambient weather for daily plans.",
            "outdoor_suitable": True
        }