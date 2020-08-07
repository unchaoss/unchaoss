import sys
if sys.version_info[0] == 3:
    import configparser as ConfigParser
elif sys.version_info[0] == 2:
    import ConfigParser
if sys.version_info[0] == 3:
    import queue as Queue
elif sys.version_info[0] == 2:
    import Queue
import os
import json
import filecmp
import shutil
import getpass
import socket
import threading
import time
import subprocess
import hashlib
import time
import logging
import copy
import glob
import inspect

USAGE_ERROR_PREFIX = "USAGE ERROR: "
RUNTIME_ERROR_PREFIX = "RUNTIME ERROR: "

TIMESTAMP = time.strftime("%Y-%m-%d-%H-%M-%S")

class UsageError(Exception):

    def __init__(self, msg):
        self.msg = USAGE_ERROR_PREFIX + msg

class RuntimeError(Exception):

    def __init__(self, msg):
        self.msg = RUNTIME_ERROR_PREFIX + msg

def Usage():
    print("USAGE:\n\t%s ini-file-name [ini-file-name ...]" % (sys.argv[0]))
    print("\tOR")
    print("\t%s configs-json-file-name" % (sys.argv[0]))
    print("\tconfigs-json-file is equivalent JSON to the ini-files (ini file SECTIONS are highest level JSON keys)")
    print("\t\t(Each run generates a configs-JSON file, usable in a later run).")
    print("")
    print("The 'commands_dir' value (under 'dirs' section in .ini and 'dirs' key in JSON) specifies a directory which")
    print("\tis checked for the existence of JSON files contaning commands. The program processes all the JSON files it")
    print("\tfinds then terminates. A command file JSON is a dict with the keys, 'link', 'device', 'commands' and")
    print("\t(optionally) 'overrides'. 'link' and 'device' are the link and device names for the list of commands and")
    print("\t'commands' is a list of dicts, each holding one command. (These commands execute sequentially while")
    print("\tcommands from the different JSON files run in parallel threads). Each dict has one key (the command),")
    print("\t\tone of 'import', 'dryrun', 'export', 'cleanup', 'admin')")
    print("\t\tThe value is either null or is a dict with command-specific parameters")                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           print("\t\t\t'import': No command-specific parameters")
    print("\t\t\t'dryrun': No command-specific parameters")
    print("\t\t\t'export': No command-specific parameters")
    print("\t\t\t'cleanup': No command-specific parameters")
    print("\t\t\t'admin': (Parameters are admin tasks as listed below. 'device'/'link' must be 'localhost'/'local_fs')")
    print("\t\t\t\t'handle_device_relocates': {'dryrun' (optional) : null")
    print("\t\t\t\t\tDelete inbox copies of files relocated on the device (retain only the copy from new location. ")
    print("\t\t\t\t\tno duplicates found on localhost.")
    print("\t\t\t\t'repair_catalog': {'dryrun' (optional) : null}")
    print("\t\t\t\t\tInsert or delete (as needed) unmatched catalogs/catalog_index; 'device' must be 'localhost'")
    print("\t\t\t\t(File locators are described below)")
    print("\t'overrides' is a dict with replacements of configs-json values to use when executing this JSON")
    print("\t\tIf a value is null the matching entry is removed")
    print("\t\tThe following sections cannot be overridden: ['local_dirs', 'file_category_for_file_extension'] and")
    print("\t\tconfig defaults cannot be overridden.")
    print("FILE LOCATORS:")
    print("\tA file locator is a string (and is a valid filename) containing information identifying the complete")
    print("\tlocation of a remote or local file. It is of the form (note the . after the device name):")
    print("\t<device name OR host-computer-name>.<String reflecting full path with / replaced by __> (example below)")
    print("\t\tPrior to replacing / by __, existing '__' sequences are first escaped out by replacing '+' by '++' then")
    print("\t\treplacing '__' by '_+_' (last step repeated while __ still present)")
    print("\t\tEg: A file '/storage/emulated/0/xxx.txt' on an Android phone named yyy will have a file locator")
    print("\t\t'yyy.__storage__emulated__0__xxx.txt'. ")

# We do not want the .ini file to change run to run which means it cannot hold values that change with each run. Instead
# we pass the (run variant) values below to the config parser to add to the processed .ini file. (Note that, as per
# standard ConfigParser parser behavior these values - along with those in the DEFAULTS section of the original .ini
# file - are replicated under each section in the processed value in memory and are no longer available in a separate
# section. For convenience, the code also creates a separate dict containing only these defaults).
CONFIG_DEFAULTS = {
    "user" : getpass.getuser(),
    "home_dir" : os.environ["HOME"],
    "host_name" : socket.gethostname(),
    "start_time" : time.strftime("%Y-%m-%d-%H-%M-%S")
}

def is_text(value):
    if sys.version_info[0] == 3:
        return isinstance(value, str)
    elif sys.version_info[0] == 2:
        return isinstance(value, str) or isinstance(value, unicode)
    return False

def link_and_device_to_link_device(link, device):
    return link + "__" + device

def link_device_to_link_and_device(link_and_device):
    words = link_and_device.split("__")
    assert len(words) == 2
    return (words[0], words[1])

def link_and_option_to_link_option(link, option):
    return link + "__" + option

def link_option_to_link_and_option(link_and_option):
    words = link_and_option.split("__")
    assert len(words) == 2
    return (words[0], words[1])

def could_be_link_option(candidate):
    return len(candidate.split("__")) == 2

def byte_to_str(text):
    return str((text).decode("utf-8") )

def get_file_md5(file_path):
    fd = open(file_path, "rb")
    hasher = hashlib.sha256()
    blocksize=1048576
    buf = fd.read(blocksize)
    while len(buf) > 0:
        hasher.update(buf)
        buf = fd.read(blocksize)
    return hasher.hexdigest()

# Base class. Should not be directly initiated. Note that class objects get
# separately instantiated for each operation (as opposed to keeping an instance
# alive over multiple operations). This allows instantiation code to be
# optimized for different operations.
#
# Assumes the destination is a (Linux/Un*x) file system, accordingly implements
# all functions that interact only with the destination. Functions interacting
# with sources are implemented in source-type-specifc subclasses.
#
# Each subclass implements a single link (eg mpt or sshfs or GDrive)
#
# These classes do not replicate source directory structures on destinations but
# create destination file names that indicate the source tree location of files.
# In cases where the source is a filesystem this should be done by using the
# class function file_path_to_file_locator() (it primarily replaces / in the
# source file path with __ to create the destination file name). The reverse
# class function file_locator_to_file_path() is used to get the source
# file path for a destination file name.
#
# Source file paths used in arguments are paths to source, not local, files
#

