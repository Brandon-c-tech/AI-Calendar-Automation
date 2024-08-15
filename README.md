# AI-Calendar-Automation

## Overview
**AI-Calendar-Automation** is a Python tool designed to automate the management of calendar events using the Nylas API and OpenAI. This project allows users to retrieve, create, and manage events programmatically, leveraging AI to generate event details.

## Features
- **Retrieve Calendars**: Fetch all calendars associated with a Nylas account.
- **Retrieve Events**: Retrieve events from a specific calendar with customizable limits.
- **Create Events**: Automatically create events on your calendar using AI-generated data.
- **AI Integration**: Utilize OpenAI to parse natural language descriptions into structured event data.

## Installation
1. Clone the repository:
    ```bash
    git clone https://github.com/Brandon-c-tech/AI-Calendar-Automation.git
    ```
2. Navigate to the project directory:
    ```bash
    cd AI-Calendar-Automation
    ```
3. Install the required dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Usage
1. **Configure API Parameters**: Replace `<GRANT_ID>`, `<API_KEY>`, and `<CALENDAR_ID>` in the code with your actual Nylas API credentials.
2. **Run the Script**: Execute the script to interact with your calendar:
    ```bash
    python your_script_name.py
    ```
3. **Example**: The script provides functions to:
    - Fetch calendars.
    - Fetch a list of events from a calendar.
    - Create new calendar events based on AI-generated input.

## Example Code
```python
# Example usage
def calendar_test():
    calendars = get_calendars(GRANT_ID, API_KEY)
    print("Calendars:", calendars)

    events = get_events(GRANT_ID, API_KEY, CALENDAR_ID, limit=5)
    print("Events:", events)

    description = "Alice and Bob are going to a science fair on Friday."
    parsed_event = parse_event_description(description)

    event_data = build_event_data(parsed_event)

    new_event = create_event(GRANT_ID, API_KEY, CALENDAR_ID, event_data)
    print("New Event:", new_event)
