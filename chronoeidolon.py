from __future__ import print_function
import httplib2
import os

# for parsing crns
import requests
from bs4 import BeautifulSoup
import re

# for creating & updating calendars
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


COLLEGE_WEEKDAYS = ['M', 'T', 'W', 'R', 'F', 'S', 'U']
RFC_WEEKDAYS = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']
COLLEGE_TO_RFC = dict(zip(COLLEGE_WEEKDAYS, RFC_WEEKDAYS))

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

        rfc_weekday_repeat= ','.join(
                [COLLEGE_TO_RFC[i] for i in split_cls_desc[4]]
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

    def get_first_start_date(self, term_start_date, weekdays):
        """
        Get first class date based on term start day and string of class days.

        E.g. term_start_date = datetime(2018, 12, 23), weekdays = 'MWF'
        """
        term_start_wd = term_start_date.weekday()

        WEEKDAY_LOOKUP = dict(zip(COLLEGE_WEEKDAYS, range(7)))

        weekdays = [WEEKDAY_LOOKUP[x] for x in weekdays]

        difference = min( (wkdy - term_start_wd) % 7 for wkdy in weekdays)

        return term_start_date + datetime.timedelta(days=difference)



    def soup_parse_dates(self,soup):

        date_string = soup.find(string='Course Dates:').find_next('td').string
        term_start, term_end = date_string.split(' - ')

        term_start = datetime.datetime.strptime(term_start, '%m/%d/%Y').date()
        term_end   = datetime.datetime.strptime(term_end, '%m/%d/%Y').date()


        time_string = soup.find(string='Days:').find_next('td').string
        weekdays, time = time_string.split(', Time:')

        time_start, time_end = time.split('-')

        time_start = datetime.datetime.strptime(time_start, '%H%M').time()
        time_end = datetime.datetime.strptime(time_end, '%H%M').time()

        # convert times
        first_class_date = self.get_first_start_date(term_start, weekdays)

        first_start = datetime.datetime.combine(
                first_class_date,
                time_start)

        first_end   = datetime.datetime.combine(
                first_class_date,
                time_end)

        utc_until = datetime.datetime.combine(
                term_end,
                time_end)

        utc_until = utc_until.replace(tzinfo = pytz.timezone('US/Eastern')).astimezone(pytz.UTC)

        rfc_weekday_repeat = ','.join([COLLEGE_TO_RFC[wd] for wd in weekdays])

        recur_string = 'RRULE:FREQ=WEEKLY;UNTIL={};BYDAY={}'.format(
                utc_until.strftime('%Y%m%dT%H%M%SZ'),
                rfc_weekday_repeat
                )

        return {
                'start': {'dateTime': first_start.isoformat(), 'timeZone': 'US/Eastern'},
                'end': {'dateTime': first_end.isoformat(), 'timeZone': 'US/Eastern'},
                'recurrence': [recur_string]
                }


    def add_crn(self, crn, term='201920'):
        url=f'https://courselist.wm.edu/courselist/courseinfo/addInfo?fterm={term}&fcrn={crn}'
        r = requests.get(url)
        soup = BeautifulSoup(r.content)

        # grab CRN, Summary, Description
        title_string = soup.find('td').string

        TITLE_PATTERN = re.compile(r'\s*CRN:(?P<crn>\d*) -- (?P<summary>.*) -- (?P<description>.*)[\r\s\r]*')

        classinfo = TITLE_PATTERN.match(title_string).groupdict()

        classinfo = {**classinfo, **self.soup_parse_dates(soup)}

        req = self.service.events().insert(
                calendarId=self.calendar['id'],
                body=classinfo)
        req.execute()



    def cleanup(self):
        service=self.service
        #calLst=self.service.calendarList().list().execute()
        calLst=service.calendarList().list().execute()
        ids_to_delete = [item['id'] for item in calLst['items'] if item['summary'] == 'Chronoeidolon']
        for cal_id in ids_to_delete:
            service.calendarList().delete(calendarId=cal_id).execute()


crns = [20234, 20744, 26029, 26033, 20232]
ce = chronoeidolon("Spring 2019 [Chronoeidolon]")
for crn in crns:
    ce.add_crn(str(crn))