class UncloudBase:

    launch_lock = threading.Lock()

    # Max-threads can be specified at four levels, global (for the entire run), per device, per link (type) and
    # for each link-device combo. This dict maintains maximum allowed and actual thread counts across all levels.
    # Keys are <GLOBAL_THREAD_COUNTS_KEY>, link, device, link_device; Values are [max-threads, actual-threads]
    threads_counts = {}
    GLOBAL_THREAD_COUNTS_KEY = "GLOBAL"
    THREADS_COUNT_MAX_THREADS_INDEX = 0
    THREADS_COUNT_ACTUAL_THREADS_INDEX = 1

    # Parallel command runs use threads with one thread per command. Each thread is run with a single argument which is
    # a queue object from which the thread reads UncloudBase objects to call their run methods. In launching a command
    # a thread is selected; 1st pref is an existing queue with an empty queue, otherwise a new thread is launched if
    # possible (ie does not exceed the max threads limit for any of the levels), otherwise the thread with the smallest
    # queue size is used. The command's UncloudBase object is then writen to the thread's queue to launch the command.

    # This dict has one list for each link-device combo where list elements are (thread-obj, queue-obj) tuples
    # Keys are linkdevice; Values are [(thread, queue), (thread, queue) ...]. 'launch_thread_index'refers to position
    # within one of these lists
    threads_pool = {}
    THREADS_POOL_THREAD_INDEX = 0
    THREADS_POOL_QUEUE_INDEX = 1

    def __init__(self, responses_file_path, link, device, original_config, updated_config, final_commands_list):
        self.final_commands_list = final_commands_list
        self.original_config = original_config
        self.updated_config = updated_config
        self.responses_file_path = responses_file_path
        self.device = device
        self.link = link
        self.host_name = self.get_config_default_value("host_name")

        section_name = "local_dirs"
        self.inbox_dir = self.get_config_value(section_name, "inbox_dir")
        self.outbox_dir = self.get_config_value(section_name, "outbox_dir")
        self.catalog_dir = self.get_config_value(section_name, "catalog_dir")
        self.catalog_index_dir = self.get_config_value(section_name, "catalog_index_dir")
        self.commands_dir = self.get_config_value(section_name, "commands_dir")
        self.responses_dir = self.get_config_value(section_name, "responses_dir")
        self.trash_list_dir = self.get_config_value(section_name, "trash_list_dir")

        MAX_FILE_NAME_SIZE = 255
        max_file_locators_base_dir_size = max( len(self.inbox_dir), len(self.outbox_dir))
        max_file_locators_base_dir_size = max(max_file_locators_base_dir_size, len(self.catalog_index_dir))
        self.max_file_locator_size = MAX_FILE_NAME_SIZE - 1 - max_file_locators_base_dir_size

        self.init_threads_counts()

    def __del__(self):
        pass

    def write_log_line(self, level, block, op, data = None):
        logging.log(level, ("Thread=" + str(threading.current_thread().ident) + "\t" +
                      str(block) + "\t" + str(op) + "\t" + str(data)))

    # The DEFAULTS section from the original .ini file(s) is replicated under each section in the original_config dict.
    # The desired value value will be the same in all the sections and here we choose the first section for use
    def get_config_default_value(self, key):
        sample_section = list(self.original_config.keys())[0]
        return self.original_config[sample_section][key]

    def device_file_path_to_file_locator(self, file_path):
        return self.file_path_to_file_locator(file_path)

    def local_file_path_to_file_locator(self, file_path):
        return self.file_path_to_file_locator(file_path, self.host_name)

    def file_path_to_file_locator(self, file_path, device = None):
        # Replaces all / by __ so as to change the path name to a file name
        # + is used as an escape character breaking up any __ sequence already present
        result = file_path
        result = result.replace("@", "@@")
        while "_/" in result:
            result = result.replace("_/", "_@_")
        result = result.replace("+", "++")
        while "__" in result:
            result = result.replace("__", "_+_")
        if device == None:
            device = self.device
        if device == "localhost":
            device = self.host_name
        return device + "." + result.replace("/", "__")

    def file_locator_to_file_path(self, file_locator):
        # Remove device name
        file_locator = file_locator[file_locator.find(".") + 1:]
        # Replaces all__ by / so as to change the file name to a path name
        # + had been used as an escape character breaking up any __ sequence already present
        result = file_locator.replace("__", "/")
        while("_+_" in result):
            result = result.replace("_+_", "__")
        result = result.replace("++", "+")
        while("_@_" in result):
            result = result.replace("_@_", "_/")
        result = result.replace("@@", "@")
        return result

    def file_locator_to_device(self, file_locator):
        device = file_locator[ : file_locator.find(".")]
        if device == self.host_name:
            device = "localhost"
        return device

    def do_device_specific_validation(self):
        has_errors = False
        responses = {"responses" : []}
        for command_index in range(len(self.final_commands_list)):
            command_info = self.final_commands_list[command_index]
            command = list(command_info.keys())[0]
            if command == "import":
                responses["responses"].append({"response" : [], "errors" : []})
            if command == "dryrun":
                responses["responses"].append({"response" : [], "errors" : []})
            elif command == "export":
                responses["responses"].append({"response" : [], "errors" : []})
            elif command == "cleanup":
                responses["responses"].append({"response" : [], "errors" : []})
            elif command == "admin":
                responses["responses"].append({"response" : [], "errors" : []})
        return(responses, has_errors)

    def init_threads_counts(self):
        self.lock_launch_state()
        self.init_threads_counts_entry()
        for link in self.get_config_default_value("links"):
            self.init_threads_counts_entry(link = link)
        for device in self.get_config_default_value("devices"):
            self.init_threads_counts_entry(device = device)
            for link in self.get_config_value(device, "links", "device"):
                self.init_threads_counts_entry(link = link, device = device)
        self.unlock_launch_state()

    def init_threads_counts_entry(self, link = None, device = None):
        if link is None and device is None:
            value = self.get_config_default_value("global_max_parallels")
            key = UncloudBase.GLOBAL_THREAD_COUNTS_KEY
        elif device is None:
            value = self.get_config_value(link, "max_parallels")
            key = link
        else:
            if link:
                value = self.get_config_value(device, "max_parallels", link)
                key = link_and_device_to_link_device(link, device)
            else:
                value = self.get_config_value(device, "max_parallels", "device")
                key = device
        if value == None:
            UncloudBase.threads_counts[key] = [None, 0]
        else:
            UncloudBase.threads_counts[key] = [int(value), 0]

    def lock_launch_state(self):
        UncloudBase.launch_lock.acquire()

    def unlock_launch_state(self):
        UncloudBase.launch_lock.release()

    def launch(self):

        self.write_log_line(logging.DEBUG, self.__class__.__name__, "Launch", "Link=" + self.link + " Device=" + self.device)

        (responses, has_errors) = self.do_device_specific_validation()
        if has_errors:
            with open(self.responses_file_path, "w") as fd:
                json.dump(responses, fd)
            return

        link_device = link_and_device_to_link_device(self.link, self.device)
        max_threads_index = UncloudBase.THREADS_COUNT_MAX_THREADS_INDEX
        actual_threads_index = UncloudBase.THREADS_COUNT_ACTUAL_THREADS_INDEX
        pool_thread_index = UncloudBase.THREADS_POOL_THREAD_INDEX
        pool_queue_index = UncloudBase.THREADS_POOL_QUEUE_INDEX

        self.lock_launch_state()

        # Check Globak, link, device, link_device limits for max threads
        if UncloudBase.threads_counts[UncloudBase.GLOBAL_THREAD_COUNTS_KEY][max_threads_index] == 0 or\
            self.link in UncloudBase.threads_counts and\
                           UncloudBase.threads_counts[self.link][max_threads_index] == 0 or\
            self.device in UncloudBase.threads_counts and\
                                UncloudBase.threads_counts[self.device][max_threads_index] == 0 or\
            link_device in UncloudBase.threads_counts and\
                                UncloudBase.threads_counts[link_device][max_threads_index] == 0:
            use_thread = False
            self.unlock_launch_state()
            self.run()

        else:

            use_thread = True
            launch_pool_thread_index = -1
            new_thread = False

            # Determine launch thread index
            if link_device not in UncloudBase.threads_counts or UncloudBase.threads_counts[link_device][actual_threads_index] == 0:
                # First thread for this link_device
                launch_pool_thread_index = 0
                new_thread = True
            else:
                # Search for first empty queue
                found = False
                min_queue_size = None
                min_pool_queue_index = None
                for index in range(len(UncloudBase.threads_pool[link_device])):
                    (launch_thread, launch_queue) = UncloudBase.threads_pool[link_device][index]
                    if launch_queue.empty():
                        found = True
                        launch_pool_thread_index = index
                    if min_queue_size is None or min_queue_size < launch_queue.size():
                        min_queue_size = launch_queue.size()
                        min_pool_queue_index = index
                if found == False:
                    # If possible, occupy a new thread
                    if UncloudBase.threads_counts[UncloudBase.GLOBAL_THREAD_COUNTS_KEY][actual_threads_index] !=\
                            UncloudBase.threads_counts[UncloudBase.GLOBAL_THREAD_COUNTS_KEY][max_threads_index] and\
                        UncloudBase.threads_counts[self.link][actual_threads_index] !=\
                                    UncloudBase.threads_counts[self.link][max_threads_index] and\
                        UncloudBase.threads_counts[self.device][actual_threads_index] !=\
                                    UncloudBase.threads_counts[self.device][max_threads_index] and\
                        UncloudBase.threads_counts[link_device][actual_threads_index] !=\
                                    UncloudBase.threads_counts[link_device][max_threads_index]:
                        launch_pool_thread_index = len(UncloudBase.threads_pool[link_device])
                        new_thread = True
                    else:
                        launch_pool_thread_index = min_pool_queue_index

            # Create new thread if needed
            if new_thread:
                new_q = Queue.Queue()
                UncloudBase.threads_pool[launch_pool_thread_index] = (
                    threading.Thread(target = thread_launch, args = (new_q,)), new_q
                )
                # Mark non-daemon or else it will get shut down if main thread terminates
                UncloudBase.threads_pool[launch_pool_thread_index][pool_thread_index].daemon = False
                UncloudBase.threads_pool[launch_pool_thread_index][pool_thread_index].start()
            # Update thread counts to include this new thread
            link_device = link_and_device_to_link_device(self.link, self.device)
            UncloudBase.threads_counts[UncloudBase.GLOBAL_THREAD_COUNTS_KEY][actual_threads_index] += 1
            UncloudBase.threads_counts[self.link][actual_threads_index] += 1
            UncloudBase.threads_counts[self.device][actual_threads_index] += 1
            UncloudBase.threads_counts[link_device][actual_threads_index] += 1

            self.unlock_launch_state()

            # Start the run
            UncloudBase.threads_pool[launch_pool_thread_index][pool_queue_index].put(self)

    def run(self):

        self.write_log_line(logging.INFO, self.__class__.__name__, "Run", "Starting")
        if self.connect():
            self.process()
            self.disconnect()

        self.write_log_line(logging.INFO, self.__class__.__name__, "RunEnded")

    def connect(self):

        errors = []

        if errors != []:
            raise RuntimeError(str(errors))

        return True

    def disconnect(self):

        self.write_log_line(logging.DEBUG, self.__class__.__name__, "Disconnect", time.strftime("%Y-%m-%d-%H-%M-%S"))

    def process(self):
        responses = {"responses" : []}
        resp = []
        errs = []
        for command_info in self.final_commands_list:
            command = list(command_info.keys())[0]
            params = command_info[command]
            if command == "import":
                (resp, errs) = self.do_import(params)
            if command == "dryrun":
                (resp, errs) = self.do_import(params, True)
            elif command == "export":
                (resp, errs) = self.do_export(params)
            elif command == "cleanup":
                (resp, errs) = self.do_cleanup(params)
            elif command == "admin":
                (resp, errs) = self.do_admin(params)
            responses["responses"].append({"response" : resp, "errors" : errs})
        with open(self.responses_file_path, "w") as fd:
            json.dump(responses, fd)

    def do_import(self, params, dryrun = False):

        file_import_mode = self.get_config_value(self.device, "file_import_mode", "device")

        if dryrun:
            self.write_log_line(logging.DEBUG, self.__class__.__name__, "Dry run", "Params=" + str(params))
        else:
            self.write_log_line(logging.DEBUG, self.__class__.__name__, "Import", "Params=" + str(params))

        free_space_by_disk_id = {}

        (exclude_dirs, exclude_files, include_files) = self.get_mounted_exclude_include_lists()
        catalog_indexed_entries = self.get_catalog_indexed_entries()
        (device_files_map, device_added_files_map) = self.get_device_files_map(catalog_indexed_entries,
                                                                       exclude_dirs, exclude_files, include_files)
        device_discards_map = {}
        for file_locator in catalog_indexed_entries:
            if self.is_file_excluded(file_locator, exclude_dirs, exclude_files, include_files):
                continue
            (_, local_file_mtime, local_file_device_bytes) = catalog_indexed_entries[file_locator]
            if file_locator not in device_files_map:
                device_discards_map[file_locator] = (local_file_mtime, local_file_device_bytes)
            else:
                (device_device_file_mtime, device_device_file_bytes) = device_files_map[file_locator]
                if local_file_mtime != device_device_file_mtime or\
                                local_file_device_bytes != local_file_device_bytes:
                    device_discards_map[file_locator] = (local_file_mtime, local_file_device_bytes)

        for file_locator in device_discards_map:
            self.write_log_line(logging.DEBUG, self.__class__.__name__, "Import:RemoteDiscard", "RemoteFileLocator=" +
                           file_locator)
            if dryrun:
                self.write_log_line(logging.DEBUG, "Dry run", "Detected discard of device " +
                                    self.file_locator_to_device(file_locator) + " file " +
                                    self.file_locator_to_file_path(file_locator))
            else:
                self.delete_catalog_entry(file_locator)

        for device_file_locator in device_added_files_map:
            device_file = self.file_locator_to_file_path(device_file_locator)
            # Note that this local file will not get created if file_import_mode
            # is 'none'. The functions below that use the 'local_file' variable
            # do not require the local file to exist
            if file_import_mode == "copy" or file_import_mode == "move":
                local_file = os.path.join(self.inbox_dir, device_file_locator)
                local_file_locator = self.local_file_path_to_file_locator(local_file)
                if len(local_file_locator) > self.max_file_locator_size:
                    self.write_log_line(logging.ERROR, self.__class__.__name__, "Import",
                                        "ERROR: local_file_locator " + str(local_file_locator) +
                                        " for local_file " + str(local_file) +
                                        " exceeds size limit, discarding")
                    continue
            else:
                local_file = None # Precaution agains coding errors
                local_file_locator = None # Precaution agains coding errors
            if dryrun:
                if file_import_mode == "copy" or file_import_mode == "move":
                    (file_bytes, disk_id) = self.get_local_file_bytes_and_disk_id(device_file, local_file)
                    if disk_id not in free_space_by_disk_id:
                        free_space_by_disk_id[disk_id] = self.get_local_drv_free_bytes(local_file)
                    free_space_by_disk_id[disk_id] -= file_bytes
                    if free_space_by_disk_id[disk_id] >= 0:
                        self.write_log_line(logging.DEBUG, "Dry run", "Importing " + str(file_bytes) +
                              " bytes " + str(local_file) + " to " + device_file +
                              "; space remaining " + str(free_space_by_disk_id[disk_id]) + " bytes")
            else:
                (mtime, device_bytes) = device_added_files_map[device_file_locator]
                if file_import_mode == "copy":
                    self.write_log_line(logging.DEBUG, self.__class__.__name__, "Import:Copying/Cataloging",
                                        "RemoteFile=" + device_file + " to Localfile=" + str(local_file))
                    self.copy_file_in(device_file, local_file)
                    md5 = get_file_md5(local_file)
                    self.add_catalog_entry(local_file_locator, md5, mtime, device_bytes) # Add inbox copy to catalog
                    self.add_catalog_entry(device_file_locator, md5, mtime, device_bytes) # Add device copy to catalog
                elif file_import_mode == "move":
                    self.write_log_line(logging.DEBUG, self.__class__.__name__, "Import:Moving/Cataloging",
                                        "RemoteFile=" + device_file + " to Localfile=" + str(local_file))
                    self.move_file_in(device_file, local_file)
                    md5 = get_file_md5(local_file)
                    self.add_catalog_entry(local_file_locator, md5, mtime, device_bytes) # Add inbox copy to catalog
                elif file_import_mode == "none":
                    self.write_log_line(logging.DEBUG, self.__class__.__name__, "Import:Cataloging",
                                        "RemoteFile=" + device_file)
                    md5 = self.get_device_file_md5(device_file)
                    self.add_catalog_entry(device_file_locator, md5, mtime, device_bytes) # Add device copy to catalog
                else:
                    assert False
        return("OK", [])

    def do_export(self, params):

        self.write_log_line(logging.DEBUG, self.__class__.__name__, "Export", "Params=" + str(params))

        for device_file_locator in os.listdir(self.outbox_dir):
            if self.file_locator_to_device(device_file_locator) != self.device:
                continue
            local_file = os.path.join(self.outbox_dir, device_file_locator)
            device_file = self.file_locator_to_file_path(device_file_locator)
            self.write_log_line(logging.DEBUG, self.__class__.__name__, "Export:Copying", "LocalFile=" +
                           local_file + " to Remotefile=" + device_file)
            self.copy_file_out(local_file, device_file)
            mtime = self.get_device_file_mtime(device_file)
            file_bytes = self.get_device_file_bytes(device_file)
            md5 = get_file_md5(local_file)
            self.add_catalog_entry(device_file_locator, md5, mtime, file_bytes)
            os.remove(local_file)
        return("OK", [])

    def do_cleanup(self, params):

        self.write_log_line(logging.DEBUG, self.__class__.__name__, "Cleanup", "Params=" + str(params))

        for device_file_locator in os.listdir(self.outbox_dir):
            path = os.path.join(self.outbox_dir, device_file_locator)
            if os.path.islink(path) == False:
                continue
            if self.file_locator_to_device(device_file_locator) != self.device:
                continue
            device_file = self.file_locator_to_file_path(device_file_locator)
            self.write_log_line(logging.DEBUG, self.__class__.__name__, "Cleanup:Deleting", "RemoteFile=" + device_file)
            self.delete_device_file(device_file)
            self.delete_catalog_entry(device_file_locator)
            os.unlink(path)
        return("OK", [])

    def do_admin(self, params):

        errs = []

        self.write_log_line(logging.DEBUG, self.__class__.__name__, "admin", "Params=" + str(params))

        catalog_indexed_entries = None
        catalog_indexed_entries_by_md5 = None

        if "handle_device_relocates" in params:
            if catalog_indexed_entries is None:
                catalog_indexed_entries = self.get_catalog_indexed_entries(True)
            if catalog_indexed_entries_by_md5 is None:
                catalog_indexed_entries_by_md5 = self.get_catalog_indexed_entries_by_md5(catalog_indexed_entries)
            dryrun = False
            if params["handle_device_relocates"] and "dryrun" in params["handle_device_relocates"]:
                dryrun = True
            (errors, catalog_indexed_entries, catalog_indexed_entries_by_md5) = \
                (self.do_admin_handle_device_relocates(params, catalog_indexed_entries, catalog_indexed_entries_by_md5, dryrun))
            errs.extend(errors)

        if "repair_catalog" in params:
            if catalog_indexed_entries is None:
                catalog_indexed_entries = self.get_catalog_indexed_entries(True)
            dryrun = False
            if params["repair_catalog"] and "dryrun" in params["repair_catalog"]:
                dryrun = True
            (errors, catalog_indexed_entries) = (self.do_admin_repair_catalog(params, catalog_indexed_entries, dryrun))
            errs.extend(errors)

        return("OK", errs) # OK signifies the command completed not that there were no errors

    def do_admin_handle_device_relocates(self, params, catalog_indexed_entries, catalog_indexed_entries_by_md5, dryrun):

        errs = []

        self.write_log_line(logging.DEBUG, self.__class__.__name__,
                            "admin::handle_device_relocates", "Params=" + str(params))

        for device_file_locator in os.listdir(self.inbox_dir):
            inbox_file_path = os.path.join(self.inbox_dir, device_file_locator)
            inbox_file_locator = self.file_path_to_file_locator(inbox_file_path, 'localhost')
            if inbox_file_locator not in catalog_indexed_entries:
                errs.append("ERROR: Catalog repair needed (Inbox file locator " + inbox_file_locator +
                            " not found in catalog_indexed_entries")
                continue
            if device_file_locator in catalog_indexed_entries:
                continue
            # File has been discarded or moved on device
            device_file_path = self.file_locator_to_file_path(device_file_locator)
            device_file_name = os.path.split(device_file_path)[1]
            device = self.file_locator_to_device(device_file_locator)
            md5 = get_file_md5(inbox_file_path)
            if md5 not in catalog_indexed_entries_by_md5:
                errs.append("ERROR: Internal error: md5 " + md5 + " for inbox file locator " + inbox_file_locator +
                            " not found in internal variable catalog_indexed_entries_by_md5")
            else:
                # A relocated copy would have the same device and name
                relocated_locator = None
                for catalog_indexed_entry in catalog_indexed_entries_by_md5[md5]:
                    (locator, _, _) = catalog_indexed_entry
                    if self.file_locator_to_device(locator) != device:
                        continue
                    path = self.file_locator_to_file_path(locator)
                    name = os.path.split(path)[1]
                    if name == device_file_name:
                        relocated_locator = locator
                        break
                if relocated_locator is not None:
                    if dryrun:
                        self.write_log_line(logging.DEBUG, self.__class__.__name__,
                                            "handle_device_relocates:dryrun:RelocationFound:Removing",
                                            "InboxFile=" + inbox_file_path + " RelocatedLocator " + relocated_locator)
                    else:
                        self.write_log_line(logging.DEBUG, self.__class__.__name__,
                                            "handle_device_relocates:DuplicatesFound:Removing",
                                            "InboxFile=" + inbox_file_path + " RelocatedLocator " + relocated_locator)
                        os.remove(inbox_file_path)
                        self.delete_catalog_entry(inbox_file_locator)
        return (errs, catalog_indexed_entries, catalog_indexed_entries_by_md5)

    def do_admin_repair_catalog(self, params, catalog_indexed_entries, dryrun):

        errs = []

        self.write_log_line(logging.DEBUG, self.__class__.__name__, "admin::repair_catalog", "Params=" + str(params))

        for catalog_file_name in os.listdir(self.catalog_dir):
            catalog_file_path = os.path.join(self.catalog_dir, catalog_file_name)
            # TODO: Put in timed mutex
            with open(catalog_file_path) as fd:
                lines = fd.readlines()
            for line in lines:
                if line.strip() == "":
                    continue
                words = line.strip().split("\t")
                if len(words) != 3:
                    continue
                (file_locator, mtime, sz) = words
                # If this catalog entry is of a local file verify the file exists
                device = self.file_locator_to_device(file_locator)
                if device == 'localhost':
                    file_path = self.file_locator_to_file_path(file_locator)
                    if os.path.isfile(file_path) == False:
                        # The local file does not exist, remove this catalog entry
                        if dryrun:
                            self.write_log_line(logging.DEBUG, self.__class__.__name__,
                                                "repair_catalog:dryrun:MissingLocalFile",
                                                "File=" + file_path)
                        else:
                            self.write_log_line(logging.DEBUG, self.__class__.__name__,
                                                "repair_catalog:MissingLocalFile",
                                                "File=" + file_path)
                            self.delete_catalog_entry(file_locator)
                            if file_locator in catalog_indexed_entries:
                                del catalog_indexed_entries[file_locator]
                        continue
                # If there is no catalog indexed entry for this file, add one
                if file_locator not in catalog_indexed_entries:
                    if dryrun:
                        self.write_log_line(logging.DEBUG, self.__class__.__name__,
                                            "repair_catalog:dryrun:AddingCatalogIndexedEntry",
                                            "CatalogFile=" + catalog_file_name)
                    else:
                        self.write_log_line(logging.DEBUG, self.__class__.__name__,
                                            "repair_catalog:AddingCatalogIndexedEntry",
                                            "CatalogFile=" + catalog_file_name)
                        self.add_catalog_indexed_entry(file_locator, catalog_file_path)
                        catalog_indexed_entries[file_locator] = (catalog_file_name, mtime, sz)

        # If any inbox copies of device files or any device file locators in inbox not in catalog, add them
        for device_file_locator in os.listdir(self.inbox_dir):

            inbox_file_path = os.path.join(self.inbox_dir, device_file_locator)
            inbox_file_locator = self.file_path_to_file_locator(inbox_file_path, 'localhost')

            # If a local file's copy is mistakenly in the inbox dir then if the local file exists
            # delete the copy otherwise relocate the copy to the local location
            # depending on whether the original also exists or is missing
            device = self.file_locator_to_device(device_file_locator)
            if device == 'localhost':
                local_file_path = self.file_locator_to_file_path(device_file_locator)
                if os.path.isfile(local_file_path):
                    # Local file also exists, just remove this copy
                    if dryrun:
                        self.write_log_line(logging.DEBUG, self.__class__.__name__,
                                            "repair_catalog:dryrun:RemovingMisplacedInboxLocator",
                                            "FilePath=" + local_file_path)
                    else:
                        self.write_log_line(logging.DEBUG, self.__class__.__name__,
                                            "repair_catalog:RemovingMisplacedInboxLocator",
                                            "FilePath=" + local_file_path)
                        os.remove(inbox_file_path)
                else:
                    # Local file does not exist. Move this copy to the local location
                    if dryrun:
                        self.write_log_line(logging.DEBUG, self.__class__.__name__,
                                            "repair_catalog:dryrun:RelocatingMisplacedInboxLocator",
                                            "FilePath=" + local_file_path)
                    else:
                        self.write_log_line(logging.DEBUG, self.__class__.__name__,
                                            "repair_catalog:RelocatingMisplacedInboxLocator",
                                            "FilePath=" + local_file_path)
                        shutil.move(inbox_file_path, local_file_path)
                continue


            # If catalog indexed entries exist for both the device file locator and for the inbox copy,
            # no further action needed
            if device_file_locator in catalog_indexed_entries and inbox_file_locator in catalog_indexed_entries:
                continue

            # Get the file stats needed for both copies
            file_md5 = get_file_md5(inbox_file_path)
            file_mtime = os.path.getmtime(inbox_file_path)
            file_bytes = os.path.getsize(inbox_file_path)

            if device_file_locator not in catalog_indexed_entries:
                if dryrun:
                    self.write_log_line(logging.DEBUG, self.__class__.__name__,
                                        "repair_catalog:dryrun:AddingCatalogEntry",
                                        "DeviceFileLocator=" + device_file_locator)
                else:
                    self.write_log_line(logging.DEBUG, self.__class__.__name__,
                                        "repair_catalog:AddingCatalogEntry",
                                        "DeviceFileLocator=" + device_file_locator)
                    self.add_catalog_entry(device_file_locator, file_md5, file_mtime, file_bytes)
            if inbox_file_locator not in catalog_indexed_entries:
                if dryrun:
                    self.write_log_line(logging.DEBUG, self.__class__.__name__,
                                        "repair_catalog:dryrun:AddingCatalogEntry",
                                        "InboxFileLocator=" + inbox_file_locator)
                else:
                    self.write_log_line(logging.DEBUG, self.__class__.__name__,
                                        "repair_catalog:AddingCatalogEntry",
                                        "InboxFileLocator=" + inbox_file_locator)
                    self.add_catalog_entry(inbox_file_locator, file_md5, file_mtime, file_bytes)

        return (errs, catalog_indexed_entries)

    def get_device_files_map(self, catalog_indexed_entries, exclude_dirs, exclude_files, include_files):
        device_files_map = {}
        device_added_files_map = {}
        device_scan_list = self.get_device_scan_list(exclude_dirs, exclude_files, include_files)
        for (file_locator, device_file_mtime, device_file_bytes) in device_scan_list:
            device_files_map[file_locator] = (device_file_mtime, device_file_bytes)
            if file_locator not in catalog_indexed_entries:
                device_added_files_map[file_locator] = (device_file_mtime, device_file_bytes)
            else:
                (_, local_file_mtime, local_file_device_bytes) =\
                catalog_indexed_entries[file_locator]
                if local_file_mtime != device_file_mtime or local_file_device_bytes != device_file_bytes:
                    device_added_files_map[file_locator] = (device_file_mtime, device_file_bytes)
        return (device_files_map, device_added_files_map)

    def get_catalog_indexed_entries(self, admin_mode = False):
        catalog_indexed_entries = {}
        exclude_dirs_list = []
        exclude_files_list = []
        include_files_list = []
        if self.is_config_value_present(self.device, "exclude_dirs", "device"):
            exclude_dirs_list = self.get_config_value(self.device, "exclude_dirs", "device")
            if exclude_dirs_list is None:
                exclude_dirs_list = []
        if self.is_config_value_present(self.device, "exclude_files", "device"):
            exclude_files_list = self.get_config_value(self.device, "exclude_files", "device")
            if exclude_files_list is None:
                exclude_files_list = []
        if self.is_config_value_present(self.device, "include_files", "device"):
            include_files_list = self.get_config_value(self.device, "include_files", "device")
            if include_files_list is None:
                include_files_list = []
        for file_locator in os.listdir(self.catalog_index_dir):
            if admin_mode == False:
                if self.file_locator_to_device(file_locator) != self.device:
                    continue
                if self.is_file_excluded(file_locator, exclude_dirs_list, exclude_files_list, include_files_list):
                    continue
            file_locator_path = os.path.join(self.catalog_index_dir, file_locator)
            if not os.path.islink(file_locator_path):
                continue
            (md5, device_mtime, device_file_bytes, err) = self.get_catalog_entry(file_locator)
            if err != "":
                self.write_log_line(logging.ERROR, self.__class__.__name__, "GetLocalRemotesMap",
                                    "Errors=" + str(err))
                continue
            catalog_indexed_entries[file_locator] = (md5, device_mtime, device_file_bytes)
        with open("/tmp/catalog_indexed_entries.txt", "w") as fd:
            for key in catalog_indexed_entries:
                fd.write(key + "\n")
        return catalog_indexed_entries

    def is_file_excluded(self, file_locator, exclude_dirs_list, exclude_files_list, include_files_list):
        file_path = self.file_locator_to_file_path(file_locator)
        file_path = os.path.realpath(file_path)
        if file_path in include_files_list:
            return False
        if file_path in exclude_files_list:
            return True
        for exclude_dir in exclude_dirs_list:
            if file_path.startswith(exclude_dir):
                return True

    def get_catalog_entry(self, file_locator):
        # TODO: Put in timed mutex
        # Some of the error conditions encountered here may result from interruptions to earlier runs that leave
        # files in inconsistent states. For such situations we return null values along with an an error message.
        # These structural breaks should be handled by executing a admin command to rebuild broken files.
        file_locator_path = os.path.join(self.catalog_index_dir, file_locator)
        if not os.path.islink(file_locator_path):
            return (None, None, None, "File locator " +  file_locator_path + " is not a link")
        catalog_file_name = os.readlink(file_locator_path)
        if not catalog_file_name.startswith(self.catalog_dir):
            return (None, None, None, ("Catalog file name %s is not in catalog dir %s") %
                    (catalog_file_name, self.catalog_dir))
        md5 = os.path.split(catalog_file_name)[1]
        # TODO: Put in mutex with time out detection
        with open(catalog_file_name) as fd:
            lines = fd.readlines()
            for index in range(len(lines)):
                line = lines[index]
                if line.startswith(file_locator + "\t"):
                    words = line.strip().split("\t")
                    if len(words) != 3:
                        return (None, None, None, ("Malformed catalog line %d ('%s') in catalog file %s") %
                                (index + 1, line.strip(), catalog_file_name))
                    errors = ""
                    device_mtime = None
                    device_file_bytes = None
                    try:
                        device_mtime = float(words[-2])
                    except ValueError:
                        errors += ((" Invalid float %s device-mtime in catalog line %d ('%s') in catalog file %s.") %
                                (words[-2], index + 1, line.strip(), catalog_file_name))

                    try:
                        device_file_bytes = int(words[-1])
                    except ValueError:
                        errors += ((" Invalid int %s device-file-bytes in catalog line %d ('%s') in catalog file %s") %
                                (words[-1], index + 1, line.strip(), catalog_file_name))
                    if errors != "":
                        return (None, None, None, errors)
                    return (md5, device_mtime, device_file_bytes, "")
        return (None, None, None, "")

    def add_catalog_entry(self, file_locator, file_md5, file_mtime, file_bytes):
        catalog_file_path = os.path.join(self.catalog_dir, file_md5)
        lines = []
        # TODO: Put in mutex with time out detection
        if os.path.isfile(catalog_file_path):
            with open(catalog_file_path, "r") as fd:
                lines = fd.readlines()
        lines.append(file_locator + "\t" + str(file_mtime) + "\t" + str(file_bytes) + "\n")
        temp_file_name = catalog_file_path + ".tmp"
        with open(temp_file_name, "w") as fd:
            for line in lines:
                if line.strip() == "":
                    continue
                fd.write(line.strip() + "\n")
        os.rename(temp_file_name, catalog_file_path)
        self.add_catalog_indexed_entry(file_locator, catalog_file_path)

    def delete_catalog_entry(self, file_locator):
        catatalog_indexed_entry_file_path = os.path.join(self.catalog_index_dir, file_locator)
        if not os.path.islink(catatalog_indexed_entry_file_path):
            return
        catalog_file_name = os.readlink(catatalog_indexed_entry_file_path)
        if not catalog_file_name.startswith(self.catalog_dir):
            return
        # TODO: Put in mutex with time out detection
        with open(catalog_file_name) as fd:
            lines = fd.readlines()
        temp_file_name = catalog_file_name + ".tmp"
        with open(temp_file_name, "w") as fd:
            for line in lines:
                if line.strip() == "":
                    continue
                if line.startswith(file_locator + "\t") is False:
                    fd.write(line.strip() + "\n")
        os.rename(temp_file_name, catalog_file_name)
        os.unlink(catatalog_indexed_entry_file_path)

    def get_catalog_indexed_entries_by_md5(self, catalog_indexed_entries):
        catalog_indexed_entries_by_md5 = {}
        for file_locator in catalog_indexed_entries:
            (md5, device_mtime, device_file_bytes) = catalog_indexed_entries[file_locator]
            if md5 not in catalog_indexed_entries_by_md5:
                catalog_indexed_entries_by_md5[md5] = []
            catalog_indexed_entries_by_md5[md5].append( (file_locator, device_mtime, device_file_bytes) )
        return catalog_indexed_entries_by_md5

    def add_catalog_indexed_entry(self, file_locator, catalog_file_path):
        symlink_name = os.path.join(self.catalog_index_dir, file_locator)
        if os.path.islink(symlink_name):
            os.unlink(symlink_name)
        elif os.path.isfile(symlink_name):
            os.remove(symlink_name)
        os.symlink(catalog_file_path, symlink_name)

    # Returns (mounted-exclude-dirs-list, mounted-exclude-files-list,
    # mounted-include-files-list) by converting these lists from updated config
    # to local mount path based forms
    def get_mounted_exclude_include_lists(self):
        raise RuntimeError("This function should be implemented in an instantiated subclass")

    # Returns a list [(source-file-file-locator, source-file-mtime, source-file-bytes)]
    def get_device_scan_list(self, mounted_exclude_dirs_list, mounted_exclude_files_list, mounted_include_files_list):
        raise RuntimeError("This function should be implemented in an instantiated subclass")

    # Returns True if the device file exists and is a file
    def is_file_device(self, device_file):
        raise RuntimeError("This function should be implemented in an instantiated subclass")

    # Returns True if the local file exists and is a file
    def is_file_local(self, local_file):
        return os.path.isfile(local_file)

    # Compares a source and a destination file taking into account their
    # respective file systems. Returns True if they appear to be identical
    def cmp_file(self, device_file, local_file):
        raise RuntimeError("This function should be implemented in an instantiated subclass")

    # Copies a device file to a local file taking into account device file system.
    def copy_file_in(self, device_file, local_file):
        raise RuntimeError("This function should be implemented in an instantiated subclass")

    # Copies a local file to a device file taking into account device file system.
    def copy_file_out(self, local_file, device_file):
        raise RuntimeError("This function should be implemented in an instantiated subclass")

    # Moves a device file to a local file taking into account device file system.
    def move_file_in(self, device_file, local_file):
        raise RuntimeError("This function should be implemented in an instantiated subclass")

    # Deletes a source file
    def delete_device_file(self, device_file):
        raise RuntimeError("This function should be implemented in an instantiated subclass")

    # Gets source file size in bytes
    def get_device_file_bytes(self, device_file):
        raise RuntimeError("This function should be implemented in an instantiated subclass")

    # Gets source file modification time
    def get_device_file_mtime(self, device_file):
        raise RuntimeError("This function should be implemented in an instantiated subclass")

    # Gets source file MD5 (checksum)
    def get_device_file_md5(self, device_file):
        raise RuntimeError("This function should be implemented in an instantiated subclass")

    # Returns the total number of bytes (rounded up to the destinaion block size
    # so as to indicate space actually used) a destination file would occupy on
    # its file system. Also returns a disk id (meaningful when the destination
    # area comprises multiple disks each with a different amount of free space
    # and operations check for out-of-space situations).
    def get_local_file_bytes_and_disk_id(self, device_file, local_file):
        raise RuntimeError("This function should be implemented in an instantiated subclass")

    # Returns the total number of available bytes (must be a multiple of the
    # destination block size for accuracy) on the disk a destination file would
    # be on
    def get_local_drv_free_bytes(self, local_file):
        raise RuntimeError("This function should be implemented in an instantiated subclass")

    # Return true if config section/option value is present
    def is_config_value_present(self, section, option, subsection = None):
        if self.updated_config:
            cfg = self.updated_config
        else:
            cfg = self.original_config
        if subsection:
            return section in cfg and subsection in cfg[section] and option in cfg[section][subsection]
        else:
            return section in cfg and option in cfg[section]

    # Get config section/option value
    def get_config_value(self, section, option, subsection = None):
        if self.updated_config:
            cfg = self.updated_config
        else:
            cfg = self.original_config
        if subsection:
            return cfg[section][subsection][option]
        else:
            return cfg[section][option]

    # Get a list of config option values for the given section
    def get_config_options(self, section, subsection = None):
        if self.updated_config:
            cfg = self.updated_config
        else:
            cfg = self.original_config
        options = []
        if subsection:
            for option in cfg[section][subsection]:
                options.append(cfg[section][option])
        else:
            for option in cfg[section]:
                options.append(cfg[section][option])
        return options

