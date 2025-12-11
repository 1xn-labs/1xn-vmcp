```
#!/usr/bin/env python3
"""
Weather Cities Workflow
Fetches list of cities, gets weather and location for each, and displays in a table
"""
import asyncio
from vmcp_sdk import VMCPClient



async def weather_analysis_workflow():
    """Fetch cities, weather, and location data and display in a table."""
    
    async with VMCPClient() as client:
        print("Fetching list of cities...\n")
        # Step 0: Get list of cities info
        cities_result  = await client.allfeature_string_cities()
        cities = cities_result.value
    
        if not cities:
            print("No cities found!")
            return
        
        print(f"Found cities info: {cities}\n")
        
        # Step 1: Get list of cities
        cities_result = await client.allfeature_list_cities_structured()
        cities = cities_result.value

        print(f"Found cities info: {cities}\n")

        # Extract cities from structured content
        cities = cities_result.value.get("result", [])

        print("Cities: ", cities)
        if not cities:
            print("No cities found!")
            return
        
        print(f"Found {len(cities)} cities\n")
        
        # Step 2: Fetch weather and location for each city
        city_data = []
        
        for city in cities:
            print(f"Fetching data for {city}...")
            
            # Get weather
            weather_result = await client.allfeature_get_weather_structured(city=city)
            weather = weather_result.value
            print("weather results: ", weather)
            
            # Get location
            location_result = await client.allfeature_get_location(city=city)
            location = location_result.value
            print("location results: ", weather)

            
            city_data.append({
                "city": city,
                "temperature": weather.get("temperature", "N/A"),
                "humidity": weather.get("humidity", "N/A"),
                "condition": weather.get("condition", "N/A"),
                "wind_speed": weather.get("wind_speed", "N/A"),
                "latitude": location.get("latitude", "N/A"),
                "longitude": location.get("longitude", "N/A")
            })
        
        # Step 3: Display as formatted table
        print("\n" + "="*100)
        print("WEATHER CONDITIONS BY CITY (Highlighting: Temperature)")
        print("="*100)
        
        # Table header
        header = f"{'City':<15} {'Temperature (°C)':<18} {'Condition':<15} {'Humidity (%)':<15} {'Wind Speed':<12} {'Location':<25}"
        print(header)
        print("-"*100)
        
        # Table rows
        for data in city_data:
            temp = data['temperature']
            
            # Highlight temperature with markers
            if isinstance(temp, (int, float)):
                if temp >= 25:
                    temp_str = f"🔥 {temp}°C (HOT)"
                elif temp >= 15:
                    temp_str = f"☀️  {temp}°C (WARM)"
                elif temp >= 5:
                    temp_str = f"🌤️  {temp}°C (COOL)"
                else:
                    temp_str = f"❄️  {temp}°C (COLD)"
            else:
                temp_str = str(temp)
            
            location_str = f"({data['latitude']}, {data['longitude']})"
            
            row = f"{data['city']:<15} {temp_str:<18} {data['condition']:<15} {data['humidity']:<15} {data['wind_speed']:<12} {location_str:<25}"
            print(row)
        
        print("="*100)
        
        # Summary statistics
        temps = [d['temperature'] for d in city_data if isinstance(d['temperature'], (int, float))]
        if temps:
            print(f"\nTemperature Summary:")
            print(f"  Average: {sum(temps)/len(temps):.1f}°C")
            print(f"  Highest: {max(temps)}°C")
            print(f"  Lowest: {min(temps)}°C")


def main():
    """Fetch cities, weather, and location data and display in a table."""
    asyncio.run(weather_analysis_workflow())


if __name__ == "__main__":
    main()

```


