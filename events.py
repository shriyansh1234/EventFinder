import json
import os

EVENTS_FILE = 'events.json'

def load_events():
    if os.path.exists(EVENTS_FILE):
        with open(EVENTS_FILE, 'r') as f:
            return json.load(f)
    return []

def save_events(events):
    with open(EVENTS_FILE, 'w') as f:
        json.dump(events, f)

events = load_events()  # Load events from the JSON file