# Base class for all links that can represent the source as a File System.
# (Examples of file system sources are mtp or sshfs mounted source devices - but
# but not sources such as Google Drive or Google Photos which do not "naturally"
# look like filesystems)
class UncloudSrcIsFs(UncloudBase):

    def __init__(self, responses_file_path, link, device, original_config, updated_config, final_commands_list):
        super(UncloudSrcIsFs, self).__init__(responses_file_path, link, device, original_config, updated_config,
                                             final_commands_list)
        self.mnt_path_prefix_to_device_path_prefix = {}
        self.device_path_prefix_to_mnt_path_prefix = {}

    def __del__(self):
        super(UncloudSrcIsFs, self).__del__()

    def set_device_mount_mappings(self, mnt_path_prefix_to_device_path_prefix,
                 device_path_prefix_to_mnt_path_prefix, device_paths):
        self.mnt_path_prefix_to_device_path_prefix = mnt_path_prefix_to_device_path_prefix
        self.device_path_prefix_to_mnt_path_prefix = device_path_prefix_to_mnt_path_prefix
        self.device_paths = device_paths

    def device_file_path_to_mnt_file_path(self, device_file):
        if self.device_path_prefix_to_mnt_path_prefix == {}:
            return device_file
        for device_path_prefix in self.device_path_prefix_to_mnt_path_prefix:
            if device_file.startswith(device_path_prefix):
                return self.device_path_prefix_to_mnt_path_prefix[device_path_prefix] +\
                    device_file[len(device_path_prefix) : ]
        return None

    def mnt_file_path_to_device_file_path(self, mnt_file):
        if self.mnt_path_prefix_to_device_path_prefix == {}:
            return mnt_file
        for mnt_path_prefix in self.mnt_path_prefix_to_device_path_prefix:
            if mnt_file.startswith(mnt_path_prefix):
                return self.mnt_path_prefix_to_device_path_prefix[mnt_path_prefix] +\
                    mnt_file[len(mnt_path_prefix) : ]
        return None

    def get_mounted_exclude_include_lists(self):
        mounted_exclude_dirs_list = []
        mounted_exclude_files_list = []
        mounted_include_files_list = []
        if self.is_config_value_present(self.device, "exclude_dirs", "device"):
            device_exclude_dirs = self.get_config_value(self.device, "exclude_dirs", "device")
            if device_exclude_dirs is not None:
                for device_exclude_dir in device_exclude_dirs:
                    mounted_exclude_dirs_list.append(self.device_file_path_to_mnt_file_path(device_exclude_dir))
        if self.is_config_value_present(self.device, "exclude_files", "device"):
            device_exclude_files = self.get_config_value(self.device, "exclude_files", "device")
            if device_exclude_files is not None:
                for device_exclude_dir in device_exclude_files:
                    mounted_exclude_files_list.append(self.device_file_path_to_mnt_file_path(device_exclude_dir))
        if self.is_config_value_present(self.device, "include_files", "device"):
            device_include_files = self.get_config_value(self.device, "include_files", "device")
            if device_include_files is not None:
                for device_include_dir in device_include_files:
                    mounted_include_files_list.append(self.device_file_path_to_mnt_file_path(device_include_dir))
        return (mounted_exclude_dirs_list, mounted_exclude_files_list, mounted_include_files_list)

    # Returns a list [(source-file-file-locator, source-file-mtime, source-file-bytes)]
    def get_device_scan_list(self, mounted_exclude_dirs_list, mounted_exclude_files_list, mounted_include_files_list):
        device_scan_list = []
        for device_path in self.device_paths:
            mnt_path = self.device_file_path_to_mnt_file_path(device_path)
            for root, dirs, files in os.walk(mnt_path, topdown = False):
                exclude = False
                for mounted_exclude_dir in mounted_exclude_dirs_list:
                    if root.startswith(mounted_exclude_dir):
                        exclude = True
                        break
                if exclude:
                    continue
                for name in files:
                    file_path = os.path.join(root, name)
                    if file_path in mounted_exclude_files_list:
                        continue
                    ext = os.path.splitext(name)[1].lower()
                    if ext[1:] not in self.original_config["file_category_for_file_extension"]:
                       continue
                    device_path_on_device = self.mnt_file_path_to_device_file_path(file_path)
                    device_file_locator = self.device_file_path_to_file_locator(device_path_on_device)
                    if len(device_file_locator) > self.max_file_locator_size:
                        self.write_log_line(logging.ERROR, self.__class__.__name__, "Device scan",
                                            "ERROR: device_file_locator " + str(device_file_locator) +
                                            " for device_file " + str(device_path_on_device) +
                                            " exceeds size limit, discarding")
                        continue
                    device_file_mtime = self.get_device_file_mtime(device_path_on_device)
                    device_file_bytes = self.get_device_file_bytes(device_path_on_device)
                    device_scan_list.append( (device_file_locator, device_file_mtime, device_file_bytes) )
            for file_path in mounted_include_files_list:
                if os.path.isfile(file_path) == False or os.access(file_path, os.R_OK) == False:
                    continue
                device_path_on_device = self.mnt_file_path_to_device_file_path(file_path)
                device_file_locator = self.device_file_path_to_file_locator(device_path_on_device)
                if len(device_file_locator) > self.max_file_locator_size:
                    self.write_log_line(logging.ERROR, self.__class__.__name__, "Device scan",
                                        "ERROR: device_file_locator " + str(device_file_locator) +
                                        " for device_file " + str(device_path_on_device) +
                                        " exceeds size limit, discarding")
                    continue
                device_file_mtime = self.get_device_file_mtime(device_path_on_device)
                device_file_bytes = self.get_device_file_bytes(device_path_on_device)
                device_scan_list.append( (device_file_locator, device_file_mtime, device_file_bytes) )
        return device_scan_list

    def is_file_device(self, device_file):
        return os.path.isfile(self.device_file_path_to_mnt_file_path(device_file))

    def cmp_file(self, device_file, local_file):
        if os.path.islink(local_file):
            md5 = self.get_device_file_md5(device_file)
            return md5 == os.readlink(local_file)
        return filecmp.cmp(self.device_file_path_to_mnt_file_path(device_file), local_file)

    def copy_file_in(self, device_file, local_file):
        shutil.copy2(self.device_file_path_to_mnt_file_path(device_file), local_file)

    def copy_file_out(self, local_file, device_file):
        shutil.copy2(local_file, self.device_file_path_to_mnt_file_path(device_file) )

    def move_file_in(self, device_file, local_file):
        shutil.move(self.device_file_path_to_mnt_file_path(device_file), local_file)

    def delete_device_file(self, device_file):
        os.remove(self.device_file_path_to_mnt_file_path(device_file))

    def get_device_file_bytes(self, device_file):
        return os.path.getsize(self.device_file_path_to_mnt_file_path(device_file))

    def get_device_file_mtime(self, device_file):
        return os.path.getmtime(self.device_file_path_to_mnt_file_path(device_file))

    def get_device_file_md5(self, device_file):
        return get_file_md5(self.device_file_path_to_mnt_file_path(device_file))

    def get_local_file_bytes_and_disk_id(self, device_file, local_file):
        size_in_bytes = self.get_device_file_bytes(device_file)
        # local_file may or may not exist, use drive - which should exist - to get statvfs info
        (local_drv, _) = os.path.split(local_file)
        statvfs = os.statvfs(local_drv)
        block_size = statvfs.f_frsize
        # Python 3.7 onwards reports the actual drive ID from Linux. Else we just use a common id of 0
        if sys.version_info[0] == 3 and sys.version_info[1] >= 7:
            return (block_size * (int( (size_in_bytes - 1)/ block_size) + 1), statvfs.f_fsid)
        else:
            return (block_size * (int( (size_in_bytes - 1)/ block_size) + 1), 0)

    def get_local_drv_free_bytes(self, local_file):
        # local_file may or may not exist, use drive - which should exist - to get statvfs info
        (local_drv, _) = os.path.split(local_file)
        statvfs = os.statvfs(local_drv)
        return statvfs.f_frsize * statvfs.f_bavail

