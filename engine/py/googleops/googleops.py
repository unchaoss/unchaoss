from __future__ import print_function
import httplib2
import os
import sys
import uuid

from apiclient import discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage
from googleapiclient import sample_tools

sys.path.append(os.path.join(os.path.dirname(__file__),".."))
from core import core, util

# If modifying these scopes, delete your previously saved credentials
# at ~/.credentials/drive-python-quickstart.json
SCOPES = 'https://www.googleapis.com/auth/drive.metadata.readonly'
ENCRYPTED_CLIENT_SECRET_FILE = os.path.join(core.get_credentials_base(), "unchaoss-encrypted-gsecret.json")
CLIENT_SECRET_FILE = os.path.join(core.get_credentials_base(), "unchaoss-gsecret.json")
APPLICATION_NAME = 'UNCHAOSS GOOGLE'
ENCRYPTED_CREDENTIALS_FILE = os.path.join(core.get_credentials_base(), "unchaoss-encrypted-credentials.json")
CREDENTIALS_FILE = os.path.join(core.get_credentials_base(), "unchaoss-credentials.json")

def cross_check_master_key(candidate):
    return core.cross_check_master_key(candidate)

def get_credentials(master_key, flags = None):
    client_secret_file_encrypt_fields = ["installed__client_id", "installed__client_secret"]
    credentials_file_encrypt_fields = ["access_token", "token_response__access_token",
                                      "client_id", "client_secret", "refresh_token"]
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """
    id = uuid.uuid4().hex
    credentials_file = CREDENTIALS_FILE + "-" + id
    if os.path.isfile(ENCRYPTED_CREDENTIALS_FILE):
        util.decrypt_json(ENCRYPTED_CREDENTIALS_FILE, credentials_file, master_key, credentials_file_encrypt_fields)
    store = Storage(credentials_file)
    store._create_file_if_needed()
    credentials = store.get()
    if not credentials or credentials.invalid:
        if os.path.isfile(ENCRYPTED_CLIENT_SECRET_FILE):
            util.decrypt_json(ENCRYPTED_CLIENT_SECRET_FILE, CLIENT_SECRET_FILE, master_key, client_secret_file_encrypt_fields)
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        if flags:
            credentials = tools.run_flow(flow, store, flags)
        else: # Needed only for compatibility with Python 2.6
            credentials = tools.run(flow, store)
        print('Storing credentials to ' + credentials_file)
        util.encrypt_json(credentials_file, ENCRYPTED_CREDENTIALS_FILE, master_key, client_secret_file_encrypt_fields)
        if os.path.isfile(CLIENT_SECRET_FILE):
            os.remove(CLIENT_SECRET_FILE)
    return (credentials, id)

def release_credentials(id):
    credentials_file = CREDENTIALS_FILE + "-" + id
    if os.path.isfile(credentials_file):
        os.remove(credentials_file)

