__author__ = 'cbdasg'

import json

#=============================== SINLGE KEY ENCRYPT/DECRYPT ====================================

from Crypto.Cipher import AES
import base64, os

#======= SINGLE KEY ENCRYPT/DECRYPT (https://gist.github.com/syedrakib/d71c463fc61852b8d366) ==========

class singleKeCryptDecrypt:

    # Inspired from https://pythonprogramming.net/encryption-and-decryption-in-python-code-example-with-explanation/
    # PyCrypto docs available at https://www.dlitz.net/software/pycrypto/api/2.6/

    def __init__(self, master_password = None, padding_character = ' '):

        self.padding_character = padding_character

        # AES key length must be either 16, 24, or 32 bytes long
        AES_key_length = 16 # use larger value in production

        if master_password == None:
            # generate a random secret key with the decided key length
            # this secret key will be used to create AES cipher for encryption/decryption
            secret_key = os.urandom(AES_key_length)
        else:
            # Pad the ley to the correct length
            secret_key = master_password
            key_length = len(master_password)
            while key_length < AES_key_length:
                secret_key += padding_character
                key_length += 1
        # encode this secret key for storing safely in database
        self.encoded_secret_key = base64.b64encode(secret_key)

    def get_key(self):
        return self.encoded_secret_key

    def encrypt_message(self, private_msg):
        # decode the encoded secret key
        secret_key = base64.b64decode(self.encoded_secret_key)
        # use the decoded secret key to create a AES cipher
        cipher = AES.new(secret_key)
        # pad the private_msg
        # because AES encryption requires the length of the msg to be a multiple of 16
        padded_private_msg = private_msg + (self.padding_character * ((16-len(private_msg)) % 16))
        # use the cipher to encrypt the padded message
        encrypted_msg = cipher.encrypt(padded_private_msg)
        # encode the encrypted msg for storing safely in the database
        encoded_encrypted_msg = base64.b64encode(encrypted_msg)
        # return encoded encrypted message
        return encoded_encrypted_msg

    def decrypt_message(self, encoded_encrypted_msg):
        # decode the encoded encrypted message and encoded secret key
        secret_key = base64.b64decode(self.encoded_secret_key)
        encrypted_msg = base64.b64decode(encoded_encrypted_msg)
        # use the decoded secret key to create a AES cipher
        cipher = AES.new(secret_key)
        # use the cipher to decrypt the encrypted message
        decrypted_msg = cipher.decrypt(encrypted_msg)
        # unpad the encrypted message
        unpadded_private_msg = decrypted_msg.rstrip(self.padding_character)
        # return a decrypted original private message
        return unpadded_private_msg

def single_key_demo():

    private_msg = """
     Lorem ipsum dolor sit amet, malis recteque posidonium ea sit, te vis meliore verterem. Duis movet comprehensam eam ex, te mea possim luptatum gloriatur. Modus summo epicuri eu nec. Ex placerat complectitur eos.
    """

    single_key_crypt_decrypt = singleKeCryptDecrypt()

    encrypted_msg = single_key_crypt_decrypt.encrypt_message(private_msg)
    decrypted_msg = single_key_crypt_decrypt.decrypt_message(encrypted_msg)

    secret_key = single_key_crypt_decrypt.get_key()

    print("   Secret Key: %s - (%d)" % (secret_key, len(secret_key)))
    print("Encrypted Msg: %s - (%d)" % (encrypted_msg, len(encrypted_msg)))
    print("Decrypted Msg: %s - (%d)" % (decrypted_msg, len(decrypted_msg)))

#=============================== PUB/PVT ENCRYPT/DECRYPT ====================================

from Crypto import Random
from Crypto.PublicKey import RSA
import base64



#======= PUB/PVT ENCRYPT/DECRYPT (https://gist.github.com/syedrakib/241b68f5aeaefd7ef8e2) ==========