class UncloudMtpUbuntu(UncloudSrcIsFs):

    def __init__(self, responses_file_path, link, device, original_config, updated_config, final_commands_list):
        super(UncloudMtpUbuntu, self).__init__(responses_file_path, link, device, original_config, updated_config,
                                               final_commands_list)


    def __del__(self):
        super(UncloudMtpUbuntu, self).__del__()


    def connect(self):
        super(UncloudMtpUbuntu, self).connect()

        self.mnt_path_prefix_to_device_path_prefix = {}
        self.device_path_prefix_to_mnt_path_prefix = {}

        # search for MTP mounted device

        mounted_path_of_device_file_system = ""
        duplicate_detected_file_systems = []
        file_system_base_wildcard = self.get_config_value(self.link, "file_system_base")
        for file_system_base in glob.glob(file_system_base_wildcard):
            if not os.access(file_system_base, os.R_OK):
                continue
            dirs = os.listdir(file_system_base)
            if dirs == []:
                continue
            if len(dirs) != 1:
                for dir_name in dirs:
                    duplicate_detected_file_systems.append(
                        os.path.join(file_system_base, dir_name))
                continue
            if mounted_path_of_device_file_system != "":
                if duplicate_detected_file_systems == []:
                    duplicate_detected_file_systems.append(mounted_path_of_device_file_system)
                    duplicate_detected_file_systems.append(
                        os.path.join(file_system_base, dirs[0]))
                    continue
            dir_to_use = os.path.join(file_system_base, dirs[0])
            if not os.access(dir_to_use, os.R_OK):
                continue
            mounted_path_of_device_file_system = dir_to_use

        if mounted_path_of_device_file_system == "":
            raise RuntimeError(self.link + ": No self.device found. Ensure your self.device connected to USB. "
                               "(If self.device is phone it may be requesting permission "
                               "to allow access")
        if duplicate_detected_file_systems != []:
            raise RuntimeError(self.link + ": You may have multiple self.devices attached to USB. "
                               "self.devices seen on " +
                                   str(duplicate_detected_file_systems))

        errors = []
        mnt_dir_device_path_pairs =\
            self.get_config_value(self.device, "mnt_dir_device_path_pairs", self.link)
        if len(mnt_dir_device_path_pairs) % 2 != 0:
            errors.append(self.link + ": Odd number of '" + self.link + "__" + "mnt_dir_device_path_pairs" +
                          "' values for device " + self.device + " in ini file(s)")
        else:
            index = 0
            device_paths = []
            while index < len(mnt_dir_device_path_pairs):
                mnt_dir = mnt_dir_device_path_pairs[index]
                device_path = mnt_dir_device_path_pairs[index +1]
                index += 2
                device_paths.append(device_path)
                mnt_path = os.path.join(mounted_path_of_device_file_system, mnt_dir)
                if os.path.isdir(mnt_path) == False:
                    errors.append(self.link + ": Mount path not found for mnt dir " + mnt_dir +
                                  " in '" + self.link + "__" + "mnt_dir_device_path_pairs" +
                                  "' for device " + self.device + " in ini file(s)")
                else:
                    self.mnt_path_prefix_to_device_path_prefix[mnt_path] = device_path
                    self.device_path_prefix_to_mnt_path_prefix[device_path] = mnt_path

            if errors != []:
                raise RuntimeError(self.link + ": Validation errors " + str(errors) + " for self.device " +
                                   self.device + " in ini file(s) " )

            super(UncloudMtpUbuntu, self).set_device_mount_mappings(self.mnt_path_prefix_to_device_path_prefix,
                                                 self.device_path_prefix_to_mnt_path_prefix, device_paths)

            return True

    def disconnect(self):
        super(UncloudMtpUbuntu, self).disconnect()


