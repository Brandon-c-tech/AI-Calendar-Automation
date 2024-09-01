import requests
import json
from pydantic import BaseModel, EmailStr, ValidationError
from openai import OpenAI
from datetime import datetime
import time
from dateutil import parser
import pytz
from typing import List, Dict
from icalendar import Calendar, Event

# API configuration parameters
GRANT_ID = "<GRANT_ID>"
API_KEY = "<API_KEY>"
CALENDAR_ID = "<CALENDAR_ID>"

# NylasAPI class handles interactions with the Nylas API, such as retrieving calendars and creating events
class NylasAPI:
    def __init__(self, grant_id: str, api_key: str):
        self.grant_id = grant_id
        self.api_key = api_key

    def _get_headers(self) -> Dict[str, str]:
        # Returns the necessary headers for authentication with the Nylas API
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

    def get_calendars(self) -> List[Dict]:
        # Fetches all calendars associated with the grant ID
        url = f'https://api.us.nylas.com/v3/grants/{self.grant_id}/calendars'
        response = requests.get(url, headers=self._get_headers())
        return response.json()

    def get_events(self, calendar_id: str, limit=5) -> List[Dict]:
        # Fetches the latest events from a specific calendar
        url = f'https://api.us.nylas.com/v3/grants/{self.grant_id}/events?calendar_id={calendar_id}&limit={limit}'
        response = requests.get(url, headers=self._get_headers())
        return response.json()

    def create_event(self, calendar_id: str, event_data: Dict) -> Dict:
        # Creates a new event in the specified calendar
        url = f'https://api.us.nylas.com/v3/grants/{self.grant_id}/events?calendar_id={calendar_id}'
        response = requests.post(url, headers=self._get_headers(), data=json.dumps(event_data))
        return response.json()

# CalendarEvent model for storing event details, used in parsing responses from OpenAI
class CalendarEvent(BaseModel):
    title: str
    description: str
    when: str
    location: str
    participants: list[str]

# OpenAIClient class handles interactions with the OpenAI API, such as extracting event details and participants
class OpenAIClient:
    def __init__(self):
        self.client = OpenAI()

    def parse_event_description(self, description: str) -> Dict:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S") #TBD
        # Parses the event description to extract structured event details using OpenAI
        system_message = f"Extract the event details based on the following structure: title, description, when, location, and participants. The current date and time is {current_time}. Please ensure WHEN is a date or time description that can be converted into a standard date format. Missing parts fill with 'unknown'."
        completion = self.client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": description},
            ],
            response_format=CalendarEvent
        )
        return json.loads(completion.choices[0].message.content)

    def extract_participants(self, description: str) -> str:
        # Extracts participants' names and emails from the event description using OpenAI
        prompt = f"""
            Extract the participants' names and emails from the following event description. Return the result as a json of dictionaries, where each dictionary contains a "name" as a key and an "email" as a value. If the email is not available, set the value of "email" to None.
            For example:
            - If the input is "Alice will attend the meeting", return {{\"participants\": [{{\"name\": \"Alice\", \"email\": null}}]}}.
            - If the input is "Alice (alice@example.com) and Bob will attend the meeting", return {{\"participants\": [{{\"name\": \"Alice\", \"email\": \"alice@example.com\"}}, {{\"name\": \"Bob\", \"email\": null}}]}}.
        """

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": description}
            ],
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content

    def extract_event_end_time(self, description: str) -> str:
        pacific_tz = pytz.timezone('America/Los_Angeles')  # TBD to set user's timezone
        current_time = datetime.now(pacific_tz).strftime("%Y-%m-%d %H:%M:%S")
        prompt = f"""
            Extract the end time from the following event description. The current date and time is {current_time}. 
            If the end time is not explicitly mentioned, try to calculate it based on the current time and the duration mentioned in the description. 
            Return the result as a string in the JSON format {{"end_time": "YYYY-MM-DD HH:MM:SS"}}.
            If can't get the end time, return 'unknow'.
            For example:
            - If the input is "The current date is 2023-09-15. The meeting will start at 3 PM and end at 4 PM", return {{"end_time": "2023-09-15 16:00:00"}}.
            - If the input is "The meeting will last for 2 hours", and the current time is "2023-09-15 14:00:00", return {{"end_time": "2023-09-15 16:00:00"}}.
        """
        
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": description}
            ],
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content

