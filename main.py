import requests
import json
from pydantic import BaseModel
from openai import OpenAI
from datetime import datetime
import time
from dateutil import parser
import pytz

# API configuration parameters
GRANT_ID = "<GRANT_ID>"
API_KEY = "<API_KEY>"
CALENDAR_ID = "<CALENDAR_ID>"

# Function to retrieve all calendars
def get_calendars(grant_id, api_key):
    url = f'https://api.us.nylas.com/v3/grants/{grant_id}/calendars'
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    response = requests.get(url, headers=headers)
    return response.json()

# Function to retrieve events from a specific calendar
def get_events(grant_id, api_key, calendar_id, limit=5):
    url = f'https://api.us.nylas.com/v3/grants/{grant_id}/events?calendar_id={calendar_id}&limit={limit}'
    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    response = requests.get(url, headers=headers)
    return response.json()

# Function to create a new event
def create_event(grant_id, api_key, calendar_id, event_data):
    url = f'https://api.us.nylas.com/v3/grants/{grant_id}/events?calendar_id={calendar_id}'
    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    response = requests.post(url, headers=headers, data=json.dumps(event_data))
    return response.json()

# Define structured event model
class CalendarEvent(BaseModel):
    title: str
    description: str
    when: str
    location: str
    participants: list[str]

# Initialize OpenAI client
client = OpenAI()

# Parse the OpenAI output into a CalendarEvent
def parse_event_description(description):
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Extract the event details based on the following structure: title, description, when, location, and participants. Please ensure WHEN is a date or time description that can be converted into a standard date format. Missing parts fill with 'unknown'"},
            {"role": "user", "content": description},
        ],
        response_format=CalendarEvent,
    )
    return completion.choices[0].message.content

# (TBD) Standardize time and convert it to a UNIX timestamp (Pacific Time)
def standardize_time(time_str):
    # Parse the time string using dateutil's parser
    parsed_time = parser.parse(time_str, fuzzy=True)
    # Define the Pacific Time timezone
    pacific = pytz.timezone('America/Los_Angeles')
    # Localize the parsed time to Pacific Time
    pacific_time = pacific.localize(parsed_time)
    # Convert to UTC time
    utc_time = pacific_time.astimezone(pytz.utc)
    # Convert to UNIX timestamp
    unix_timestamp = int(utc_time.timestamp())
    return unix_timestamp

# Convert the OpenAI structured output into API-compatible event_data
def build_event_data(parsed_event):
    json_parsed_event = json.loads(parsed_event)
    start_time = standardize_time(json_parsed_event['when'])  # Use standardized time
    event_data = {
        "title": json_parsed_event['title'],
        "status": "confirmed",
        "busy": True,
        "participants": [{"name": "test user", "email": "test@user.io"}], # TBD
        "description": json_parsed_event['description'],
        "when": {
            "object": "timespan",
            "start_time": start_time,  
            "end_time": start_time + 3600  # TBD
        },
        "location": json_parsed_event['location']
    }
    return event_data

# Example usage
def calendar_test():
    # Retrieve calendars
    calendars = get_calendars(grant_id, api_key)
    print("Calendars:", calendars)
    # Retrieve events
    events = get_events(grant_id, api_key, calendar_id, limit=5)
    print("Events:", events)
    # Use OpenAI to generate event description
    description = "Insights Sharing: Alice and Bob are going to a Kindred meeting room chat with Uber CEO on 8月16日 2024 5:00pm. signed a NDA"
    parsed_event = parse_event_description(description)
    # Build event data
    event_data = build_event_data(parsed_event)
    # Create new event
    new_event = create_event(grant_id, api_key, calendar_id="brandon.ch.thu@gmail.com", event_data=event_data)
    print("New Event:", new_event)

# Run the test function
calendar_test()