class UncloudUsbUbuntu(UncloudSrcIsFs):

    def __init__(self, responses_file_path, link, device, original_config, updated_config, final_commands_list):

        super(UncloudUsbUbuntu, self).__init__(responses_file_path, link, device, original_config, updated_config,
                                               final_commands_list)

        self.mnt_path_prefix_to_device_path_prefix = {}
        self.device_path_prefix_to_mnt_path_prefix = {}

        # search for USB mounted device

        path_wildcard = self.get_config_value(self.link, "file_system_base")
        errors = []
        mnt_dir_device_path_pairs =\
            self.get_config_value(device, "mnt_dir_device_path_pairs", self.link)
        if len(mnt_dir_device_path_pairs) % 2 != 0:
            errors.append(self.link +
                          ": Odd number of '" + self.link + "__" + "mnt_dir_device_path_pairs" + "' values for device "
                          + device + " in ini file(s)")
        else:
            path_found = None
            for mounted_path_of_device_file_system in glob.glob(path_wildcard):
                if os.path.isdir(mounted_path_of_device_file_system) == False or\
                    os.access(mounted_path_of_device_file_system, os.R_OK) == False:
                    continue
                index = 0
                match = True
                while index < len(mnt_dir_device_path_pairs):
                    path = os.path.join(mounted_path_of_device_file_system, mnt_dir_device_path_pairs[index])
                    if os.path.isdir(path) == False:
                        match = False
                        break
                    index += 2
                if match:
                    if path_found:
                        errors.append(self.link + ": Duplicate device: Matching USB devices found mounted at  " +
                                      path_found + " and " + mounted_path_of_device_file_system +
                                      " (do you have two devices plugged in?) in '" + self.link + "__" +
                                      "mnt_dir_device_path_pairs" + "' for device " + device + " in ini file(s)")
                        continue
                    else:
                        path_found = mounted_path_of_device_file_system
                index = 0
                device_paths = []
                while index < len(mnt_dir_device_path_pairs):
                    mnt_dir = mnt_dir_device_path_pairs[index]
                    device_path = mnt_dir_device_path_pairs[index +1]
                    index += 2
                    device_paths.append(device_path)
                    mnt_path = os.path.join(mounted_path_of_device_file_system, mnt_dir)
                    if os.path.isdir(mnt_path) == False:
                        errors.append(self.link + ": Mount path not found for mnt dir " + mnt_dir +
                                      " in '" + self.link + "__" + "mnt_dir_device_path_pairs" +
                                      "' for device " + device + " in ini file(s)")
                    else:
                        self.mnt_path_prefix_to_device_path_prefix[mnt_path] = device_path
                        self.device_path_prefix_to_mnt_path_prefix[device_path] = mnt_path

            if errors != []:
                raise RuntimeError(self.link + ": Validation errors " + str(errors) + " for device " +
                                   device + " in ini file(s) " )

            super(UncloudUsbUbuntu, self).set_device_mount_mappings(self.mnt_path_prefix_to_device_path_prefix,
                                                 self.device_path_prefix_to_mnt_path_prefix, device_paths)

    def __del__(self):
        super(UncloudUsbUbuntu, self).__del__()


class UncloudAndroidSSHelper(UncloudSrcIsFs):

    def __init__(self, responses_file_path, link, device, original_config, updated_config, final_commands_list):

        super(UncloudAndroidSSHelper, self).__init__(responses_file_path, link, device, original_config, updated_config,
                                               final_commands_list)

    def __del__(self):
        super(UncloudAndroidSSHelper, self).__del__()


    def connect(self):
        if super(UncloudAndroidSSHelper, self).connect() == False:
            return False

        self.mnt_path_prefix_to_device_path_prefix = {}
        self.device_path_prefix_to_mnt_path_prefix = {}

        self.dirs_to_umount = []

        # search for USB mounted self.self.device

        mounted_path_of_device_file_system = self.get_config_value(self.link, "mnt_pt")
        sshfs__user = self.get_config_value(self.device, "user", self.link)
        sshfs__ip = self.get_config_value(self.device, "ip", self.link)
        sshfs__port = self.get_config_value(self.device, "port", self.link)
        sshfs_bonjour_device_name =\
            self.get_config_value(self.device, "bonjour_device_name", self.link)

        errors = []

        if sshfs__ip == "" and sshfs_bonjour_device_name == "":
            errors.append(self.link + ": Either ip or bonjour_name must be specified for device "
                          + self.device + " in ini file(s)")
        else:
            located_ip = self.locate_through_bonjour(sshfs_bonjour_device_name)
            if located_ip is None:
                if sshfs__ip == None:
                    errors.append(self.link + ": ip not specified and could not locate bonjour_device_name " +
                                      sshfs_bonjour_device_name + " for device " + self.device + " in ini file(s)")
            else:
                sshfs__ip = located_ip

        to_mount_pairs = self.get_config_value(self.device, "to_mount_pairs", self.link)
        if len(to_mount_pairs) % 2 != 0:
            errors.append(self.link + ": Odd number of '" + self.link + "__" + "to_mount_pairs" + "' values for device "
                          + self.device + " in ini file(s)")
        else:
            index = 0
            while index < len(to_mount_pairs):
                device_path = to_mount_pairs[index]
                mnt_dir = to_mount_pairs[index +1]
                index += 2
                mnt_path = os.path.join(mounted_path_of_device_file_system, mnt_dir)
                self.dirs_to_umount.append(mnt_path)
                os.makedirs(mnt_path, exist_ok = True)
                mnt_cmd = ["sshfs", "-o", "UserKnownHostsFile=/dev/null", "-o",
                           "StrictHostKeyChecking=no", "-o", "idmap=user",
                           sshfs__user + "@" + sshfs__ip + ":" + device_path,
                           mnt_path, "-p", str(sshfs__port)]
                try:
                    subprocess.check_call(mnt_cmd)
                except subprocess.CalledProcessError as err:
                    raise RuntimeError("Error return from '" + str(err.cmd) + " (" + str(err.output) + ")")

        mnt_dir_device_path_pairs =\
            self.get_config_value(self.device, "mnt_dir_device_path_pairs", self.link)
        if len(mnt_dir_device_path_pairs) % 2 != 0:
            errors.append(self.link + ": Odd number of '" + self.link + "__" +
                          "mnt_dir_device_path_pairs" + "' values for device " + self.device + " in ini file(s)")
        else:
            index = 0
            device_paths = []
            while index < len(mnt_dir_device_path_pairs):
                mnt_dir = mnt_dir_device_path_pairs[index]
                device_path = mnt_dir_device_path_pairs[index +1]
                index += 2
                device_paths.append(device_path)
                mnt_path = os.path.join(mounted_path_of_device_file_system, mnt_dir)
                if os.path.isdir(mnt_path) == False:
                    errors.append(self.link + ": Mount path not found for mnt dir " + mnt_dir +
                                  " in '" + self.link + "__" + "mnt_dir_device_path_pairs" +
                                  "' for device " + self.device + " in ini file(s)")
                else:
                    self.mnt_path_prefix_to_device_path_prefix[mnt_path] = device_path
                    self.device_path_prefix_to_mnt_path_prefix[device_path] = mnt_path

            if errors != []:
                print(self.link + ": Validation errors " + str(errors) + " for self.device " +
                                   self.device + " in ini file(s) " )
                return False

            super(UncloudAndroidSSHelper, self).set_device_mount_mappings(self.mnt_path_prefix_to_device_path_prefix,
                                                 self.device_path_prefix_to_mnt_path_prefix, device_paths)

        return True

    def disconnect(self):
        for dir_to_umount in self.dirs_to_umount:
            umount_cmd = ["fusermount", "-u", dir_to_umount]
            try:
                subprocess.check_call(umount_cmd)
            except subprocess.CalledProcessError as err:
                raise RuntimeError("Error return from '" + err.cmd + " (" + err.output + ")")
        super(UncloudAndroidSSHelper, self).disconnect()

    def locate_through_bonjour(self, bonjour_device_name):
        name_to_use = ""
        for namechar in bonjour_device_name:
            if namechar == '(' or namechar == ')':
                name_to_use += "'" + namechar + "'"
            else:
                name_to_use += namechar
        cmd = "avahi-resolve --name " + name_to_use + ".local"
        try:
            words = subprocess.check_output(cmd, shell= True).split()
        except subprocess.CalledProcessError as err:
            raise RuntimeError("Error return (did you forget to run SSHelper on ph?) from '" + err.cmd + " (" + err.output + ")")

        if len(words) == 2:
            return byte_to_str(words[1])
        return None