# CalendarEventProcessor class processes event data and manages participants
class CalendarEventProcessor:
    def __init__(self, api_client: NylasAPI, openai_client: OpenAIClient):
        self.api_client = api_client
        self.openai_client = openai_client

    def standardize_time(self, time_str: str) -> int:
        # Converts a natural language time string into a standardized Unix timestamp in Pacific Time
        parsed_time = parser.parse(time_str, fuzzy=True)
        pacific = pytz.timezone('America/Los_Angeles')
        pacific_time = pacific.localize(parsed_time)
        utc_time = pacific_time.astimezone(pytz.utc)
        return int(utc_time.timestamp())

    def process_start_time(self, parsed_event: Dict):
        start_time = self.standardize_time(parsed_event['when'])
        return start_time
    
    def process_end_time(self, description: str, start_time: int) -> int:
        end_time_str = self.openai_client.extract_event_end_time(description)
        if end_time_str.lower() != 'unknown':
            try:
                end_time_timestamp = self.standardize_time(end_time_str)
                return end_time_timestamp
            except Exception as e:
                raise ValueError(f"Error standardizing end time: {e}")
        else:
            return start_time + 3600

    def process_participants(self, participants_json: str) -> (Dict[str, str], List[str]):
        # Processes participants JSON to extract emails and identify participants without valid emails
        try:
            data = json.loads(participants_json)
            participants = data["participants"]
            emails_dict = {}
            names_without_valid_email = []
            for participant in participants:
                name = participant["name"]
                email = participant.get("email")
                if email and EmailStr._validate(email):
                    emails_dict[name] = email
                else:
                    names_without_valid_email.append(name)
            return emails_dict, names_without_valid_email
        except json.JSONDecodeError:
            raise ValueError("Failed to parse JSON string")
        except Exception as e:
            raise ValueError(f"Error processing participants: {e}")

    def build_event_data(self, parsed_event: Dict, emails_dict: Dict[str, str], start_time: int, end_time: int) -> Dict:
        # Constructs the final event data dictionary for creating a new event in the calendar
        participants = [{"name": name, "email": email} for name, email in emails_dict.items()]
        event_data = {
            "title": parsed_event['title'],
            "status": "confirmed",
            "busy": True,
            "participants": participants,
            "description": parsed_event['description'],
            "when": {
                "object": "timespan",
                "start_time": start_time,
                "end_time": end_time
            },
            "location": parsed_event['location']
        }
        return event_data

# Generate an ICS file using the structured data
class ICSGenerator:
    def __init__(self):
        self.calendar = Calendar()

    def generate_event(self, event_data: Dict) -> Event:
        # Create an event and add it to the calendar
        event = Event()

        event.add('summary', event_data['title'])
        event.add('dtstart', self._parse_datetime(event_data['start_time']))
        event.add('dtend', self._parse_datetime(event_data['end_time']))
        event.add('location', event_data.get('location', ''))
        event.add('description', event_data.get('description', ''))

        for attendee in event_data.get('attendees', []):
            event.add('attendee', attendee)

        # Validate event logic (example: start time should be before end time)
        self._validate_event(event)

        self.calendar.add_component(event)
        return event

    def _parse_datetime(self, date_str: str) -> datetime:
        # Example parsing datetime with timezone, adjust according to your needs
        return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=pytz.utc)

    def _validate_event(self, event: Event):
        # Example of validating that the event start time is before the end time
        dtstart = event.get('dtstart').dt
        dtend = event.get('dtend').dt
        if dtstart >= dtend:
            raise ValueError("Event start time must be before end time")

    def save_to_file(self, filename: str):
        # Save the calendar to an .ics file
        with open(filename, 'wb') as f:
            f.write(self.calendar.to_ical())

# CalendarManager class integrates NylasAPI and CalendarEventProcessor to manage the overall process
class CalendarManager:
    def __init__(self, api_client: NylasAPI, event_processor: CalendarEventProcessor):
        self.api_client = api_client
        self.event_processor = event_processor

    def readable_event(self, event_data):
        # Extract relevant information
        title = event_data['data']['title']
        participants = [(p['name'], p['email']) for p in event_data['data']['participants']]
        start_time = datetime.fromtimestamp(event_data['data']['when']['start_time']).strftime('%Y-%m-%d %H:%M:%S')
        location = event_data['data']['location']
        description = event_data['data']['description']

        # Format the output
        output = f"Title: {title}\n" \
                 f"Participants:\n" + "\n".join([f"  Name: {name}, Email: {email}" for name, email in participants]) + "\n" \
                 f"Start Time (UTC): {start_time}\n" \ #TBD
                 f"Location: {location}\n" \
                 f"Description: {description}"
        
        return output

    def run_test(self):
        # Example method to demonstrate the workflow: retrieving calendars, processing events, and creating a new event
        calendars = self.api_client.get_calendars()
        print("Calendars:", calendars)
        events = self.api_client.get_events(calendar_id="brandon.ch.thu@gmail.com", limit=5)
        print("Events:", events)

        # Example event description for testing
        description = "Hey, you free Aug 17, 2024, around 1? Thinking we could grab an hour, talking AI file management stuff. Wanna meet at Blue Bottle, you know, the one at 1385 4th St in San Francisco, CA 94158? Alice Wang's gonna join his mail -> test@user.io"
        
        # Parse the event description using OpenAI
        parsed_event = self.event_processor.openai_client.parse_event_description(description)
        # Extract and process participants from the event description
        extracted_participants_raw = self.event_processor.openai_client.extract_participants(description)
        emails, no_emails = self.event_processor.process_participants(extracted_participants_raw)
        # Extract start and end time
        start_time = self.event_processor.process_start_time(parsed_event)
        end_time = self.event_processor.process_end_time(description, start_time)

        # Build the event data and create the new event
        event_data = self.event_processor.build_event_data(parsed_event, emails, start_time, end_time)
        new_event = self.api_client.create_event(calendar_id="brandon.ch.thu@gmail.com", event_data=event_data)
        print("New Event:", new_event)

        # Format the event readable details and print
        formatted_event_details = self.readable_event(new_event)
        print("Readable Event Details:\n", formatted_event_details)

# Usage
if __name__ == "__main__":
    api_client = NylasAPI(grant_id=GRANT_ID, api_key=API_KEY)
    openai_client = OpenAIClient()
    event_processor = CalendarEventProcessor(api_client, openai_client)
    manager = CalendarManager(api_client, event_processor)
    manager.run_test()
