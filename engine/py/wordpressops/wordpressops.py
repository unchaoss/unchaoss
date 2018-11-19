__author__ = 'cbdasg'
import requests
from requests_oauthlib import OAuth1
import hmac
from hashlib import sha1

def fix_signature_url_chars(str):
    str = str.replace(":", "%3A")
    str = str.replace("/", "%2F")
    str = str.replace("=", "%3D")
    str = str.replace("&", "%26")
    return str

def fix_request_url_chars(str):
    str = str.replace("+", "%2B")
    return str

def send_request(key, signature_fields, request_fields, payload_values):
    cmd = "GET"
    url = "http://pinkyscreativerecipes.com/recipes/oauth1/request"
    raw = cmd + "&" + fix_signature_url_chars(url) + "&"
    prefix = ""
    for signature_field in signature_fields:
        raw += fix_signature_url_chars(prefix + signature_field + "=" + payload_values[signature_field])
        prefix = "&"
    hashed=hmac.new(key, raw, sha1)
    payload_values["oauth_signature"] = fix_request_url_chars(hashed.digest().encode("base64").rstrip("\n"))

    req_txt = url
    prefix = "?"
    for request_field in request_fields:
        req_txt += (prefix + request_field + "=" + payload_values[request_field])
        prefix = "&"
    print req_txt


    r = requests.get("http://pinkyscreativerecipes.com/recipes/oauth1/request", params = payload_values)
    print str(r.text)

signature_fields_1 = ["oauth_consumer_key", "oauth_nonce", "oauth_signature_method",
           "oauth_timestamp", "oauth_version"]

request_fields_1 = ["oauth_consumer_key", "oauth_signature_method", "oauth_timestamp",
                  "oauth_nonce", "oauth_version", "oauth_signature"]

payload_values_1 = {"oauth_consumer_key" : "zTOCIM1R772I" , "oauth_signature_method" : "HMAC-SHA1",
           "oauth_timestamp" : "1499648039", "oauth_nonce" : "D7LCfBJGJxM", "oauth_version": "1.0",
           "oauth_signature" : ""}

key = "qZurqPPfuD1yl4DEzAXj3cCyvLMWPblUWLeJprbJtHonHeRt&"

send_request(key, signature_fields_1, request_fields_1, payload_values_1)++++


