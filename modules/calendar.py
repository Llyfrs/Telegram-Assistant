import json
from datetime import datetime, timedelta

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from enums.database import DatabaseConstants
from modules.database import ValkeyDB


class Calendar:

    def __init__(self, credentials, token=None):


        self.credentials = credentials
        self.token = token
        self.SCOPES = ['https://www.googleapis.com/auth/calendar']

        pass

    def get_auth_link(self):

        flow = InstalledAppFlow.from_client_config(
            self.credentials,
            self.SCOPES,
            redirect_uri='urn:ietf:wg:oauth:2.0:oob'  # Enables manual code copy
        )

        auth_url, _ = flow.authorization_url(
            prompt='consent',
            access_type='offline',
        )
        return auth_url

    def exchange_code(self, code):

        flow = InstalledAppFlow.from_client_config(
            self.credentials,
            self.SCOPES,
            redirect_uri='urn:ietf:wg:oauth:2.0:oob'
        )

        flow.fetch_token(code=code)
        return flow.credentials


    def is_token_valid(self):
        if not self.token or not self.token.valid:
            return self.refresh_token()
        return True

    def refresh_token(self):
        if self.token and self.token.expired and self.token.refresh_token:
            try:
                self.token.refresh(Request())
                return True
            except Exception as e:
                print(f"Token refresh failed: {e}")
                return False
        return False

    ## https://developers.google.com/calendar/api/v3/reference/events/list
    def get_events(self, max_results=10):

        try:
            service = build('calendar', 'v3', credentials=self.token)

            # Call the Calendar API
            now = datetime.utcnow().isoformat() + 'Z'
            events_result = service.events().list(calendarId='primary', timeMin=now,
                                                  maxResults=max_results, singleEvents=True,
                                                  orderBy='startTime').execute()

            events = events_result.get('items', [])

            return events

        except Exception as e:
            print(f"An error occurred while fetching events: {e}")
            return []

        ## https://developers.google.com/calendar/api/v3/reference/events/insert
    def add_event(self, start: datetime, end :datetime, summary, description=None, location=None, all_day=False):
        service = build('calendar', 'v3', credentials=self.token)

        timezone = "Europe/Prague"

        event = {
            'summary': summary,
        }

        if description:
            event['description'] = description

        if location:
            event['location'] = location

        if all_day:
            # The date, in the format "yyyy-mm-dd", if this is an all-day event.
            event['start'] = {
                'date': start.date().isoformat(),
            }

            if end:
                event['end'] = {
                    'date': end.date().isoformat(),
                }
            else:
                event['end'] = {
                'date': start.date().isoformat(),
            }

        else:
            event['start'] = {
                'dateTime': start.isoformat(),
                'timeZone': timezone
            }

            if end:
                event['end'] = {
                    'dateTime': end.isoformat(),
                    'timeZone': timezone
                }
            else : ## Hour afte start
                start = start + timedelta(hours=1)
                event['end'] = {
                    'dateTime': start.isoformat(),
                    'timeZone': timezone
                }

        service.events().insert(calendarId='primary', body=event).execute()



if __name__ == "__main__":

    with open("modules/credentials.json", "r") as file:
        data = file.read()
        ValkeyDB().set(DatabaseConstants.CALENDAR_CREDS, data)


    creds = ValkeyDB().get(DatabaseConstants.CALENDAR_CREDS)
    creds = json.loads(creds)

    callendar = Calendar(creds)
    print(callendar.get_auth_link())

    code = input("Enter code: ")

    token = callendar.exchange_code(code)

    callendar.token = token

    ValkeyDB().set_serialized(DatabaseConstants.CALENDAR_TOKEN, token)

    events = callendar.get_events()

    for event in events:

        print(event)

        print(event['summary'])
        print(event['start']['date'])
        print(event['end']['date'])
        print()