class pubPvtCryptDecrypt:

    # Inspired from http://coding4streetcred.com/blog/post/Asymmetric-Encryption-Revisited-(in-PyCrypto)
    # PyCrypto docs available at https://www.dlitz.net/software/pycrypto/api/2.6/

    def __init__(self):
        # RSA modulus length must be a multiple of 256 and >= 1024
        modulus_length = 256*4 # use larger value in production
        self.privatekey = RSA.generate(modulus_length, Random.new().read)
        self.publickey = self.privatekey.publickey()

    def get_keys(self):
        return (self.privatekey, self.publickey)

    def encrypt_message(self, a_message):
        encrypted_msg = self.publickey.encrypt(a_message, 32)[0]
        encoded_encrypted_msg = base64.b64encode(encrypted_msg) # base64 encoded strings are database friendly
        return encoded_encrypted_msg

    def decrypt_message(self, encoded_encrypted_msg):
        decoded_encrypted_msg = base64.b64decode(encoded_encrypted_msg)
        decoded_decrypted_msg = self.privatekey.decrypt(decoded_encrypted_msg)
        return decoded_decrypted_msg

def pub_pvt_demo():
    pub_pvt_crypt_decrypt = pubPvtCryptDecrypt()
    a_message = "The quick brown fox jumped over the lazy dog"
    encrypted_msg = pub_pvt_crypt_decrypt.encrypt_message(a_message)
    decrypted_msg = pub_pvt_crypt_decrypt.decrypt_message(encrypted_msg)

    (privatekey, publickey) = pub_pvt_crypt_decrypt.get_keys()

    print("%s - (%d)" % (privatekey.exportKey() , len(privatekey.exportKey())))
    print("%s - (%d)" % (publickey.exportKey() , len(publickey.exportKey())))
    print(" Original content: %s - (%d)" % (a_message, len(a_message)))
    print("Encrypted message: %s - (%d)" % (encrypted_msg, len(encrypted_msg)))
    print("Decrypted message: %s - (%d)" % (decrypted_msg, len(decrypted_msg)))

#======= JSON FILE ENCRYPT/DECRYPT ==========

import json

# Replaces specifed values in a JSON file with their encrypted values. The keys list
# is used to locate the values to replace. A key of the form key1__key2 means
# key1 is a dict containing key2 as a key (and so on with __key3 etc). Encrypt
# is done using the supplied master key
def encrypt_json(in_json_file, out_json_file, master_key, encrypt_keys_list):
    single_key_crypt_decrypt = singleKeCryptDecrypt(master_key)
    with open(in_json_file) as fd:
        json_to_encrypt = json.load(fd)
    for key_to_encrypt_expr in encrypt_keys_list:
        jsn = json_to_encrypt
        keys_list_to_encrypt = key_to_encrypt_expr.split("__")
        for index in range(len(keys_list_to_encrypt)):
            key_to_encrypt = keys_list_to_encrypt[index]
            print("key " + key_to_encrypt + " jsn " + str(jsn))
            if key_to_encrypt not in jsn:
                return None
            if index != len(keys_list_to_encrypt) - 1:
                jsn = jsn[key_to_encrypt]
        jsn[key_to_encrypt] =\
            single_key_crypt_decrypt.encrypt_message(jsn[key_to_encrypt])
    with open(out_json_file, "w") as fd:
        json.dump(json_to_encrypt, fd)

# Replaces specifed values in a JSON file with their decrypted values. The keys list
# is used to locate the values to replace. A key of the form key1__key2 means
# key1 is a dict containing key2 as a key (and so on with __key3 etc). Decrypt
# is done using the supplied master key
def decrypt_json(in_json_file, out_json_file, master_key, decrypt_keys_list):
    single_key_crypt_decrypt = singleKeCryptDecrypt(master_key)
    with open(in_json_file) as fd:
        json_to_decrypt = json.load(fd)
    for key_to_decrypt_expr in decrypt_keys_list:
        jsn = json_to_decrypt
        keys_list_to_decrypt = key_to_decrypt_expr.split("__")
        for index in range(len(keys_list_to_decrypt)):
            key_to_decrypt = keys_list_to_decrypt[index]
            if key_to_decrypt not in jsn:
                return None
            if index != len(keys_list_to_decrypt) - 1:
                jsn = jsn[key_to_decrypt]
        jsn[key_to_decrypt] =\
            single_key_crypt_decrypt.decrypt_message(jsn[key_to_decrypt])
    with open(out_json_file, "w") as fd:
        json.dump(json_to_decrypt, fd)

if __name__ == "__main__":
    exit(0)
    single_key_demo()
    pub_pvt_demo()
