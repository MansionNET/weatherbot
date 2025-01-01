#!/usr/bin/env python3
"""
MansionNet Weather Bot
A simple IRC bot that provides weather information using the Open-Meteo API
"""

import socket
import ssl
import requests
import time
from datetime import datetime

class WeatherBot:
    def __init__(self):
        # IRC Server Configuration
        self.server = "irc.server.com"
        self.port = 6697  # SSL port
        self.nickname = "WeatherBot"
        self.channels = ["#help", "#welcome"]  # List of channels to join
        
        # Initialize SSL context for secure connection
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        
    def connect(self):
        """Establish connection to the IRC server"""
        # Create socket and wrap with SSL
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.irc = self.ssl_context.wrap_socket(sock)
        
        print(f"Connecting to {self.server}:{self.port}...")
        self.irc.connect((self.server, self.port))
        
        # Register with the IRC server
        self.send(f"NICK {self.nickname}")
        self.send(f"USER {self.nickname} 0 * :MansionNet Weather Information Bot")
        
        # Wait for registration to complete
        buffer = ""
        registered = False
        while not registered:
            try:
                temp = self.irc.recv(2048).decode("UTF-8")
                print("Received:", temp)  # Debug print
                buffer += temp
                
                # Handle ping during registration
                if "PING" in buffer:
                    ping_token = buffer[buffer.find("PING"):].split()[1]
                    self.send(f"PONG {ping_token}")
                    print(f"Responded to PING with: PONG {ping_token}")
                
                # Look for successful registration
                if "001" in buffer:
                    print("Successfully registered!")
                    registered = True
                    break
                    
                # Check for registration timeout
                if "Closing Link" in buffer or "ERROR" in buffer:
                    print("Registration failed, retrying...")
                    time.sleep(5)
                    return False
                    
            except UnicodeDecodeError:
                buffer = ""
                continue
            except Exception as e:
                print(f"Error during registration: {str(e)}")
                time.sleep(5)
                return False
        
        # Now join all configured channels
        for channel in self.channels:
            print(f"Joining channel {channel}")
            self.send(f"JOIN {channel}")
            time.sleep(1)  # Small delay between joins to prevent flooding

        return True

    def send(self, message):
        """Send a raw message to the IRC server"""
        print(f"Sending: {message}")  # Debug print
        self.irc.send(bytes(f"{message}\r\n", "UTF-8"))

    def send_message(self, target, message):
        """Send a message to a specific channel or user"""
        self.send(f"PRIVMSG {target} :{message}")

    def get_coordinates(self, city):
        """Get latitude and longitude for a city using the Geocoding API"""
        try:
            url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=en&format=json"
            response = requests.get(url)
            data = response.json()
            
            if response.status_code == 200 and data.get('results'):
                location = data['results'][0]
                return {
                    'lat': location['latitude'],
                    'lon': location['longitude'],
                    'name': location['name'],
                    'country': location['country']
                }
            return None
        except Exception as e:
            print(f"Geocoding error: {str(e)}")
            return None

    def get_weather(self, city):
        """Get weather information for a city using Open-Meteo API"""
        try:
            # First get coordinates
            location = self.get_coordinates(city)
            if not location:
                return f"Could not find location: {city}"

            # Get weather data
            url = f"https://api.open-meteo.com/v1/forecast?latitude={location['lat']}&longitude={location['lon']}&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code"
            response = requests.get(url)
            
            if response.status_code == 200:
                data = response.json()
                current = data['current']
                
                # Weather code to description mapping
                weather_codes = {
                    0: "Clear sky",
                    1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
                    45: "Foggy", 48: "Depositing rime fog",
                    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
                    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
                    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
                    77: "Snow grains",
                    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
                    85: "Slight snow showers", 86: "Heavy snow showers",
                    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail"
                }
                
                weather_desc = weather_codes.get(current['weather_code'], "Unknown")
                
                return (f"Weather in {location['name']}, {location['country']}: "
                       f"{weather_desc}, "
                       f"Temperature: {current['temperature_2m']}°C, "
                       f"Humidity: {current['relative_humidity_2m']}%, "
                       f"Wind: {current['wind_speed_10m']} km/h")
            else:
                return f"Could not fetch weather data for {city}"
                
        except Exception as e:
            return f"Error fetching weather data: {str(e)}"

    def run(self):
        """Main bot loop"""
        while True:
            try:
                if self.connect():
                    buffer = ""
                    
                    while True:
                        try:
                            # Receive and process IRC messages
                            buffer += self.irc.recv(2048).decode("UTF-8")
                            lines = buffer.split("\r\n")
                            buffer = lines.pop()
                            
                            for line in lines:
                                print(line)  # Debug output
                                
                                # Keep connection alive by responding to PINGs
                                if line.startswith("PING"):
                                    ping_token = line.split()[1]
                                    self.send(f"PONG {ping_token}")
                                
                                # Process channel messages
                                if "PRIVMSG" in line:
                                    # Extract the target channel from the message
                                    parts = line.split()
                                    target_channel = parts[2]
                                    
                                    # Only process messages sent to our channels
                                    if target_channel in self.channels:
                                        sender = line.split("!")[0][1:]
                                        message = line.split("PRIVMSG")[1].split(":", 1)[1].strip()
                                        print(f"Received message from {sender} in {target_channel}: {message}")
                                        
                                        # Handle weather command
                                        if message.startswith("!weather"):
                                            parts = message.split()
                                            if len(parts) > 1:
                                                city = " ".join(parts[1:])
                                                weather = self.get_weather(city)
                                                self.send_message(target_channel, weather)
                                            else:
                                                self.send_message(target_channel, "Usage: !weather <city>")
                                        
                                        # Handle help command
                                        elif message == "!help":
                                            help_msg = "MansionNet Weather Bot | Commands: !weather <city> - Get weather information for a city"
                                            self.send_message(target_channel, help_msg)
                                    
                        except UnicodeDecodeError:
                            buffer = ""
                            continue
                            
            except Exception as e:
                print(f"Error: {str(e)}")
                time.sleep(30)
                continue

if __name__ == "__main__":
    bot = WeatherBot()
    bot.run()