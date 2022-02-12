# UNCHAOSS: Google Services: Common code


## Setup: 

### Classes in this package require you to pass in previously obtained Google OAuth2 credentials.

#### An overview of the classes you would use to procure credentials is at https://developers.google.com/api-client-library/python/guide/aaa_oauth

#### A quick'n'dirty example of using some of these classes is at https://developers.google.com/drive/v3/web/quickstart/python

#### These steps get you a client ID and Client Secret that you can store to avoid having to ping the user each time to authorize access.


* Go to the API Console https://console.developers.google.com/
** Create a Project (or select an existing Project)
** Open the API Manager (if not already open) from the console left side menu. Enable all desired APIs for the Project.
** Click Credentials, click New Credentials, then select OAuth client ID
** Click the applicatiotype Other, enter an Application name of your choice and click the Create button
** Click OK to dismiss the resulting dialog
** Click the download symbol to the right of the client ID.
** Save the created JSON file

#### Other Useful URLs;

Google's "Getting started" page for the Python client is at: https://developers.google.com/api-client-library/python/start/get_started

Google's OAuth 2.0 instructions page is at https://developers.google.com/identity/protocols/OAuth2

