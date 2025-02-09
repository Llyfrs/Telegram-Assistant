import json
from datetime import datetime

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.discovery import Resource

from modules.database import ValkeyDB


class Callendar:

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

        auth_url, _ = flow.authorization_url(prompt='consent')
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
            if self.token and self.token.expired and self.token.refresh_token:
                self.token.refresh(Request())
            else:
                return False
        return True

    ## https://developers.google.com/calendar/api/v3/reference/events/list
    def get_events(self):
        service = build('calendar', 'v3', credentials=self.token)

        # Call the Calendar API
        now = datetime.utcnow().isoformat() + 'Z'
        events_result = service.events().list(calendarId='primary', timeMin=now,
                                              maxResults=10, singleEvents=True,
                                              orderBy='startTime').execute()

        events = events_result.get('items', [])

        return events




if __name__ == "__main__":

    with open("modules/credentials.json", "r") as file:
        data = file.read()
        ValkeyDB().set("callendar_credentials", data)


    creds = ValkeyDB().get("callendar_credentials")
    creds = json.loads(creds)

    callendar = Callendar(creds)
    print(callendar.get_auth_link())

    code = input("Enter code: ")

    token = callendar.exchange_code(code)

    ValkeyDB().set_serialized("callendar_token", token)

    events = callendar.get_events(token)

    for event in events:
        print(event['summary'])
        print(event['start']['dateTime'])
        print(event['end']['dateTime'])
        print()

