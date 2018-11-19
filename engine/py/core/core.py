__author__ = 'cbdasg'

import os
import util

def get_credentials_base():
    home_dir = os.path.expanduser('~')
    credentials_base = os.path.join(home_dir, '.credentials')
    if not os.path.exists(credentials_base):
        os.makedirs(credentials_base)
    return credentials_base

# UNCHAOSS expects the same master key to be used on every run but does not save
# the key itself as a security measure. The key must be externally provided
# (entered by a user using getpass or a through a web page displayed by a
# locally running server). After entry, and as a precaution against typos,
# there is a one time manual step where the master key is manually encrypted
# using itself (i.e. the master key is# both the text to encrypt and the
# encryption key) and saved in a file used by the code to verifies user entries.

# The class singleKeCryptDecrypt can be used for this manual step

def cross_check_master_key(candidate):
    master_password_cross_check_file = os.path.join(get_credentials_base(), "master_password_cross_check")
    with open(master_password_cross_check_file) as fd:
        master_password_cross_check_value = fd.readlines()[0].strip()

    single_key_crypt_decrypt = util.singleKeCryptDecrypt(candidate)

    encrypted_msg = single_key_crypt_decrypt.encrypt_message(candidate)
    if encrypted_msg != master_password_cross_check_value:
        return False
    return True

