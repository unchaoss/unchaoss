from __future__ import print_function
import httplib2
import os
import sys
import getpass

from apiclient import discovery
from oauth2client import tools

sys.path.append(os.path.join(os.path.dirname(__file__),".."))

import googleops

try:
    import argparse
    flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
except ImportError:
    flags = None

def quick_test_blogger(service):
    users = service.users()
    thisuser = users.get(userId='self').execute()
    print(str(users))
    blogs = service.blogs()
    print(str(blogs.listByUser(userId='self').execute()))

def quick_test_drive(service):
    results = service.files().list(
        pageSize=10,fields="nextPageToken, files(id, name)").execute()
    items = results.get('files', [])
    if not items:
        print('No files found.')
    else:
        print('Files:')
        for item in items:
            print('{0} ({1})'.format(item['name'], item['id']))

def main(argv):
    tries_remaining=3
    master_key = None
    while tries_remaining:
        print("Enter master key")
        master_key = getpass.getpass()
        if googleops.cross_check_master_key(master_key) == False:
            if tries_remaining > 1:
                print("Master key fails cross check, re-enter. You have " + str(tries_remaining - 1) + " retries left")
                tries_remaining -= 1
            else:
                print("Master key fails cross check, re-enter. You have no more retries left")
                exit(1)
        else:
            break
    (credentials, id) = googleops.get_credentials(master_key)
    http = credentials.authorize(httplib2.Http())
    """Shows basic usage of the Google Drive API.
    Creates a Google Drive API service object and outputs the names and IDs
    for up to 10 files.
    """
    drive_service = discovery.build('drive', 'v3', http=http)
    quick_test_drive(drive_service)
    blogger_service = discovery.build('blogger', 'v3', http=http)
    quick_test_blogger(blogger_service)
    googleops.release_credentials(id)

if __name__ == '__main__':
    main(sys.argv)

