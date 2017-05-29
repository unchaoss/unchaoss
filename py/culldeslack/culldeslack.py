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
    print "USAGE:\n\tpython %s followed by one out of:" % (sys.argv[0])
    for valid_args in valid_args_list:
        args_string = ""
        for arg_desc in valid_args[1]:
            args_string += " " + arg_desc
        print "\t\t" + valid_args[0] + args_string


class culldeslack:

    def cli(self, args):
        valid_args_list = [
            ("GetDump", ["in-file", "out-file"], self.get_dump)
        ]

        try:
            if len(sys.argv) == 1:
                raise UsageError("Missing args")
            valid_op_flag = False
            for valid_args in valid_args_list:
                if valid_args[0] == sys.argv[1]:
                    valid_op_flag = True
                    if len(sys.argv) != len(valid_args[1]) + 2:
                        raise UsageError("Wrong number of arguments for operation ' " + sys.argv[1] + " ' ")
                    valid_args[2](sys.argv[2:])
                    break
            if valid_op_flag == False:
                raise UsageError("Unrecognized operation " +  sys.argv[1])

        except UsageError as err:
            print err.msg
            Usage(valid_args_list)
            sys.exit(1)
        except RuntimeError as err:
            print err.msg
            sys.exit(2)


    def get_dump(self, args):

        palm_csv_default_headings = [
            "Prefix", "First Name", "Middle Name", "Last Name",
            "Suffix","Nickname", "Anniversary", "Birthday",
            "Profession", "Company", "Job Title", "Assistant Name",
            "Assistant Phone", "Work Street", "Work City", "Work State",
            "Work Zip", "Work Country", "Home Street", "Home City",
            'Home State', "Home Zip", "Home Country", "Other Street",
            "Other City", 'Other State', "Other Zip", "Other Country",
            "Work", "Home", "Fax", "Other",
            "Email", "Mobile", "Main", "Chat 1",
            "Chat 2", "Website", "Custom 1", "Custom 2",
            "Custom 3", "Custom 4", "Custom 5", "Custom 6",
            "Custom 7", "Custom 8", "Custom 9", "Note",
            "Private", "Category"
        ]

        in_file_name = args[0]
        out_file_name = args[1]

        try:

            self.validate_file_or_dir(in_file_name, is_file=True, is_write=False)
            rename_msg = self.rename_file_on_overwrite(out_file_name)
            if rename_msg is not None:
                print rename_msg
            self.validate_file_or_dir(out_file_name, is_file=True, is_write=True)

            in_file = open(in_file_name)
            reader = csv.DictReader(in_file, palm_csv_default_headings)
            out_file = open(out_file_name, "w")

        except IOError as err:
            raise UsageError(err)

        try:
            for row in reader:
                jcard =  [
                    "vcard",
                    [
                        ["version", {}, "text", "4.0"]
                    ]
                ]
                name_fields = ["Prefix", "First Name", "Middle Name", "Last Name",
                    "Suffix"]
                fn = ""
                for name_field in name_fields:
                    fn += row[name_field] + " "
                if fn != "":
                    fn = fn.strip()
                    jcard[1].append(["fn", {}, "text", fn])

                json.dump(jcard, out_file)
            in_file.close()
            out_file.close()
        except IOError as err:
            raise RuntimeError(err)

    def rename_file_on_overwrite(self,file_name):
        if os.path.isfile(file_name) == True:
            rename = file_name + datetime.datetime.now().strftime("-before-%Y-%m-%d-%H-%M-%S")
            os.rename(file_name, rename)
            return "Renaming " + file_name + " to " + rename
        return None

    def rename_dir_on_overwrite(self,dir_name):
        if os.path.isdir(dir_name) == True:
            rename = dir_name + datetime.datetime.now().strftime("-before-%Y-%m-%d-%H-%M-%S")
            os.rename(dir_name, rename)
            return "Renaming " + dir_name + " to " + rename
        return None

    def validate_file_or_dir(self, file_or_dir_name, is_file, is_write, no_over_write = True):
        if is_write:
            if os._exists(file_or_dir_name):
                if no_over_write:
                    raise UsageError(file_or_dir_name + " cannot be overwritten")
                if is_file:
                    if os.path.isfile(file_or_dir_name) == False:
                        raise UsageError(file_or_dir_name + " not found or is not a file")
                else:
                    if os.path.isdir(file_or_dir_name) == False:
                        raise UsageError(file_or_dir_name + " not found or is not a dir")
                if os.access(file_or_dir_name, os.W_OK) == False:
                    raise UsageError("You do not appear to have write permissions in " +
                        file_or_dir_name)
        else:
            if is_file:
                if os.path.isfile(file_or_dir_name) == False:
                    raise UsageError(file_or_dir_name + " not found or is not a file")
            else:
                if os.path.isdir(file_or_dir_name) == False:
                    raise UsageError(file_or_dir_name + " not found or is not a dir")
            if os.access(file_or_dir_name, os.R_OK) == False:
                raise UsageError("You do not appear to have read permissions in " +
                    file_or_dir_name)

def main():
    cds = culldeslack()
    cds.cli(sys.argv)

if __name__ == "__main__":
    main()
