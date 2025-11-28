from datetime import datetime, timedelta

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


class Calendar:

    SCOPES = ['https://www.googleapis.com/auth/calendar']

    def __init__(self, service_account_file: str, calendar_id: str = 'primary'):
        self.calendar_id = calendar_id
        self.credentials = Credentials.from_service_account_file(
            service_account_file,
            scopes=self.SCOPES
        )

    ## https://developers.google.com/calendar/api/v3/reference/events/list
    def get_events(self, max_results=10):

        try:
            service = build('calendar', 'v3', credentials=self.credentials)

            # Call the Calendar API
            now = datetime.utcnow().isoformat() + 'Z'
            events_result = service.events().list(calendarId=self.calendar_id, timeMin=now,
                                                  maxResults=max_results, singleEvents=True,
                                                  orderBy='startTime').execute()

            events = events_result.get('items', [])

            return events

        except Exception as e:
            print(f"An error occurred while fetching events: {e}")
            return []

    ## https://developers.google.com/calendar/api/v3/reference/events/insert
    def add_event(self, start: datetime, end: datetime, summary, description=None, location=None, all_day=False):
        service = build('calendar', 'v3', credentials=self.credentials)

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
            else:  ## Hour after start
                start = start + timedelta(hours=1)
                event['end'] = {
                    'dateTime': start.isoformat(),
                    'timeZone': timezone
                }

        service.events().insert(calendarId=self.calendar_id, body=event).execute()


    def list_calendars(self):
        """List all calendars the service account has access to."""
        try:
            service = build('calendar', 'v3', credentials=self.credentials)
            calendar_list = service.calendarList().list().execute()
            return calendar_list.get('items', [])
        except Exception as e:
            print(f"An error occurred while listing calendars: {e}")
            return []


if __name__ == "__main__":
    calendar = Calendar("service_account.json")

    print("Available calendars:")
    print("-" * 50)
    for cal in calendar.list_calendars():
        print(f"Name: {cal.get('summary')}")
        print(f"ID: {cal.get('id')}")
        print(f"Access: {cal.get('accessRole')}")
        print("-" * 50)
