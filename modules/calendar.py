from datetime import datetime, timedelta

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from utils.logging import get_logger

logger = get_logger(__name__)


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
            service = build('calendar', 'v3', credentials=self.credentials, cache_discovery=False)

            # Call the Calendar API
            now = datetime.utcnow().isoformat() + 'Z'
            events_result = service.events().list(calendarId=self.calendar_id, timeMin=now,
                                                  maxResults=max_results, singleEvents=True,
                                                  orderBy='startTime').execute()

            events = events_result.get('items', [])

            return events

        except Exception as e:
            logger.error("An error occurred while fetching events: %s", e)
            return []

    ## https://developers.google.com/calendar/api/v3/reference/events/insert
    def add_event(self, start: datetime, end: datetime, summary, description=None, location=None, all_day=False):
        service = build('calendar', 'v3', credentials=self.credentials, cache_discovery=False)

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
            service = build('calendar', 'v3', credentials=self.credentials, cache_discovery=False)
            calendar_list = service.calendarList().list().execute()
            return calendar_list.get('items', [])
        except Exception as e:
            logger.error("An error occurred while listing calendars: %s", e)
            return []


if __name__ == "__main__":
    from utils.logging import setup_logging
    setup_logging()
    
    calendar = Calendar("service_account.json")

    logger.info("Available calendars:")
    logger.info("-" * 50)
    for cal in calendar.list_calendars():
        logger.info("Name: %s", cal.get('summary'))
        logger.info("ID: %s", cal.get('id'))
        logger.info("Access: %s", cal.get('accessRole'))
        logger.info("-" * 50)
