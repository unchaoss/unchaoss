__author__ = 'chitrabhanu'

import csv
import os, stat
import sys
import datetime
import time
import json

USAGE_ERROR_PREFIX = "USAGE ERROR: "
RUNTIME_ERROR_PREFIX = "RUNTIME ERROR: "

class UsageError(Exception):

    def __init__(self, msg):
        self.msg = USAGE_ERROR_PREFIX + msg

class RuntimeError(Exception):

    def __init__(self, msg):
        self.msg = RUNTIME_ERROR_PREFIX + msg

def Usage(valid_args_list):
    print("USAGE:\n\tpython %s followed by one out of:" % (sys.argv[0]))
    print("TBD")


class culldeslack:

    def cli(self, args):
        pass

def main():
    cds = culldeslack()
    cds.cli(sys.argv)

if __name__ == "__main__":
    main()
