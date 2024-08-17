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

# Function to extract participants' information
def ai_extract_participants(description):
    prompt = f"""
    Extract the participants' names and emails from the following event description. Return the result as a json of dictionaries, where each dictionary contains a "name" as a key and an "email" as a value. If the email is not available, set the value of "email" to None.
    For example:
    - If the input is "Alice will attend the meeting", return {{\"participants\": [{{\"name\": \"Alice\", \"email\": null}}]}}.
    - If the input is "Alice (alice@example.com) and Bob will attend the meeting", return {{\"participants\": [{{\"name\": \"Alice\", \"email\": \"alice@example.com\"}}, {{\"name\": \"Bob\", \"email\": null}}]}}.
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": description}
        ],
        response_format={"type": "json_object"}
    )

    return response.choices[0].message.content

# Function to validate and process participants' information
def process_participants_valid_mail(json_string):
    """
    Convert the JSON string to a dictionary, validate its format, and place participants with emails into a dictionary, while those without emails are placed in a list.
    Parameters:
    - json_string: A JSON string containing participants' information
    """
    try:
        # Convert JSON string to dictionary
        data = json.loads(json_string)
        
        # Validate that the top-level structure is a dictionary and contains the "participants" key
        if not isinstance(data, dict) or "participants" not in data:
            raise ValueError("Invalid JSON format, top-level must be a dictionary containing the 'participants' key")

        participants = data["participants"]
        
        # Validate that "participants" is a list
        if not isinstance(participants, list):
            raise ValueError("The 'participants' key's value must be a list")

        # Prepare two containers
        emails_dict = {}
        names_without_valid_email = []

        # Process each participant
        for participant in participants:
            # Validate that each participant is a dictionary and contains the "name" key
            if not isinstance(participant, dict) or "name" not in participant:
                raise ValueError("Each participant must be a dictionary containing the 'name' key")

            name = participant["name"]
            email = participant.get("email")

            if email and EmailStr._validate(email):  # If email exists and validation passes
                emails_dict[name] = email
            else:  # If no email or validation fails
                names_without_valid_email.append(name)

        return emails_dict, names_without_valid_email

    except json.JSONDecodeError:
        raise ValueError("Failed to parse JSON string")
    except Exception as e:
        raise ValueError(f"Error processing participants: {e}")

# Convert OpenAI's structured output to API-compliant event_data
def build_event_data(parsed_event, emails_dict):
    json_parsed_event = json.loads(parsed_event)
    start_time = standardize_time(json_parsed_event['when'])  # Use standardized time
    participants = [{"name": name, "email": email} for name, email in emails_dict.items()]
    event_data = {
        "title": json_parsed_event['title'],
        "status": "confirmed",
        "busy": True,
        "participants": participants,
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

    # Example event description generated by OpenAI
    description = "2024年8月17日下午3点你有空吗？我们约一个小时catchup一下ai文件管理的事,地点在Blue Bottle 1385 4th St, San Francisco, CA 94158，关于。和Alice一起。test2@user.io"
    parsed_event = parse_event_description(description)
    
    # Extract participants using OpenAI
    extracted_participants_raw = ai_extract_participants(description)
    # Validate and process participants' information
    emails, no_emails = process_participants_valid_mail(extracted_participants_raw)

    # Build event data
    event_data = build_event_data(parsed_event, emails)

    # Create a new event
    new_event = create_event(grant_id, api_key, calendar_id=CALENDAR_ID, event_data=event_data)
    print("New Event:", new_event)

# Run the test function
calendar_test()
