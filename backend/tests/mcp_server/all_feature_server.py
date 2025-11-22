"""
All Feature MCP Server - Comprehensive demonstration of MCP features

Supports multiple transport types:
- stdio: Standard input/output transport (for CLI usage)
- sse: Server-Sent Events transport
- streamable-http: Streamable HTTP transport (default)
"""

import argparse
import logging
import os
import random
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, TypedDict

import aiohttp  # type: ignore[import-untyped]
import pandas as pd  # type: ignore[import-untyped]
import pytz  # type: ignore[import-untyped]
from mcp.server.fastmcp import Context, FastMCP, Image
from mcp.server.fastmcp.prompts import base
from mcp.types import (
    Completion,
    CompletionArgument,
    CompletionContext,
    PromptReference,
    ResourceTemplateReference,
    SamplingMessage,
    TextContent,
)
from PIL import Image as PILImage  # type: ignore[import-untyped]
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# Mock database class for example
class Database:
    """Mock database class for example."""

    @classmethod
    async def connect(cls) -> "Database":
        """Connect to database."""
        return cls()

    async def disconnect(self) -> None:
        """Disconnect from database."""
        pass

    def query(self) -> str:
        """Execute a query."""
        return "Query result"

@dataclass
class AppContext:
    """Application context with typed dependencies."""

    db: Database


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage application lifecycle with type-safe context."""
    # Initialize on startup
    db = await Database.connect()
    try:
        yield AppContext(db=db)
    finally:
        # Cleanup on shutdown
        await db.disconnect()

# Global variable to cache the cities DataFrame
_cities_df = None

def _load_cities_data():
    """Load and cache the cities data once."""
    global _cities_df
    if _cities_df is None:
        csv_path = os.path.join(os.path.dirname(__file__), "worldcities.csv")
        _cities_df = pd.read_csv(csv_path)
        # Create lowercase column for case-insensitive matching
        _cities_df['city_ascii_lower'] = _cities_df['city_ascii'].str.lower()
    return _cities_df

def _weather_code_to_condition(weather_code: int) -> str:
    """Convert Open-Meteo weather code to human-readable condition."""
    # Based on Open-Meteo weather codes
    code_map = {
        0: "clear",
        1: "mainly clear",
        2: "partly cloudy",
        3: "overcast",
        45: "foggy",
        48: "foggy",
        51: "light drizzle",
        53: "moderate drizzle",
        55: "dense drizzle",
        61: "light rain",
        63: "moderate rain",
        65: "heavy rain",
        71: "light snow",
        73: "moderate snow",
        75: "heavy snow",
        80: "light showers",
        81: "moderate showers",
        82: "violent showers",
        95: "thunderstorm",
        96: "thunderstorm with hail",
        99: "thunderstorm with hail"
    }
    return code_map.get(weather_code, "unknown")

mcp = FastMCP(name="Everything MCP Server",stateless_http=True)#,lifespan=app_lifespan)

# Access type-safe lifespan context in tools
@mcp.tool()
def query_db(ctx: Context) -> str:
    """Tool that uses initialized resources."""
    db = ctx.request_context.lifespan_context.db
    return db.query()

@mcp.prompt(title="Code Review")
def review_code(code: str) -> str:
    return f"Please review this code:\n\n{code}"


@mcp.prompt(title="Debug Assistant")
def debug_error(error: str) -> list[base.Message]:
    return [
        base.UserMessage("I'm seeing this error:"),
        base.UserMessage(error),
        base.AssistantMessage("I'll help debug that. What have you tried so far?"),
    ]

@mcp.resource("file://documents/{name}")
def read_document(name: str) -> str:
    """Read a document by name."""
    # This would normally read from disk
    return f"Content of {name}"


@mcp.resource("config://settings")
def get_settings() -> str:
    """Get application settings."""
    return """{
  "theme": "dark",
  "language": "en",
  "debug": false
}"""


@mcp.tool()
def add_numbers(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b


@mcp.tool()
async def get_weather(city: str, unit: str = "celsius") -> str:
    """Get weather for a city using Open-Meteo API."""
    try:
        # Load cached cities data
        df = _load_cities_data()
        city_lower = city.lower()

        # Find matching city
        city_match = df[df['city_ascii_lower'] == city_lower]

        if city_match.empty:
            # Return default temperature when city is not found
            default_temp = 22.0
            temp_unit = "°C"
            if unit.lower() == "fahrenheit":
                default_temp = (default_temp * 9/5) + 32
                temp_unit = "°F"
            return f"Weather in {city}: {default_temp}{temp_unit} (default - city not found in database)"

        # Get the first match (in case of duplicates)
        city_row = city_match.iloc[0]
        lat = float(city_row['lat'])
        lng = float(city_row['lng'])
        found_city = city_row['city_ascii']

        # Call Open-Meteo API
        api_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lng}&current=temperature_2m"

        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                if response.status == 200:
                    data = await response.json()

                    # Extract temperature
                    current_temp = data['current']['temperature_2m']
                    temp_unit = data['current_units']['temperature_2m']
                    timezone = data['timezone']
                    time = data['current']['time']

                    # Convert temperature if needed
                    if unit.lower() == "fahrenheit":
                        if temp_unit == "°C":
                            current_temp = (current_temp * 9/5) + 32
                            temp_unit = "°F"

                    return f"Weather in {found_city}: {current_temp}{temp_unit} (as of {time} {timezone})"
                else:
                    # Return default temperature when API fails
                    default_temp = 25.0
                    temp_unit = "°C"
                    if unit.lower() == "fahrenheit":
                        default_temp = (default_temp * 9/5) + 32
                        temp_unit = "°F"
                    return f"Weather in {found_city}: {default_temp}{temp_unit} (default - API unavailable)"

    except FileNotFoundError:
        # Return default temperature when CSV file is not found
        default_temp = 22.0
        temp_unit = "°C"
        if unit.lower() == "fahrenheit":
            default_temp = (default_temp * 9/5) + 32
            temp_unit = "°F"
        return f"Weather in {city}: {default_temp}{temp_unit} "
    except Exception:
        # Return default temperature for any other errors
        default_temp = 25.0
        temp_unit = "°C"
        if unit.lower() == "fahrenheit":
            default_temp = (default_temp * 9/5) + 32
            temp_unit = "°F"
        return f"Weather in {city}: {default_temp}{temp_unit} "

@mcp.resource("github://repos/{owner}/{repo}")
def github_repo(owner: str, repo: str) -> str:
    """GitHub repository resource."""
    return f"Repository: {owner}/{repo}"


@mcp.prompt(description="Code review prompt")
def review_code_prompt(language: str, code: str) -> str:
    """Generate a code review."""
    return f"Review this {language} code:\n{code}"


@mcp.completion()
async def handle_completion(
    ref: PromptReference | ResourceTemplateReference,
    argument: CompletionArgument,
    context: CompletionContext | None,
) -> Completion | None:
    """Provide completions for prompts and resources."""

    # Complete programming languages for the prompt
    if isinstance(ref, PromptReference):
        if ref.name == "review_code" and argument.name == "language":
            languages = ["python", "javascript", "typescript", "go", "rust"]
            return Completion(
                values=[lang for lang in languages if lang.startswith(argument.value)],
                hasMore=False,
            )

    # Complete repository names for GitHub resources
    if isinstance(ref, ResourceTemplateReference):
        if ref.uri == "github://repos/{owner}/{repo}" and argument.name == "repo":
            if context and context.arguments and context.arguments.get("owner") == "modelcontextprotocol":
                repos = ["python-sdk", "typescript-sdk", "specification"]
                return Completion(values=repos, hasMore=False)

    return None

@mcp.tool()
def hello(name: str = "World") -> str:
    """Say hello to someone."""
    return f"Hello, {name}!"

class BookingPreferences(BaseModel):
    """Schema for collecting user preferences."""

    checkAlternative: bool = Field(description="Would you like to check another date?")
    alternativeDate: str = Field(
        default="2024-12-26",
        description="Alternative date (YYYY-MM-DD)",
    )


@mcp.tool()
async def book_table(
    date: str,
    time: str,
    party_size: int,
    ctx: Context,
) -> str:
    """Book a table with date availability check."""
    # Check if date is available
    if date == "2024-12-25":
        # Date unavailable - ask user for alternative
        result = await ctx.elicit(
            message=(f"No tables available for {party_size} on {date}. Would you like to try another date?"),
            schema=BookingPreferences,
        )

        if result.action == "accept" and result.data:
            if result.data.checkAlternative:
                return f"[SUCCESS] Booked for {result.data.alternativeDate}"
            return "[CANCELLED] No booking made"
        return "[CANCELLED] Booking cancelled"

    # Date available
    return f"[SUCCESS] Booked for {date} at {time}"

# Add an addition tool
@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b


# Add a dynamic greeting resource
@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    """Get a personalized greeting"""
    return f"Hello, {name}!"


# Add a prompt
@mcp.prompt()
def greet_user(name: str, style: str = "friendly") -> str:
    """Generate a greeting prompt"""
    styles = {
        "friendly": "Please write a warm, friendly greeting",
        "formal": "Please write a formal, professional greeting",
        "casual": "Please write a casual, relaxed greeting",
    }

    return f"{styles.get(style, styles['friendly'])} for someone named {name}."

@mcp.tool()
def create_thumbnail(image_path: str) -> Image:
    """Create a thumbnail from an image"""
    img = PILImage.open(image_path)
    img.thumbnail((100, 100))
    return Image(data=img.tobytes(), format="png")

@mcp.tool()
async def process_data(data: str, ctx: Context) -> str:
    """Process data with logging."""
    # Different log levels
    await ctx.debug(f"Debug: Processing '{data}'")
    await ctx.info("Info: Starting processing")
    await ctx.warning("Warning: This is experimental")
    await ctx.error("Error: (This is just a demo)")

    # Notify about resource changes
    await ctx.session.send_resource_list_changed()

    return f"Processed: {data}"

@mcp.tool()
async def generate_poem(topic: str, ctx: Context) -> str:
    """Generate a poem using LLM sampling."""
    prompt = f"Write a short poem about {topic}"

    result = await ctx.session.create_message(
        messages=[
            SamplingMessage(
                role="user",
                content=TextContent(type="text", text=prompt),
            )
        ],
        max_tokens=100,
    )

    if result.content.type == "text":
        return result.content.text
    return str(result.content)


# Using Pydantic models for rich structured data
class WeatherData(BaseModel):
    """Weather information structure."""

    temperature: float = Field(description="Temperature in Celsius")
    humidity: float = Field(description="Humidity percentage")
    condition: str
    wind_speed: float


@mcp.tool()
async def get_weather_structured(city: str) -> WeatherData:
    """Get weather for a city - returns structured data."""
    try:
        # Load cached cities data
        df = _load_cities_data()
        city_lower = city.lower()

        # Find matching city
        city_match = df[df['city_ascii_lower'] == city_lower]

        if city_match.empty:
            # Return default weather data when city is not found
            return WeatherData(
                temperature=22.0,
                humidity=50.0,
                condition="unknown",
                wind_speed=5.0,
            )

        # Get the first match (in case of duplicates)
        city_row = city_match.iloc[0]
        lat = float(city_row['lat'])
        lng = float(city_row['lng'])

        # Call Open-Meteo API with more weather parameters
        api_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lng}&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code"
        logger.info(f"🔍 Calling Open-Meteo API: {api_url}")
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                if response.status == 200:
                    data = await response.json()
                    current = data['current']

                    # Extract weather data
                    temperature = float(current.get('temperature_2m', 25.0))
                    humidity = float(current.get('relative_humidity_2m', 50.0))
                    wind_speed = float(current.get('wind_speed_10m', 5.0))
                    weather_code = current.get('weather_code', 0)

                    # Convert weather code to condition
                    condition = _weather_code_to_condition(weather_code)
                    logger.info(f"🔍 Weather data: {temperature}, {humidity}, {condition}, {wind_speed}")
                    return WeatherData(
                        temperature=temperature,
                        humidity=humidity,
                        condition=condition,
                        wind_speed=wind_speed,
                    )
                else:
                    # Return default weather data when API fails
                    return WeatherData(
                        temperature=25.0,
                        humidity=50.0,
                        condition="unknown",
                        wind_speed=5.0,
                    )

    except Exception:
        # Return default weather data for any errors
        return WeatherData(
            temperature=25.0,
            humidity=50.0,
            condition="unknown",
            wind_speed=5.0,
        )


# Using TypedDict for simpler structures
class LocationInfo(TypedDict):
    latitude: float
    longitude: float
    name: str


@mcp.tool()
def get_location(city: str) -> LocationInfo:
    """Get location coordinates for a city using the world cities database."""
    try:
        # Load cached cities data
        df = _load_cities_data()
        city_lower = city.lower()

        # Find matching city
        city_match = df[df['city_ascii_lower'] == city_lower]

        if city_match.empty:
            # Return default coordinates (London) when city is not found
            return LocationInfo(
                latitude=51.5074,
                longitude=-0.1278,
                name=f"{city} (not found - showing London)"
            )

        # Get the first match (in case of duplicates)
        city_row = city_match.iloc[0]
        lat = float(city_row['lat'])
        lng = float(city_row['lng'])
        country = city_row['country']
        found_city = city_row['city_ascii']

        return LocationInfo(
            latitude=lat,
            longitude=lng,
            name=f"{found_city}, {country}"
        )

    except Exception:
        # Return default coordinates on any error
        return LocationInfo(
            latitude=51.5074,
            longitude=-0.1278,
            name=f"{city} (error occurred - showing London)"
        )


# Using dict[str, Any] for flexible schemas
@mcp.tool()
def get_statistics(data_type: str) -> dict[str, float]:
    """Get various statistics"""
    return {"mean": 42.5, "median": 40.0, "std_dev": 5.2}


# Ordinary classes with type hints work for structured output
class UserProfile:
    name: str
    age: int
    email: str | None = None

    def __init__(self, name: str, age: int, email: str | None = None):
        self.name = name
        self.age = age
        self.email = email


@mcp.tool()
def get_user(user_id: str) -> UserProfile:
    """Get user profile - returns structured data"""
    return UserProfile(name="Alice", age=30, email="alice@example.com")


# Classes WITHOUT type hints cannot be used for structured output
class UntypedConfig:
    def __init__(self, setting1, setting2):
        self.setting1 = setting1
        self.setting2 = setting2


@mcp.tool()
def get_config() -> UntypedConfig:
    """This returns unstructured output - no schema generated"""
    return UntypedConfig("value1", "value2")

@mcp.tool()
def sum_of_array(array: list[int]) -> int:
    """Sum of array"""
    return sum(array)


@mcp.tool()
async def get_weather_array(array: list[str]) -> str:
    """Get weather for multiple cities - returns structured data. Input should
    be a list of city names . example input: ['London', 'Paris', 'Tokyo']"""
    weather_output = ''
    for city in array:
        weather_output += await get_weather(city) + '\n'
    return weather_output


@mcp.tool()
async def get_weather_json(json_data: dict[str, Any]) -> str:
    """Get weather for multiple cities from JSON input. Each city can have location and unit settings.
    Example: {'pune':{'location':1,'unit':'celsius'},'mumbai':{'location':0,'unit':'fahrenheit'}}"""
    weather_results = []

    # Load cities data once for all cities
    df = _load_cities_data()

    for city_name, city_config in json_data.items():
        try:
            # Extract configuration
            location_flag = city_config.get('location', 0)  # Default to 0 (no location)
            unit = city_config.get('unit', 'celsius')  # Default to celsius

            city_lower = city_name.lower()

            # Find matching city
            city_match = df[df['city_ascii_lower'] == city_lower]

            if city_match.empty:
                # Return default temperature when city is not found
                default_temp = 22.0
                temp_unit = "°C"
                if unit.lower() == "fahrenheit":
                    default_temp = (default_temp * 9/5) + 32
                    temp_unit = "°F"

                result = f"Weather in {city_name}: {default_temp}{temp_unit} (default - city not found)"
                if location_flag == 1:
                    result += f" | Location: {city_name} (not found)"
                weather_results.append(result)
                continue

            # Get the first match (in case of duplicates)
            city_row = city_match.iloc[0]
            lat = float(city_row['lat'])
            lng = float(city_row['lng'])
            found_city = city_row['city_ascii']
            country = city_row['country']

            # Call Open-Meteo API
            api_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lng}&current=temperature_2m"

            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as response:
                    if response.status == 200:
                        data = await response.json()

                        # Extract temperature
                        current_temp = data['current']['temperature_2m']
                        temp_unit = data['current_units']['temperature_2m']
                        timezone = data['timezone']
                        time = data['current']['time']

                        # Convert temperature if needed
                        if unit.lower() == "fahrenheit":
                            if temp_unit == "°C":
                                current_temp = (current_temp * 9/5) + 32
                                temp_unit = "°F"

                        result = f"Weather in {found_city}: {current_temp}{temp_unit} (as of {time} {timezone})"
                        if location_flag == 1:
                            result += f" | Location: {found_city}, {country} (Lat: {lat}, Lng: {lng})"
                        weather_results.append(result)
                    else:
                        # Return default temperature when API fails
                        default_temp = 25.0
                        temp_unit = "°C"
                        if unit.lower() == "fahrenheit":
                            default_temp = (default_temp * 9/5) + 32
                            temp_unit = "°F"
                        result = f"Weather in {found_city}: {default_temp}{temp_unit} (default - API unavailable)"
                        if location_flag == 1:
                            result += f" | Location: {found_city}, {country} (Lat: {lat}, Lng: {lng})"
                        weather_results.append(result)

        except Exception:
            # Return default temperature for any errors
            default_temp = 25.0
            temp_unit = "°C"
            if city_config.get('unit', 'celsius').lower() == "fahrenheit":
                default_temp = (default_temp * 9/5) + 32
                temp_unit = "°F"
            result = f"Weather in {city_name}: {default_temp}{temp_unit} (error occurred)"
            if city_config.get('location', 0) == 1:
                result += f" | Location: {city_name} (error)"
            weather_results.append(result)

    return '\n'.join(weather_results)


# Lists and other types are wrapped automatically
@mcp.tool()
def list_cities() -> list[str]:
    """Get a list of cities"""
    return ["London", "Paris", "Tokyo"]
    # Returns: {"result": ["London", "Paris", "Tokyo"]}



@mcp.tool()
async def long_running_task(task_name: str, ctx: Context, steps: int = 5) -> str:
    """Execute a task with progress updates."""
    await ctx.info(f"Starting: {task_name}")

    for i in range(steps):
        progress = (i + 1) / steps
        await ctx.report_progress(
            progress=progress,
            total=1.0,
            message=f"Step {i + 1}/{steps}",
        )
        await ctx.debug(f"Completed step {i + 1}")

    return f"Task '{task_name}' completed"

@mcp.tool()
def get_current_time(timezone_name: str = "UTC") -> str:
    """Get current time in specified timezone."""
    try:
        # Handle common timezone abbreviations
        timezone_map = {
            "UTC": "UTC",
            "GMT": "GMT",
            "EST": "US/Eastern",
            "PST": "US/Pacific",
            "CST": "US/Central",
            "MST": "US/Mountain",
            "IST": "Asia/Kolkata",
            "JST": "Asia/Tokyo",
            "CET": "Europe/Berlin",
            "BST": "Europe/London"
        }

        # Use mapped timezone or the provided one
        tz_name = timezone_map.get(timezone_name.upper(), timezone_name)

        if tz_name == "UTC":
            current_time = datetime.now(timezone.utc)
            formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S UTC")
        else:
            try:
                tz = pytz.timezone(tz_name)
                current_time = datetime.now(tz)
                tz_name_str = current_time.tzinfo.tzname(current_time) if current_time.tzinfo else tz_name
                formatted_time = current_time.strftime(f"%Y-%m-%d %H:%M:%S {tz_name_str}")
            except pytz.exceptions.UnknownTimeZoneError:
                # Fallback to UTC if timezone is invalid
                current_time = datetime.now(timezone.utc)
                formatted_time = f"{current_time.strftime('%Y-%m-%d %H:%M:%S UTC')} (Invalid timezone '{timezone_name}', showing UTC)"

        return formatted_time

    except Exception:
        # Fallback to UTC on any error
        current_time = datetime.now(timezone.utc)
        return f"{current_time.strftime('%Y-%m-%d %H:%M:%S UTC')} (Error occurred)"


@mcp.tool()
def convert_time(time_str: str, from_timezone: str, to_timezone: str) -> str:
    """Convert time from one timezone to another."""
    try:
        # Handle common timezone abbreviations
        timezone_map = {
            "UTC": "UTC",
            "GMT": "GMT",
            "EST": "US/Eastern",
            "PST": "US/Pacific",
            "CST": "US/Central",
            "MST": "US/Mountain",
            "IST": "Asia/Kolkata",
            "JST": "Asia/Tokyo",
            "CET": "Europe/Berlin",
            "BST": "Europe/London"
        }

        # Map timezone names
        from_tz_name = timezone_map.get(from_timezone.upper(), from_timezone)
        to_tz_name = timezone_map.get(to_timezone.upper(), to_timezone)

        # Parse the input time string (supports various formats)
        time_formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%H:%M:%S",
            "%H:%M",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d %H:%M",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M"
        ]

        parsed_time = None
        for fmt in time_formats:
            try:
                parsed_time = datetime.strptime(time_str, fmt)
                break
            except ValueError:
                continue

        if parsed_time is None:
            return f"Error: Unable to parse time '{time_str}'. Supported formats: YYYY-MM-DD HH:MM:SS, HH:MM:SS, etc."

        # Handle timezone conversion
        if from_tz_name == "UTC":
            from_tz = timezone.utc
            localized_time = parsed_time.replace(tzinfo=from_tz)
        else:
            try:
                from_tz = pytz.timezone(from_tz_name)
                localized_time = from_tz.localize(parsed_time)  # type: ignore[attr-defined]
            except pytz.exceptions.UnknownTimeZoneError:
                return f"Error: Unknown source timezone '{from_timezone}'"

        if to_tz_name == "UTC":
            to_tz = timezone.utc
            converted_time = localized_time.astimezone(to_tz)
            result = converted_time.strftime("%Y-%m-%d %H:%M:%S UTC")
        else:
            try:
                to_tz = pytz.timezone(to_tz_name)
                converted_time = localized_time.astimezone(to_tz)
                tz_name_str = converted_time.tzinfo.tzname(converted_time) if converted_time.tzinfo else to_tz_name
                result = converted_time.strftime(f"%Y-%m-%d %H:%M:%S {tz_name_str}")
            except pytz.exceptions.UnknownTimeZoneError:
                return f"Error: Unknown target timezone '{to_timezone}'"

        return f"{time_str} {from_timezone} → {result}"

    except Exception as e:
        return f"Error converting time: {str(e)}"


@mcp.tool()
def roll_dice(num_dice: int = 1, num_sides: int = 6) -> str:
    """Roll dice with specified number of dice and sides."""
    try:
        # Validate inputs
        if num_dice < 1:
            return "Error: Number of dice must be at least 1"
        if num_dice > 100:
            return "Error: Maximum 100 dice allowed"
        if num_sides < 2:
            return "Error: Number of sides must be at least 2"
        if num_sides > 1000:
            return "Error: Maximum 1000 sides allowed"

        # Roll the dice
        rolls = []
        for _ in range(num_dice):
            roll = random.randint(1, num_sides)
            rolls.append(roll)

        # Calculate total
        total = sum(rolls)

        # Format the result
        if num_dice == 1:
            return f"🎲 Rolled 1d{num_sides}: {rolls[0]}"
        else:
            rolls_str = ", ".join(str(roll) for roll in rolls)
            return f"🎲 Rolled {num_dice}d{num_sides}: [{rolls_str}] = {total}"

    except Exception as e:
        return f"Error rolling dice: {str(e)}"


def parse_args():
    """Parse command line arguments for transport selection."""
    parser = argparse.ArgumentParser(
        description="All Feature MCP Server - Comprehensive MCP features demonstration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Transport types:
  stdio           Standard input/output transport (for CLI/subprocess usage)
  sse             Server-Sent Events transport (HTTP-based, legacy)
  streamable-http Streamable HTTP transport (default, recommended)

Examples:
  python all_feature_server.py                      # Default: streamable-http on port 8000
  python all_feature_server.py --transport stdio    # Run with stdio transport
  python all_feature_server.py --transport sse      # Run with SSE transport
  python all_feature_server.py --port 9000          # Custom port for HTTP transports
        """
    )
    parser.add_argument(
        "--transport", "-t",
        choices=["stdio", "sse", "streamable-http"],
        default="streamable-http",
        help="Transport type to use (default: streamable-http)"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to for HTTP transports (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8000,
        help="Port to listen on for HTTP transports (default: 8000)"
    )
    return parser.parse_args()


def run_stdio():
    """Run the server with stdio transport."""
    logger.info("[all_feature_server] Starting All Feature MCP Server with stdio transport")
    mcp.run(transport="stdio")


def run_sse(host: str, port: int):
    """Run the server with SSE transport."""
    import uvicorn
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Mount

    logger.info(f"[all_feature_server] Starting All Feature MCP Server with SSE transport on {host}:{port}")

    sse_app = Starlette(
        routes=[
            Mount("/", mcp.sse_app()),
        ],
    )

    # Add health check endpoint
    @sse_app.route("/health")
    async def health_check(request):
        return JSONResponse({"status": "healthy", "service": "all_feature_server", "transport": "sse"})

    uvicorn.run(sse_app, host=host, port=port)


def run_streamable_http(host: str, port: int):
    """Run the server with streamable-http transport."""
    import uvicorn
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Mount

    logger.info(f"[all_feature_server] Starting All Feature MCP Server with streamable-http transport on {host}:{port}")

    http_app = Starlette(
        routes=[
            Mount("/", mcp.streamable_http_app()),
        ],
    )

    # Add health check endpoint
    @http_app.route("/health")
    async def health_check(request):
        return JSONResponse({"status": "healthy", "service": "all_feature_server", "transport": "streamable-http"})

    uvicorn.run(http_app, host=host, port=port)


# Run server with configurable transport
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    args = parse_args()

    print("🚀 Starting All Feature MCP Server...")
    print("📊 Comprehensive demonstration of MCP protocol features")
    print("🔧 Features: Tools, Resources, Prompts, Sampling, Elicitation")
    print("🌍 Weather API, Time zones, Dice rolling, and more")
    print(f"🔌 Transport: {args.transport}")
    print("=" * 60)

    if args.transport == "stdio":
        run_stdio()
    elif args.transport == "sse":
        run_sse(args.host, args.port)
    else:  # streamable-http (default)
        run_streamable_http(args.host, args.port)