class UncloudLocalFs(UncloudSrcIsFs):

    def __init__(self, responses_file_path, link, device, original_config, updated_config, final_commands_list):

        super(UncloudLocalFs, self).__init__(responses_file_path, link, device, original_config, updated_config,
                                             final_commands_list)

        self.mnt_path_prefix_to_device_path_prefix = {}
        self.device_path_prefix_to_mnt_path_prefix = {}

        # search for USB mounted device

        mounted_path_of_device_file_system = self.get_config_value(self.link, "file_system_base")
        if os.path.isdir(mounted_path_of_device_file_system) == False:
            raise RuntimeError(self.link + ": Missing directory 'file_system_base' " + mounted_path_of_device_file_system +
                               " specified in ini file(s)")

        errors = []
        mnt_dir_device_path_pairs = self.get_config_value(device, "mnt_dir_device_path_pairs", self.link)
        if len(mnt_dir_device_path_pairs) % 2 != 0:
            errors.append(self.link + ": Odd number of '" + self.link + "__" +
                          "mnt_dir_device_path_pairs" + "' values for device " + device + " in ini file(s)")
        else:
            index = 0
            device_paths = []
            while index < len(mnt_dir_device_path_pairs):
                mnt_dir = mnt_dir_device_path_pairs[index]
                device_path = mnt_dir_device_path_pairs[index +1]
                index += 2
                device_paths.append(device_path)
                mnt_path = os.path.join(mounted_path_of_device_file_system, mnt_dir)
                if os.path.isdir(mnt_path) == False:
                    errors.append(self.link + ": Mount path not found for mnt dir " + mnt_dir +
                                  " in '" + self.link + "__" +
                                  "mnt_dir_device_path_pairs" + "' for device " + device + " in ini file(s)")
                else:
                    self.mnt_path_prefix_to_device_path_prefix[mnt_path] = device_path
                    self.device_path_prefix_to_mnt_path_prefix[device_path] = mnt_path

            if errors != []:
                raise RuntimeError(self.link + ": Validation errors " + str(errors) + " for device " +
                                   device + " in ini file(s) " )

            super(UncloudLocalFs, self).set_device_mount_mappings(self.mnt_path_prefix_to_device_path_prefix,
                                                 self.device_path_prefix_to_mnt_path_prefix, device_paths)

    def __del__(self):
        super(UncloudLocalFs, self).__del__()


def thread_launch(queue):

    write_log_line(logging.DEBUG, "thread_launch", "Starting")

    while True:
        queue.get().run()


# Called once for each command received, whether from command file or web server or sockets.

# NOTE: At some point, if this JSON gets overly complex, this manual validation code will become
# unwieldy and should be replaced by some form of JSON validator. On the other hand complex
# validation can have the benefit of discouraging JSON changes and facilitating standardization :).

def process_command(responses_file_path, link, device, original_config, updated_config, final_commands_list):

    write_log_line(logging.DEBUG, "CommandProcess", "Starting", "Link=" + link + " Device=" + device)
    if link == "usb_ubuntu":
        obj = UncloudUsbUbuntu(responses_file_path, link, device, original_config, updated_config, final_commands_list)
    elif link == "mtp_ubuntu":
        obj = UncloudMtpUbuntu(responses_file_path, link, device, original_config, updated_config, final_commands_list)
    elif link == "android_sshelper":
        obj = UncloudAndroidSSHelper(responses_file_path, link, device, original_config, updated_config, final_commands_list)
    elif link == "local_fs":
        obj = UncloudLocalFs(responses_file_path, link, device, original_config, updated_config, final_commands_list)
    else:
        obj = None
        assert False
    obj.launch()

def parse_commands_json(config, commands_file):

    errors = []

    link = ""
    device = ""
    final_commands_list = []
    updated_config = None

    only_defaults = config["only_defaults"]

    write_log_line(logging.DEBUG, "CommandsParse", "Starting", "CommandsFile=" + commands_file)

    with open(commands_file) as fd:
        try:
            commands_info = json.load(fd)
            replace_empty_str_with_none(commands_info)
        except Exception as err:
            errors.append("Errror (" + str(err) + " trying to parse commands json file " + commands_file)
            return (link, device, updated_config, final_commands_list, errors)

    write_log_line(logging.DEBUG, "CommandsParse", "ReadCommands", "Commands=" + str(commands_info))

    if isinstance(commands_info, dict) is False:
        errors.append("JSON is not a dict in file " + commands_file)
        return (link, device, updated_config, final_commands_list, errors)

    mandatory_keys = [ "link", "device", "commands"]

    optional_keys = [ "overrides" ]

    for mandatory_key in mandatory_keys:
        if mandatory_key not in commands_info:
            errors.append(("Mandatory key %s not found in file %s") %
                          (mandatory_key, commands_file))

    for key in commands_info:
        if key not in mandatory_keys and key not in optional_keys:
            errors.append(("Illegal key %s (valid keys are %s %s) in file %s") %
                          (key, str(mandatory_keys), str(optional_keys), commands_file))

    if "link" in commands_info: # ie not omitted due to error
        link = commands_info["link"]
        if is_text(link) == False:
            errors.append(("'link' (%s) is not text in file %s") % (str(link), commands_file))
    if "device" in commands_info: # ie not omitted due to error
        device = commands_info["device"]
        if is_text(device) == False:
            errors.append(("'device' (%s) is not text in file %s") % (str(device), commands_file))
    if "commands" in commands_info: # ie not omitted due to error
        commands = commands_info["commands"]
        if isinstance(commands, list) == False:
            errors.append(("'commands' (%s) is not a list in file %s") % (str(commands), commands_file))

    if "overrides" in commands_info:
        overrides = commands_info["overrides"]
        if isinstance(overrides, dict) == False:
            errors.append(("'overrides' %s is not a dict in file %s") %
                          (str(commands_info["overrides"]), commands_file))
        else:
            (updated_config, errs) = apply_overrides(config, overrides)
            for err in errs:
                errors.append (("%s in file %s") % (err, commands_file) )

    if errors != []:
        return (link, device, updated_config, final_commands_list, errors)

    for index in range(len(commands)):

        command_info = commands[index]

        if isinstance(command_info, dict) == False:
            errors.append(("Entry %d (%s) is not a dict in file %s") % (index, str(command_info), commands_file))
            continue

        if len(command_info.keys()) != 1:
            errors.append(("Muliple keys (%s) (the command should be the only key) found in entry %d (%s) in file %s") %
                          (str(command_info.keys()), index, str(command_info), commands_file))
            # If there is at least one key assume the first key is the command and try and do further error checking
            if len(command_info.keys()) == 0:
                continue

        command = list(command_info.keys())[0]

        if is_text(command) == False:
            errors.append(("'command' %s is not text in entry %d (%s) in file %s") %
                          (str(command_info["command"]), index, str(command_info), commands_file))
        else:
            valid_commands = ["import", "dryrun", "export", "cleanup", "admin"]
            if command not in valid_commands:
                errors.append( ("Invalid 'command' %s (valid commands are %s) in entry %d (%s) in file %s") %
                    (command, str(valid_commands), index, str(command_info), commands_file) )
                continue

            mandatory_params =  {
                                "import" : [], "dryrun" : [], "export" : [],
                                "cleanup" : [], "admin": []
                                }
            optional_params =   {
                                "import" : [], "dryrun" : [], "export" : [],
                                "cleanup" : [],"admin": ["handle_device_relocates","repair_catalog"]
                                }

            file_categories = {}
            for ext in config["file_category_for_file_extension"]:
                if ext in only_defaults:
                    continue
                file_categories[config["file_category_for_file_extension"][ext]] = None

            assert set(valid_commands) == set(mandatory_params.keys())
            assert set(valid_commands) == set(optional_params.keys())

            params = command_info[command]
            if params == None:
                params = {}
            if isinstance(params, dict) == False:
                errors.append(("'params' %s is not a dict in entry %d (%s) in file %s") %
                              (str(command_info["params"]), index, str(command_info), commands_file))
            else:
                for mandatory_param in mandatory_params[command]:
                    if mandatory_param not in params:
                        errors.append( ("Mandatory 'param' %s not found for command %s in entry %d (%s) in file %s")
                            % (mandatory_param, command, index, str(command_info), commands_file) )
                for param in params:
                    if param not in mandatory_params[command] and param not in optional_params[command]:
                        errors.append( ("Invalid 'param' %s (valid params are %s,%s) "
                                        "for command %s in entry %d (%s) in file %s") %
                            (param, mandatory_params[command], optional_params[command], command, index,
                            str(command_info), commands_file) )
                if command == "import":
                    pass
                elif command == "dryrun":
                    pass
                elif command == "export":
                    pass
                elif command == "cleanup":
                    pass

                elif command == "admin":

                    if device != "localhost":
                        errors.append( ("'device' (%s) is not 'localhost' in %s in entry %d (%s) in file %s")
                            % (device, command, index, str(command_info), commands_file) )

                    if link != "local_fs":
                        errors.append( ("'link' (%s) is not 'local_fs' in %s in entry %d (%s) in file %s")
                            % (link, command, index, str(command_info), commands_file) )

                    admin_cmd_mandatory_keys = []
                    admin_cmd_optional_keys = ["handle_device_relocates", "repair_catalog"]
                    for admin_cmd_mandatory_key in admin_cmd_mandatory_keys:
                        if admin_cmd_mandatory_key not in command_info:
                            errors.append( ("Mandatory entry %s not found in %s in entry %d (%s) in file %s")
                                % (admin_cmd_mandatory_key, command, index, str(command_info), commands_file) )
                    for key in command_info[command]:
                        if key not in admin_cmd_mandatory_keys and key not in admin_cmd_optional_keys:
                            errors.append( ("Invalid entry %s (valid entries are %s,%s) found in %s in entry %d"
                                            "(%s) in file %s")
                                % (key, str(admin_cmd_mandatory_keys), str(admin_cmd_optional_keys), command, index,
                                   str(command_info), commands_file) )

                    if "handle_device_relocates" in command_info[command]:
                        handle_device_relocates_info = command_info[command]["handle_device_relocates"]
                        if handle_device_relocates_info is not None and isinstance(handle_device_relocates_info, dict) == False:
                            errors.append( ("%s['handle_device_relocates'] (%s) not a dict in entry %d (%s) in file %s")
                                % (command, str(handle_device_relocates_info), index, str(command_info), commands_file) )
                        elif handle_device_relocates_info is not None:
                            handle_device_relocates_mandatory_keys = []
                            handle_device_relocates_optional_keys = ["dryrun"]
                            for handle_device_relocates_mandatory_key in handle_device_relocates_mandatory_keys:
                                if handle_device_relocates_mandatory_key not in handle_device_relocates_info:
                                    errors.append( ("Mandatory key %s not found in %s['handle_device_relocates'] in entry"
                                                    " %d (%s) in file %s") % (handle_device_relocates_mandatory_key,
                                                    command, index, str(command_info), commands_file) )
                            for handle_device_relocates_key in handle_device_relocates_info:
                                if handle_device_relocates_key not in handle_device_relocates_mandatory_keys and\
                                    handle_device_relocates_key not in handle_device_relocates_optional_keys:
                                    errors.append( ("Invalid entry %s (valid entries are %s,%s) found in "
                                                    "%s['handle_device_relocates'] in entry %d (%s) in file %s") %\
                                                   (handle_device_relocates_key,str(handle_device_relocates_mandatory_keys), 
                                                    str(handle_device_relocates_optional_keys), command, index,
                                                    str(command_info), commands_file) )
                            if "dryrun" in handle_device_relocates_info and\
                                handle_device_relocates_info["dryrun"] is not None:
                                errors.append( ("'dryrun' value should be null in %s['handle_device_relocates'] in entry"
                                                " %d (%s) in file %s") % (command, index, str(command_info),
                                                                          commands_file) )

                    if "repair_catalog" in command_info[command]:
                        repair_catalog_info = command_info[command]["repair_catalog"]
                        if repair_catalog_info is not None and isinstance(repair_catalog_info, dict) == False:
                            errors.append( ("%s['repair_catalog'] (%s) not a dict in entry %d (%s) in file %s")
                                % (command, str(repair_catalog_info), index, str(command_info), commands_file) )
                        elif repair_catalog_info is not None:
                            repair_catalog_mandatory_keys = []
                            repair_catalog_optional_keys = ["dryrun"]
                            for repair_catalog_mandatory_key in repair_catalog_mandatory_keys:
                                if repair_catalog_mandatory_key not in repair_catalog_info:
                                    errors.append( ("Mandatory key %s not found in %s['repair_catalog'] in entry"
                                                    " %d (%s) in file %s") % (repair_catalog_mandatory_key,
                                                    command, index, str(command_info), commands_file) )
                            for repair_catalog_key in repair_catalog_info:
                                if repair_catalog_key not in repair_catalog_mandatory_keys and\
                                    repair_catalog_key not in repair_catalog_optional_keys:
                                    errors.append( ("Invalid entry %s (valid entries are %s,%s) found in "
                                                    "%s['repair_catalog'] in entry %d (%s) in file %s") %\
                                                   (repair_catalog_key,str(repair_catalog_mandatory_keys), 
                                                    str(repair_catalog_optional_keys), command, index,
                                                    str(command_info), commands_file) )
                            if "dryrun" in repair_catalog_info and\
                                repair_catalog_info["dryrun"] is not None:
                                errors.append( ("'dryrun' value should be null in %s['repair_catalog'] in entry"
                                                " %d (%s) in file %s") % (command, index, str(command_info),
                                                                          commands_file) )


                op = {command : {} }
                for key in command_info:
                    op[key] = command_info[key]


                final_commands_list.append(op)

    return (link, device, updated_config, final_commands_list, errors)

