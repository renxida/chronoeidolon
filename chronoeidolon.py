from __future__ import print_function
import httplib2
import os

from apiclient import discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage

import datetime, pytz

try:
    import argparse
    flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
except ImportError:
    flags = None

# If modifying these scopes, delete your previously saved credentials
# at ~/.credentials/calendar-python-quickstart.json
SCOPES = 'https://www.googleapis.com/auth/calendar'
CLIENT_SECRET_FILE = 'client_secret.json'
APPLICATION_NAME = 'Chronoeidolon'
TIMEZONE = 0

class chronoeidolon:
    
    # used by init
    
    def get_credentials(self):
        """Gets valid user credentials from storage.
    
        If nothing has been stored, or if the stored credentials are invalid,
        the OAuth2 flow is completed to obtain the new credentials.
    
        Returns:
            Credentials, the obtained credential.
        """
        home_dir = os.path.expanduser('~')
        credential_dir = os.path.join(home_dir, '.credentials')
        if not os.path.exists(credential_dir):
            os.makedirs(credential_dir)
        credential_path = os.path.join(credential_dir,
                                       'calendar-python-quickstart.json')
    
        store = Storage(credential_path)
        credentials = store.get()
        if not credentials or credentials.invalid:
            flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
            flow.user_agent = APPLICATION_NAME
            if flags:
                credentials = tools.run_flow(flow, store, flags)
            else: # Needed only for compatibility with Python 2.6
                credentials = tools.run(flow, store)
            print('Storing credentials to ' + credential_path)
        return credentials
    

    def make_calendar(self, calendar_name):
        """ Makes calendar
        """
        service=self.service
        calendar = {'summary': calendar_name, 'timeZone': 'America/New_York'}
        return service.calendars().insert(body=calendar).execute()
    
    def __init__(self, calendar_name = 'Chronoeidolon'):
        credentials = self.get_credentials()
        http = credentials.authorize(httplib2.Http())
        self.service = discovery.build('calendar', 'v3', http=http)
        self.calendar = self.make_calendar(calendar_name)
        self.timezone = self.service.calendars().get(calendarId='primary').execute()['timeZone']

    # Used by addclass
    def parse_class_description(self, class_description):
        """
        parses a class description string into a calendar event dict
        
        Keyword arguments:
        class_description -- str, of the form:
            name   ,location,time     ,1st day -last day,weekdays, optional comments
            MATH132,JONES111,1230-1320,20170118-20170427,MWF     
        """
        split_cls_desc = class_description.split(',')
        cls_times = split_cls_desc[2].split('-') # should be of form 1200
        cls_dates = split_cls_desc[3].split('-') # should be of form 20170120
        first_start = datetime.datetime.strptime(
                ''.join([cls_dates[0], cls_times[0]]),
                '%Y%m%d%H%M'
                )
        first_end = datetime.datetime.strptime(
                ''.join([cls_dates[0], cls_times[1]]),
                '%Y%m%d%H%M'
                )
        
        # generating recur string
        utc_until = datetime.datetime.strptime(
        ''.join([cls_dates[1], cls_times[1]]),
        '%Y%m%d%H%M'
        ).replace(tzinfo = pytz.timezone('US/Eastern')).astimezone(pytz.UTC)
        
        college_weekdays = ['M', 'T', 'W', 'R', 'F', 'S', 'U']
        rfc_weekdays = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']
        college_to_rfc = dict(zip(college_weekdays, rfc_weekdays))
        rfc_weekday_repeat= ','.join(
                [college_to_rfc[i] for i in split_cls_desc[4]]
                )
        
        recur_string = 'RRULE:FREQ=WEEKLY;UNTIL={};BYDAY={}'.format(
                utc_until.strftime('%Y%m%dT%H%M%SZ'),
                rfc_weekday_repeat,
                )
        
        ret_k = ['summary', 'location', 'description', 'start', 'end', 'recurrence']
        ret_v = [split_cls_desc[0],
                 split_cls_desc[1],
                 split_cls_desc[5],
                 {'dateTime': first_start.isoformat(), 'timeZone': 'US/Eastern'},
                 {'dateTime': first_end.isoformat(), 'timeZone': 'US/Eastern'},
                 [recur_string]
                 ]
        return dict(zip(ret_k, ret_v))
    
    def add_class(self, descriptor):
        cls_evt = self.parse_class_description(descriptor)
        req = self.service.events().insert(
                calendarId = self.calendar['id'],
                                        body = cls_evt)
        req.execute()

    def cleanup(self):
        service=self.service
        #calLst=self.service.calendarList().list().execute()
        calLst=service.calendarList().list().execute()
        ids_to_delete = [item['id'] for item in calLst['items'] if item['summary'] == 'Chronoeidolon']
        for cal_id in ids_to_delete:
            service.calendarList().delete(calendarId=cal_id).execute()

