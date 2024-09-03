# AI-Calendar-Automation

## Overview
**AI-Calendar-Automation** is a Python tool designed to automate the management of calendar events using the Nylas API and OpenAI. This project allows users to retrieve, create, and manage events programmatically, leveraging AI to generate event details.

## Features
- **Retrieve Calendars**: Fetch all calendars associated with a Nylas account.
- **Retrieve Events**: Retrieve events from a specific calendar with customizable limits.
- **Create Events**: Automatically create events on your calendar using AI-generated data.
- **AI Integration**: Utilize OpenAI to parse natural language descriptions into structured event data.

## Requirements

The following Python packages are required to run the project:

- `requests`
- `pydantic`
- `openai`
- `python-dateutil`
- `pytz`
- `ics`

## Installation

1. Clone the repository to your local machine.

    ```bash
    git clone https://github.com/Brandon-c-tech/AI-Calendar-Automation.git
    ```

2. Install the required Python packages.

    ```bash
    pip install -r requirements.txt
    ```

## Usage

1. **Configure API Parameters**: Replace `<GRANT_ID>`, `<API_KEY>`, and `<CALENDAR_ID>` in the code with your actual Nylas API credentials. Ensure that your environment variable contains the OpenAI API key.

2. **Run the Script**: Execute the script to interact with your calendar:
    ```bash
    python main.py
    ```

3. **Example**: The script provides functions to:
    - Fetch calendars.
    - Fetch a list of events from a calendar.
    - Create new calendar events based on natural language input.