def validate_dir_access(path, required_access, required_access_description):
    errors = []
    if os.path.isdir(path) == False:
        errors.append(("Dir %s not found or is not a dir") % path)
    elif os.access(path, required_access) == False:
        errors.append(("You do not appear to have %s access to dir %s") % (required_access_description, path))
    return errors

def validate_file_access(path, required_access, required_access_description):
    errors = []
    if os.path.isfile(path) == False:
        errors.append(("File %s not found or is not a file") % path)
    elif os.access(path, required_access) == False:
        errors.append(("You do not appear to have %s access to file %s") % (required_access_description, path))
    return errors

def apply_overrides(config, overrides):
    non_overridable_sections = ["local_dirs", "file_category_for_file_extension"]
    errors = []
    only_defaults = config["only_defaults"]
    new_config = copy.deepcopy(config)
    # Apply overrides
    for section in overrides:
        if section in non_overridable_sections:
            errors.append( ("It is illegal to override section %s") % (section) )
        if section not in config:
            errors.append( ("section %s is not a valid config section") % (section) )
        value = overrides[section]
        if isinstance(value, dict) == False:
            errors.append( ("'overrides' section %s value %s is not a dict") %
                (section, str(value) ) )
        else:
            for option in overrides[section]:
                value = overrides[section][option]
                if option in only_defaults:
                    errors.append( ("Cannot override default value %s in 'overrides' section %s option %s") %
                        (str(value), section, option ) )
                    continue
                if isinstance(value, dict):
                    for nested_option in overrides[section][option]:
                        value = overrides[section][option][nested_option]
                        if isinstance(value, dict):
                            errors.append( ("'overrides' section %s option %s__%s value %s cannot be a dict") %
                                (section, option, nested_option, str(value) ) )
                        if option not in config[section]:
                            config[section][option] = {}
                            new_config[section][option] = {}
                        if nested_option not in config[section][option]:
                            if value is not None:
                                new_config[section][option][nested_option] = value
                        else:
                            if value is None:
                                del config[section][option][nested_option]
                                if config[section][option] == {}:
                                    del config[section][option]
                            else:
                                old_value = config[section][option][nested_option]
                                if is_text(value):
                                    if is_text(old_value) == False:
                                        errors.append( ("'overrides' section %s option %s__%s value %s is text but value being"
                                                        " replaced %s is not text") % (section, option, nested_option,
                                          str(value), str(old_value) ) )
                                    else:
                                        new_config[section][option][nested_option] = value
                                if isinstance(value, int) or isinstance(value, float):
                                    if isinstance(old_value, int) == False and isinstance(old_value, float) == False:
                                        errors.append( ("'overrides' section %s option %s__%s value %s is number but value being"
                                                        " replaced %s is not numeric") % (section, nested_option,
                                                                                          str(value), str(old_value) ) )
                                    else:
                                        new_config[section][option][nested_option] = value
                    continue
                if option not in config[section]:
                    if value is not None:
                        new_config[section][option] = value
                else:
                    if value is None:
                        del config[section][option]
                    else:
                        old_value = config[section][option]
                        if is_text(value):
                            if is_text(old_value) == False:
                                errors.append( ("'overrides' section %s option %s value %s is text but value being"
                                                " replaced %s is not text") % (section, option,
                                  str(value), str(old_value) ) )
                            else:
                                new_config[section][option] = value
                        if isinstance(value, int) or isinstance(value, float):
                            if isinstance(old_value, int) == False and isinstance(old_value, float) == False:
                                errors.append( ("'overrides' section %s option %s value %s is number but value being"
                                                " replaced %s is not numeric") % (section, option,
                                                                                  str(value), str(old_value) ) )
                            else:
                                new_config[section][option] = value

    errs = validate_config(new_config)

    errors.extend(errs)

    return (new_config, errors)

def validate_config(config):

    errors = []

    only_defaults = config["only_defaults"]

    write_log_line(logging.DEBUG, "ConfigsValidate", "Starting", "Configs=" + str(config) +
                   ", Defaults=" + str(only_defaults))
    mandatory_keys = ["file_category_for_file_extension", "local_dirs"]
    for mandatory_key in mandatory_keys:
        if mandatory_key not in config:
            errors.append("Mandatory section " + mandatory_key + " not found in ini file(s) " )

    (links, devices, ops, defaults_errors) = validate_defaults(config)
    if defaults_errors != []:
        errors.extend(defaults_errors)

    directories_errors = validate_directories(config)
    if directories_errors != []:
        errors.extend(directories_errors)

    file_category_for_file_extension_errors = validate_file_category_for_file_extension(config)
    if file_category_for_file_extension_errors != []:
        errors.extend(file_category_for_file_extension_errors)

    for key in config:
        if key == "only_defaults":
            continue
        if key in mandatory_keys:
            continue
        if (links != [] and key not in links) and\
            (devices != [] and key not in devices):
                errors.append("Section " + key + " not listed in devices or links in ini file(s) ")

    links_errors = validate_links(config, links)
    if links_errors != []:
        errors.extend(links_errors)

    devices_errors = validate_devices(config, links, devices, ops)
    if devices_errors != []:
        errors.extend(devices_errors)

    return errors

def validate_defaults(config):

    default_options = {
        "mandatory" : ["links", "devices", "ops", "global_max_parallels"],
        "optional" : [],
        "numerics_min_max" : {"global_max_parallels" :  (0, None)}
    }

    errors = []

    links = []
    devices = []
    ops = []

    only_defaults = config["only_defaults"]

    for mandatory_default_option in default_options["mandatory"]:
        if mandatory_default_option not in only_defaults:
            errors.append("Mandatory default option " + mandatory_default_option + " not found in ini file(s) ")
    for default_item in only_defaults:
        if default_item not in default_options["mandatory"] and\
            default_item not in default_options["optional"] and\
                default_item not in CONFIG_DEFAULTS:
            errors.append("Illegal option " + default_item + " under DEFAULT " +
                          " in ini file(s) " )
        if default_item in default_options["numerics_min_max"]:
            num_validate_errors = validate_numeric(only_defaults[default_item],
                                                   default_options["numerics_min_max"][default_item],
                                                   "Option " + default_item + " under DEFAULT",
                                                   "in ini file(s)")
            if num_validate_errors != []:
                errors.extend(num_validate_errors)
                continue
    if "links" in only_defaults: # i.e. not omitted due to error
        links = only_defaults["links"]
    if "devices" in only_defaults: # i.e. not omitted due to error
        devices = only_defaults["devices"]
    if "ops" in only_defaults: # i.e. not omitted due to error
        ops = only_defaults["ops"]

    return (links, devices, ops, errors)

def validate_directories(config):

    directories_options = {
        "mandatory" : [
            ("inbox_dir", os.W_OK, "write"),
            ("outbox_dir", os.W_OK, "write"),
            ("catalog_dir", os.W_OK, "write"),
            ("catalog_index_dir", os.W_OK, "write"),
            ("commands_dir", os.R_OK, "read"),
            ("responses_dir", os.W_OK, "write"),
            ("trash_list_dir", os.W_OK, "write")
                       ],
        "optional" : []
    }

    errors = []

    only_defaults = config["only_defaults"]

    key_name = "local_dirs"
    if key_name in config: # i.e. not omitted due to error
        options = config[key_name].keys()
        for (dir, _, _) in directories_options["mandatory"]:
            if dir not in options:
                errors.append("Mandatory local_dir " + dir + " not found in ini file(s) ")
        found = False
        for option in options:
            if option in only_defaults:
                continue
            for list_type in ["mandatory", "optional"]:
                for (dir, _, _) in directories_options[list_type]:
                    if option == dir:
                        found = True
                        break
                if found:
                    break
            if not found:
                errors.append("Illegal option " + option + " under directories " +
                              " in ini file(s) " )

        for list_type in ["mandatory", "optional"]:
            for (key, required_access, required_access_description) in directories_options[list_type]:
                path = config[key_name][key]
                errs = validate_dir_access(path, required_access, required_access_description)
                if errs != []:
                    errors.extend(errs)

    return errors

def validate_file_category_for_file_extension(config):
    errors = []

    only_defaults = config["only_defaults"]

    key_name = "file_category_for_file_extension"
    valid_file_categories = ["picture", "video", "music", "document"]
    if key_name in config: # i.e. not omitted due to error
        extensions = config[key_name].keys()
        for extension in extensions:
            if extension in only_defaults:
                continue
            file_category = config[key_name][extension]
            if file_category not in valid_file_categories:
                errors.append("Invalid file category '" + file_category + "' for extension '" + extension +
                "' (valid categories are " +
                              str(valid_file_categories) + " in ini file(s)")
    return errors

def validate_links(config, links):

    link_options = {
        "mandatory" : {
            "mtp_ubuntu" : ["file_system_base", "max_parallels"],
            "usb_ubuntu" : ["file_system_base", "max_parallels"],
            "android_sshelper" : ["mnt_pt", "max_parallels"],
            "local_fs" : ["file_system_base", "max_parallels"]
        },
        "optional" : {
            "mtp_ubuntu" : [],
            "usb_ubuntu" : [],
            "android_sshelper" : [],
            "local_fs" : []
        },
        "numerics_min_max" : {
            "mtp_ubuntu" : {"max_parallels" :  (0, None)},
            "usb_ubuntu" : {"max_parallels" :  (0, None)},
            "android_sshelper" : {"max_parallels" :  (0, None)},
            "local_fs" : {"max_parallels" :  (0, None)},
        }
    }

    errors = []

    only_defaults = config["only_defaults"]

    for link in links:
        if link not in config:
            errors.append("link " + link + " not listed in ini file(s) " )
        else:
            mandatory_options = link_options["mandatory"][link]
            optional_options = link_options["optional"][link]
            for mandatory_option in mandatory_options:
                if mandatory_option not in config[link]:
                    errors.append("Mandatory option " + mandatory_option +
                                  " not listed under link [" + link +
                                  "] in ini file(s) " )
            for option in config[link]:
                if option in only_defaults:
                    continue
                if option not in mandatory_options and option not in optional_options:
                    errors.append("Illegal option " + option + " under link " + link +
                    " in ini file(s) " )
                if link in link_options["numerics_min_max"] and option in link_options["numerics_min_max"][link]:
                    num_validate_errors = validate_numeric(config[link][option],
                                                           link_options["numerics_min_max"][link][option],
                                                           "Option " + option + " under link " + link,
                                                           "in ini file(s)")
                    if num_validate_errors != []:
                        errors.extend(num_validate_errors)
                        continue

    return errors

