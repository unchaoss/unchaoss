# UNCHAOSS: PYTHON

This directory holds all of the UNCHAOSS Python code

## About this directory

Each of the packages under this operates independently except for the unchaoss.core package used by all the other packages. All code is Python 2.7

## Pre-installs

The following Python packages are required to be pre-installed:


 <table>
  <tr>
    <th>Package</th>
    <th>Used by unchaoss packages</th>
    <th>Install command</th>
    <th>URL(s)</th>
    <th>NOTES</th>
  </tr>
  <tr>
    <td>Slack client</td>
    <td>culldeslack</td>
    <td>pip install slackclient==1.0.0</td>
    <td>https://realpython.com/blog/python/getting-started-with-the-slack-api-using-python-and-flask/<br/>https://github.com/slackapi/python-slackclient</td>
    <td></td>
  </tr>
  <tr>
    <td>Google API client</td>
    <td>googleops</td>
    <td>pip install --upgrade google-api-python-client</td>
    <td>https://developers.google.com/api-client-library/python/start/installation</td>
    <td></td>
  </tr>
  <tr>
    <td>Wordpress API wrapper</td>
    <td>wordpressops</td>
    <td>sudo pip install setuptools; git clone https://github.com/derwentx/wp-api-python; cd wp-api-python/; sudo python setup.py install </td>
    <td>https://pypi.python.org/pypi/wordpress-api/1.2.1</td>
    <td>Uses package requests; Uses package beautifulsoup</td>
  </tr>
</table> 