def validate_devices(config, links, devices, ops):

    # We assume the same set of options for all devices under a given link. If you have a device
    # which needs different options for a link then create a new link instead.

    device_options = {
         "mandatory" : {
             "device" : ["links", "ops", "max_parallels", "file_import_mode"],
             "mtp_ubuntu" : ["mnt_dir_device_path_pairs", "max_parallels"],
             "usb_ubuntu" : ["mnt_dir_device_path_pairs", "max_parallels"],
             "android_sshelper" : ["port", "user", "to_mount_pairs", "mnt_dir_device_path_pairs", "max_parallels"],
             "local_fs" : ["mnt_dir_device_path_pairs", "max_parallels"],
         },
        "optional" : {
            "device" : ["exclude_dirs", "exclude_files", "include_files"],
            "mtp_ubuntu" : [],
            "usb_ubuntu" : [],
            "android_sshelper" : ["ip", "bonjour_device_name"],
            "local_fs" : []
        },
        "numerics_min_max" : {
            "device" : {"max_parallels" :  (0, None)},
            "mtp_ubuntu" : {"max_parallels" :  (0, None)},
            "usb_ubuntu" : {"max_parallels" :  (0, None)},
            "android_sshelper" : {"max_parallels" :  (0, None)},
            "local_fs" : {"max_parallels" :  (0, None)},
        }
    }

    device_valid_option_values = {
        "device" : {"file_import_mode" : ["copy", "move", "none"]}
    }

    errors = []

    only_defaults = config["only_defaults"]

    for device in devices:

        if device not in config:
            errors.append("device " + device + " not listed in ini file(s) " )
        mandatory_link_independent_options = device_options["mandatory"]["device"]
        for mandatory_link_independent_option in mandatory_link_independent_options:
            if mandatory_link_independent_option not in config[device]["device"]:
                errors.append("Mandatory option " + "device" + "::" + mandatory_link_independent_option +
                              " not listed under device [" + device +
                              "] in ini file(s) " )
        if "ops" in config[device]["device"]: # Not skipped due to error
            device_ops = config[device]["device"]["ops"]
            for device_op in device_ops:
                if device_op not in ops:
                    errors.append("Op " + device_op +
                                  " listed under device [" + device +
                                  "] device__ops not defined in ini file(s) " )
        if "links" not in config[device]["device"]: # Skipped due to error
            continue
        device_links = config[device]["device"]["links"]
        for device_link in device_links:
            if device_link not in links:
                errors.append("Link " + device_link +
                              " listed under device default [" + device +
                              "] devicelinks not defined in ini file(s) " )

        for device_link in device_options["mandatory"]:
            if device_link not in device_links:
                continue
            for mandatory_device_option in device_options["mandatory"][device_link]:
                if device_link not in config[device] or mandatory_device_option not in config[device][device_link]:
                    errors.append("Mandatory device option " + device_link + "__" + mandatory_device_option +
                                  " not listed under device [" + device +
                                  "] in ini file(s) " )

        for option in config[device]:
            if option in only_defaults:
                continue
            if isinstance(config[device][option], dict)== False:
                errors.append("Invalid option " + option + " (all options must be "
                               "of the form linkname__optionname or device__optionname) "
                               "under device " + device + " in ini file(s) " )
            else:
                link = option
                if link != "device" and link not in device_links:
                    link_options_list = "("
                    for link_option in config[device][link]:
                        link_options_list += link + "__" + link_option + " "
                    link_options_list += ")"
                    errors.append("Link " + link + " used in options " + link_options_list +
                                  " not listed under devicelinks under device [" + device + "] in ini file(s) " )
                for link_option in config[device][link]:
                    valid = False
                    if link in device_options["mandatory"] and\
                                    link_option in device_options["mandatory"][link]:
                        valid = True
                    elif link in device_options["optional"] and\
                                    link_option in device_options["optional"][link]:
                        valid = True
                    if valid == False:
                        errors.append("Unrecognized option " + link_option + " (option must be a valid "
                                       "link-independent option or must be of the form link__option) "
                                       "under device " + device + " in ini file(s) " )
                        continue
                    if link_option in device_options["numerics_min_max"][link]:
                        num_validate_errors = validate_numeric(config[device][link][link_option],
                                                               device_options["numerics_min_max"][link][link_option],
                                                               "Option " + option + " under device " + device,
                                                               "in ini file(s)")
                        if num_validate_errors != []:
                            errors.extend(num_validate_errors)
                    if link in device_valid_option_values and link_option in device_valid_option_values[link]:
                        if config[device][link][link_option] not in device_valid_option_values[link][link_option]:
                            errors.append("Invalid value " + config[device][link][link_option] + " for " +\
                                          link + "__" + link_option + " (valid values are " +
                                          str(device_valid_option_values[link][link_option]) + ") "
                                           "under device " + device + " in ini file(s) " )

    return errors

def validate_numeric(value_text, numeric_min_max_entry, err_msg_prefix, err_msg_suffix):
    errors = []
    if value_text is None or value_text == "":
        return errors
    try:
        value = int(value_text)
        (min_value, max_value) = numeric_min_max_entry
        if min_value is not None and value < min_value:
            errors.append(err_msg_prefix + "; value " +
                          str(value) + " is less than minimum allowed (" + str(min_value) +
                          ") " + err_msg_suffix )
        if max_value is not None and value > max_value:
            errors.append(err_msg_prefix + "; value " +
                          str(value) + " exceeds maximum aloowed (" + str(max_value) +
                          ") " + err_msg_suffix )
    except ValueError:
        errors.append(err_msg_prefix + "; " + value_text + " is not numeric " + err_msg_suffix)

    return errors

def process_args():

    write_log_line(logging.DEBUG, "ArgsParser", "Starting", "Args=" + str(sys.argv[1]))
    if len(sys.argv) < 2:
        raise UsageError("Less than minimum number of args; received args " + str(sys.argv[1:]) )
    ini_link_names = sys.argv[1:]
    for ini_link_name in ini_link_names:
        if not os.path.isfile(ini_link_name):
            raise UsageError("ini file %s not found " % (ini_link_name) )
        elif os.access(ini_link_name, os.R_OK) == False:
            raise UsageError("You do not appear to have read permissions on ini file %s " % (ini_link_name) )
    (config, arg_was_json) = cfg_to_json(ini_link_names)
    errors = validate_config(config)
    if errors != []:
        raise UsageError("Usage errors: " + str(errors))
    setupLogging(config["local_dirs"]["responses_dir"])
    write_log_line(logging.INFO, "UNCLOUD", "STARTING")
    return (config, arg_was_json)

def cfg_to_json(cfg_file_names):

    ret = {}

    if len(cfg_file_names) == 1:
        try:
            with open(cfg_file_names[0]) as fd:
                ret = json.load(fd)
                replace_empty_str_with_none(ret)
                # Validate "only_defaults" section since that is inserted and
                # not validated by .ini parsing code
                errs = []
                if "only_defaults" not in ret:
                    errs.append("'only_defaults' section missing")
                elif isinstance(ret["only_defaults"], dict) == False:
                    errs.append("'only_defaults' section is not a dict")
                else:
                    for key in ret["only_defaults"]:
                        for section in ret:
                            if section == "only_defaults":
                                continue
                            if key not in ret[section]:
                                errs.append("'only_defaults[" + key + " not found under section " + section)
                            elif ret["only_defaults"][key] != ret[section][key]:
                                errs.append("only_defaults[" + key + "[ and " + section + "[" + key +
                                            "] contents do not match")
                if errs != []:
                    raise UsageError("Invalid JSON file " + cfg_file_names[0] + "( " + str(errs) + ")")

                return(ret, True)

        except Exception:
            pass

    # This dict contains only the defaults so they can be separately validated
    only_defaults = {}
    cfg = None
    if sys.version_info[0] == 3:
        cfg = ConfigParser.ConfigParser(defaults = CONFIG_DEFAULTS, allow_no_value=True)
    elif sys.version_info[0] == 2:
        cfg = ConfigParser.SafeConfigParser(defaults = CONFIG_DEFAULTS, allow_no_value=True)
    try:
        cfg.read(cfg_file_names)
    except ConfigParser.Error as err:
        raise RuntimeError("Config parse errors: " + str(err))

    for option in cfg["DEFAULT"]:
        value = cfg.get("DEFAULT", option)
        try:
            only_defaults[option] = int(value)
            continue
        except ValueError as err:
            pass
        words = value.split(",")
        if len(words) > 1:
            if words[-1] == "":
                only_defaults[option] = words[ : -1]
            else:
                only_defaults[option] = words
        elif len(words) == 0:
            only_defaults[option] = None
        else:
            only_defaults[option] = value

    for section in cfg.sections():
        ret[section] = {}
        for option in cfg.options(section):
            value = cfg.get(section, option)
            if could_be_link_option(option):
                (link, option) = link_option_to_link_and_option(option)
                if link not in ret[section]:
                    ret[section][link] = {}
                try:
                    ret[section][link][option] = int(value)
                    continue
                except ValueError:
                    pass
                words = value.split(",")
                if len(words) > 1:
                    if words[-1] == "":
                        ret[section][link][option] = words[ : -1]
                    else:
                        ret[section][link][option] = words
                elif len(words) == 0:
                    ret[section][link][option] = None
                else:
                    ret[section][link][option] = value
            else:
                try:
                    ret[section][option] = int(value)
                    continue
                except ValueError:
                    pass
                words = value.split(",")
                if len(words) > 1:
                    if words[-1] == "":
                        ret[section][option] = words[ : -1]
                    else:
                        ret[section][option] = words
                elif len(words) == 0:
                    ret[section][option] = None
                else:
                    ret[section][option] = value

    ret["only_defaults"] = only_defaults

    replace_empty_str_with_none(ret)

    return (ret, False)

def replace_empty_str_with_none(obj):
    for key in obj:
        if isinstance(obj[key], dict):
            replace_empty_str_with_none(obj[key])
        else:
            if obj[key] == "":
                obj[key] = None

def setupLogging(dir):
    global TIMESTAMP
    log_path = os.path.join(dir, "UNCLOUD-" + TIMESTAMP + ".log")
    file_handler = logging.FileHandler(log_path)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter("%(name)s--%(levelname)s--%(message)s"))
    logging.getLogger().addHandler(file_handler)
    logging.getLogger().setLevel(logging.DEBUG)

def write_log_line(level, block, op, data = None):
    logging.log(level, ("Thread=" + str(threading.current_thread().ident) + "\t" +
                  str(block) + "\t" + str(op) + "\t" + str(data)))

def main():

    global TIMESTAMP

    try:
        (config, arg_was_json) = process_args()
        if arg_was_json is False:
            json_name = "UNCLOUD-" + TIMESTAMP + ".json"
            json_path = os.path.join(config["local_dirs"]["responses_dir"], json_name)
            json_dict = copy.deepcopy(config)
            with open(json_path, "w") as fd:
                json.dump(json_dict, fd, indent=4)
        commands_dir = config["local_dirs"]["commands_dir"]
        for commands_file_name in os.listdir(commands_dir):
            commands_file_path = os.path.join(commands_dir, commands_file_name)
            if os.path.isfile(commands_file_path) is False:
                continue
            (name, ext) = os.path.splitext(commands_file_path)
            (_, filename) = os.path.split(name)
            response_file_name = filename + "-reponse" + ext
            responses_file_path = os.path.join(config["local_dirs"]["responses_dir"], response_file_name)
            responses = {"responses" : []}
            try:
                (link, device, updated_config, final_commands_list, errors) =\
                    parse_commands_json(config, commands_file_path)
                if errors != []:
                    responses["responses"].append({"response" : {}, "errors" : errors})
                    with open(responses_file_path, "w") as fd:
                        json.dump(responses, fd)
                else:
                    process_command(responses_file_path, link, device, config, updated_config, final_commands_list)
            except Exception as err:
                for index in range(len(inspect.trace())):
                    frame = inspect.trace()[index]
                    print(logging.ERROR, "UNCLOUD", "Error:", str(err) + "; STACK " +
                                   str(index) + "::" + frame[1] + "::" + str(frame[2]) + "::" + frame[3])
        write_log_line(logging.INFO, "UNCLOUD", "Done")

    except UsageError as err:
        print("UsageError" + err.msg)
        Usage()
        sys.exit(1)
    except RuntimeError as err:
        print("RuntimeError: " + str(err))
        print(err.msg)
        for index in range(len(inspect.trace())):
            frame = inspect.trace()[index]
            write_log_line(logging.ERROR, "UNCLOUD", "RuntimeError", err.msg + "; STACK " +
                           str(index) + "::" + frame[1] + "::" + str(frame[2]) + "::" + frame[3])
        sys.exit(1)
    except Exception as err:
        print("Exception: " + str(err))
        for index in range(len(inspect.trace())):
            frame = inspect.trace()[index]
            print("STACK " + str(index) + "::" + frame[1] + "::" + str(frame[2]) + "::" + frame[3])
            write_log_line(logging.ERROR, "UNCLOUD", "Exception", str(err) + "; STACK " +
                           str(index) + "::" + frame[1] + "::" + str(frame[2]) + "::" + frame[3])
        sys.exit(1)

if __name__ == "__main__":
    main()
