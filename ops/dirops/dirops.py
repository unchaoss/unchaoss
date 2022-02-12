__author__ = 'chitrabhanu'

import os, stat
import sys
import datetime
import hashlib
import time
from filecmp import dircmp
import json
if sys.version_info[0] < 3:
    import Queue
else:
    import queue as Queue

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
    for valid_args in valid_args_list:
        args_string = ""
        for arg_desc in valid_args[1]:
            args_string += " " + arg_desc
        print("\t\t" + valid_args[0] + args_string)

def get_dir_list(args):
    dir_name = args[0]
    out_file_name = args[1]

    try:

        validate_file_or_dir(dir_name, is_file=False, is_write=False)
        rename_msg = rename_file_on_overwrite(out_file_name)
        if rename_msg is not None:
            print(rename_msg)
        validate_file_or_dir(out_file_name, is_file=True, is_write=True)

        out_file = open(out_file_name, "w")

    except IOError as err:
        raise UsageError(err)

    dir_name_len = len(dir_name)
    if dir_name.endswith("/") is False and dir_name.endswith("\\") is False:
        dir_name_len += 1
    for root, dirs, files in os.walk(dir_name):
        for file_name in files:
            file_path = ""
            try:
                out_line = ""
                file_path = os.path.join(root, file_name)
                out_line += file_path
                out_line = add_file_stats(out_line, file_path)
                out_file.write(out_line+"\n")
            except IOError as err:
                out_file.write(RUNTIME_ERROR_PREFIX + "(non-fatal) " +
                               str(err) + " (file = " + file_path + ")\n")
                continue
    out_file.close()

def match_dir_copies(args):
    dir_list_file_golden_name = args[0]
    dir_list_file_test_name = args[1]
    golden_errors_file_name = args[2]
    test_errors_file_name = args[3]
    golden_only_file_name = args[4]
    test_only_file_name = args[5]
    size_or_cksm_mismatches_file_name = args[6]
    name_matches_file_name = args[7]

    try:

        validate_file_or_dir(dir_list_file_golden_name, is_file=True,
                             is_write=False)
        dir_list_file_golden = open(dir_list_file_golden_name)

        validate_file_or_dir(dir_list_file_test_name, is_file=True,
                             is_write=False)
        dir_list_file_test = open(dir_list_file_test_name)

        rename_msg = rename_file_on_overwrite(golden_errors_file_name)
        if rename_msg is not None:
            print(rename_msg)
        validate_file_or_dir(golden_errors_file_name, is_file=True,
                             is_write=True)
        golden_errors_file = open(golden_errors_file_name, "w")

        rename_msg = rename_file_on_overwrite(test_errors_file_name)
        if rename_msg is not None:
            print(rename_msg)
        validate_file_or_dir(test_errors_file_name, is_file=True, is_write=True)
        test_errors_file = open(test_errors_file_name, "w")

        rename_msg = rename_file_on_overwrite(golden_only_file_name)
        if rename_msg is not None:
            print(rename_msg)
        validate_file_or_dir(golden_only_file_name, is_file=True, is_write=True)
        golden_only_file = open(golden_only_file_name, "w")

        rename_msg = rename_file_on_overwrite(test_only_file_name)
        if rename_msg is not None:
            print(rename_msg)
        validate_file_or_dir(test_only_file_name, is_file=True, is_write=True)
        test_only_file = open(test_only_file_name, "w")

        rename_msg = rename_file_on_overwrite(size_or_cksm_mismatches_file_name)
        if rename_msg is not None:
            print(rename_msg)
        validate_file_or_dir(size_or_cksm_mismatches_file_name, is_file=True,
                             is_write=True)
        size_or_cksm_mismatches_file = open(size_or_cksm_mismatches_file_name, "w")

        rename_msg = rename_file_on_overwrite(name_matches_file_name)
        if rename_msg is not None:
            print(rename_msg)
        validate_file_or_dir(name_matches_file_name, is_file=True, is_write=True)
        name_matches_file = open(name_matches_file_name, "w")

    except IOError as err:
        raise UsageError(str(err))

    golden_file_info = {}
    test_file_info = {}

    try:
        update_file_info(dir_list_file_golden, golden_file_info, golden_errors_file)
        golden_errors_file.close()
        update_file_info(dir_list_file_test, test_file_info, test_errors_file)
        test_errors_file.close()

    except IOError as err:
        raise RuntimeError(str(err))

    name_matches_count = 0
    golden_only_count = 0
    golden_count = 0
    golden_total = len(golden_file_info)
    for golden_dir_entry in golden_file_info:
        golden_count += 1
        if (golden_count % 10000 ) == 0:
            print("Processed ", golden_count, "out of", golden_total,\
                "name_matches_count", name_matches_count,\
                "golden_only_count", golden_only_count)
        if golden_dir_entry not in test_file_info.keys():
            golden_only_count += 1
            golden_only_file.write(str(golden_dir_entry) + "\n")
        else:
            name_matches_count += 1
            name_matches_file.write(str(golden_dir_entry) + "\n")
            (golden_size, _, _, golden_cksm) = golden_file_info[golden_dir_entry]
            (test_size, _, _, test_cksm) = test_file_info[golden_dir_entry]
            if golden_size != test_size or golden_cksm != test_cksm:
                size_or_cksm_mismatches_file.write("GOLDEN: " + str(golden_dir_entry) +
                                           str(golden_file_info[
                                                   golden_dir_entry]) + "\n")
                size_or_cksm_mismatches_file.write("TEST: " + str(golden_dir_entry) +
                                           str(test_file_info[
                                                   golden_dir_entry]) + "\n")
    golden_only_file.close()
    name_matches_file.close()
    size_or_cksm_mismatches_file.close()

    for test_dir_entry in test_file_info:
        if test_dir_entry not in golden_file_info.keys():
            test_only_file.write(str(test_dir_entry) + "\n")
    test_only_file.close()

def update_file_times(args):
    dir_name = args[0]
    dir_list_file_golden_name = args[1]
    dir_list_file_test_name = args[2]
    log_file_name = args[3]

    try:

        validate_file_or_dir(dir_name, is_file=False, is_write=False)
        validate_file_or_dir(dir_list_file_golden_name, is_file=True,
                             is_write=False)
        dir_list_file_golden = open(dir_list_file_golden_name)

        validate_file_or_dir(dir_list_file_test_name, is_file=True,
                             is_write=False)
        dir_list_file_test = open(dir_list_file_test_name)

        rename_msg = rename_file_on_overwrite(log_file_name)
        if rename_msg is not None:
            print(rename_msg)
        validate_file_or_dir(log_file_name, is_file=True, is_write=True)
        log_file = open(log_file_name, "w")

    except IOError as err:
        raise UsageError(str(err))

    golden_file_info = {}
    test_file_info = {}

    try:
        update_file_info(dir_list_file_golden, golden_file_info, log_file)
        update_file_info(dir_list_file_test, test_file_info, log_file)
        dir_list_file_golden.close()
        dir_list_file_test.close()

    except IOError as err:
        raise RuntimeError(str(err))
    
    for test_dir_entry in test_file_info:
        if "  " not in test_dir_entry:
            continue
        if test_dir_entry in golden_file_info.keys():
            (golden_size, golden_atime, golden_mtime, golden_cksm) =\
                golden_file_info[test_dir_entry]
            (test_size, test_atime, test_mtime, test_cksm) =\
                test_file_info[test_dir_entry]
            if golden_atime != test_atime or golden_mtime != test_mtime:
                file_path = os.path.join(dir_name, test_dir_entry)
                if golden_atime != test_atime:
                    log_file.write(file_path + " Replacing Atime " +
                                   time.ctime(test_atime) + " by " +
                                   time.ctime(golden_atime) + " ")
                if golden_mtime != test_mtime:
                    log_file.write(file_path + " Replacing Mtime " +
                                   time.ctime(test_mtime) + " by " +
                                   time.ctime(golden_mtime) + " ")
                if not os.path.exists(file_path):
                    log_file.write(" ERROR (file not found)\n")
                else:
                    log_file.write("\n")
                    os.utime(file_path, (golden_atime, golden_mtime))
    log_file.close()

def compare_dirs_match_names(args):
    dir1 = args[0]
    dir2 = args[1]
    output_file = args[2]

    try:

        validate_file_or_dir(dir1, is_file=False, is_write=False)
        validate_file_or_dir(dir2, is_file=False, is_write=False)

        rename_msg = rename_file_on_overwrite(output_file)
        if rename_msg is not None:
            print(rename_msg)
        validate_file_or_dir(output_file, is_file=True, is_write=True)
        output_file = open(output_file, "w")

    except IOError as err:
        raise UsageError(str(err))

    try:
        path1 = os.path.realpath(dir1)
        path2 = os.path.realpath(dir2)
        dcmp = dircmp(path1, path2)
        list_diff_files(dcmp, output_file)

    except IOError as err:
        raise RuntimeError(str(err))

    output_file.close()

def list_dups(args):
    dir_list_file_names = args[0:-2]
    dup_non_tree_files_list_file_name = args[-2]
    dup_trees_list_file_name = args[-1]

    try:

        for dir_list_file_name in dir_list_file_names:
            validate_file_or_dir(dir_list_file_name, is_file=True, is_write=False)
        rename_msg = rename_file_on_overwrite(dup_non_tree_files_list_file_name)
        if rename_msg is not None:
            print(rename_msg)
        validate_file_or_dir(dup_non_tree_files_list_file_name, is_file=True, is_write=True)
        rename_msg = rename_file_on_overwrite(dup_trees_list_file_name)
        if rename_msg is not None:
            print(rename_msg)
        validate_file_or_dir(dup_trees_list_file_name, is_file=True, is_write=True)
        dup_non_tree_files_list_file = open(dup_non_tree_files_list_file_name, "w")
        dup_trees_list_file = open(dup_trees_list_file_name, "w")

    except IOError as err:
        raise UsageError(str(err))

    # Key is dir path (ending in /). Value is map with fields:
    #   Key: md5_of_md5s. Value: md5-of-md5-s
    #           (ie md5 of string formed by sorting+concatenating md5-s of child files and md5-of-md5-s of child dirs.
    #           This value is None until all child md5-s and md5--of-md5-s gets determined
    #   Key: unresolved_sub_dirs_count : Value: The number of child dirs for which md5-of-md5s not yet determined
    #   Key: children. Value: list of names of children. Directory names end in /.
    #   Key: parent. Value: Path name (ends in /) of parent dir. None for root dir for this scan.
    dir_dup_calc_info = {}

    # Key is file path. Value is md5 checksum for that file path.
    md5_cksm_for_file_path = {}

    # Key is file path. Value is total bytes of that file path.
    total_bytes_by_file_path = {}

    # Key is md5_of_md5s matching more than one dir.Value is list of roots of fully cloned trees where the roots
    # have that md5_of_md5s.
    cloned_tree_roots_by_md5_of_md5s = {}

    # Key is total bytes. Value is list of md5_of_md5s of cloned trees whose roots have that md5_of_md5s.
    cloned_tree_md5_of_md5s_by_total_bytes = {}

    # Key is md5 matching more than one file path provided at least one file path is not in a dir with a clones.
    # File paths in the list that have clones in cloned trees are identified by prefixing the paths by the
    # expression "<tree-root-name>::" where tree-root-name is the root of the cloned tree containing the file_path.
    cloned_file_paths_with_prefixes_by_md5 = {}

    # Key is total bytes. Value is list of md5s with each md5 being that of a set of clone file paths all of which
    # having that many total bytes.
    cloned_file_paths_with_prefix_md5s_by_total_bytes = {}

    try:
        for dir_list_file_name in dir_list_file_names:
            dir_list_file = open(dir_list_file_name)
            print("Reading ", dir_list_file_name)
            read_files_record_md5s_and_total_bytes(dir_list_file, md5_cksm_for_file_path, total_bytes_by_file_path,
                                   dir_dup_calc_info, cloned_file_paths_with_prefixes_by_md5, dup_trees_list_file)
            dir_list_file.close()

        calculate_md5s_of_md5s(dir_dup_calc_info, md5_cksm_for_file_path, total_bytes_by_file_path,
                               cloned_tree_roots_by_md5_of_md5s)

        determine_clones(dir_dup_calc_info, total_bytes_by_file_path, cloned_tree_roots_by_md5_of_md5s,
                         cloned_file_paths_with_prefixes_by_md5, cloned_file_paths_with_prefix_md5s_by_total_bytes,
                         cloned_tree_md5_of_md5s_by_total_bytes)

        print("Printing duplicate-trees-file")
        total_bytes_list = cloned_tree_md5_of_md5s_by_total_bytes.keys()
        total_bytes_list.sort(reverse = True)
        for total_bytes in total_bytes_list:
            for md5_of_md5s in cloned_tree_md5_of_md5s_by_total_bytes[total_bytes]:
                out_data = md5_of_md5s + "\t" + str(total_bytes)
                cloned_tree_roots_by_md5_of_md5s[md5_of_md5s].sort()
                for cloned_tree_root in cloned_tree_roots_by_md5_of_md5s[md5_of_md5s]:
                    out_data += ("\t" + cloned_tree_root)
                dup_trees_list_file.write(out_data + "\n")
                break
    
        print("Printing duplicate-non-tree-files-file")
        total_bytes_list = cloned_file_paths_with_prefix_md5s_by_total_bytes.keys()
        total_bytes_list.sort(reverse = True)
        for total_bytes in total_bytes_list:
            for md5 in cloned_file_paths_with_prefix_md5s_by_total_bytes[total_bytes]:
                out_data = md5 + "\t" + str(total_bytes)
                cloned_file_paths_with_prefixes_by_md5[md5].sort()
                for cloned_file_path in cloned_file_paths_with_prefixes_by_md5[md5]:
                    out_data += ("\t" + cloned_file_path)
                dup_non_tree_files_list_file.write(out_data + "\n")

    except IOError as err:
        raise RuntimeError(str(err))

def read_files_record_md5s_and_total_bytes(dir_file, md5_cksm_for_file_path, total_bytes_by_file_path,
                                           dir_dup_calc_info, cloned_file_paths_with_prefixes_by_md5, err_file):
    line_number = 1
    for line in dir_file:
        (file_path, total_bytes, _, _, md5_checksum) = read_dir_file_line(line, err_file, line_number)
        if file_path is None:
            return
        md5_cksm_for_file_path[file_path] = md5_checksum
        total_bytes_by_file_path[file_path] = total_bytes
        if md5_checksum not in cloned_file_paths_with_prefixes_by_md5:
            cloned_file_paths_with_prefixes_by_md5[md5_checksum] = []
        cloned_file_paths_with_prefixes_by_md5[md5_checksum].append(file_path)
        (dir_path, _) = os.path.split(file_path)
        child = file_path
        dir_path += "/"
        successively_longer_paths = get_successively_longer_paths(dir_path)
        if dir_path in dir_dup_calc_info:
            dir_dup_calc_info[dir_path]["children"].append(child)
        else:
            child_is_a_file = True
            for index in range(len(successively_longer_paths)):
                (path, parent) = successively_longer_paths[len(successively_longer_paths) - index -1]
                if path not in dir_dup_calc_info:
                    create_new_dup_calc_info(path, dir_dup_calc_info)
                    dir_dup_calc_info[path]["children"].append(child)
                else:
                    dir_dup_calc_info[path]["children"].append(child)
                    if child_is_a_file == False:
                        dir_dup_calc_info[path]["unresolved_sub_dirs_count"] += 1
                    # We have an already-processed dir, its info has already been set so break this loop
                    break
                if child_is_a_file == False:
                    dir_dup_calc_info[path]["unresolved_sub_dirs_count"] += 1
                dir_dup_calc_info[path]["parent"] = parent
                child = path
                child_is_a_file = False
        line_number += 1

def calculate_md5s_of_md5s(dir_dup_calc_info, md5_cksm_for_file_path, total_bytes_by_file_path,
                           cloned_tree_roots_by_md5_of_md5s):
    remaining_unresolved_dir_paths = {}
    resolved_dir_paths_queue = Queue.Queue()
    for dir_path in dir_dup_calc_info:
        if dir_dup_calc_info[dir_path]["unresolved_sub_dirs_count"]:
            remaining_unresolved_dir_paths[dir_path]= 0
        else:
            resolved_dir_paths_queue.put(dir_path)
    # Loop needs to repeat while  'remaining_unresolved_dir_paths' remains non-empty. We cannot directly
    # test for the dict being empty inside the while expression because the dict gets modified inside the loop
    while True:
        if remaining_unresolved_dir_paths == {}:
            break
        dir_path = resolved_dir_paths_queue.get()
        update_md5_of_md5s_and_total_bytes(dir_path, dir_dup_calc_info, md5_cksm_for_file_path,
                                           total_bytes_by_file_path, cloned_tree_roots_by_md5_of_md5s)
        parent = dir_dup_calc_info[dir_path]["parent"]
        dir_dup_calc_info[parent]["unresolved_sub_dirs_count"] -= 1
        if dir_dup_calc_info[parent]["unresolved_sub_dirs_count"] == 0:
            del remaining_unresolved_dir_paths[parent]
            resolved_dir_paths_queue.put(parent)
    while resolved_dir_paths_queue.qsize():
        dir_path = resolved_dir_paths_queue.get()
        update_md5_of_md5s_and_total_bytes(dir_path, dir_dup_calc_info, md5_cksm_for_file_path,
                                           total_bytes_by_file_path, cloned_tree_roots_by_md5_of_md5s)
        assert dir_dup_calc_info[dir_path]["parent"] is None

def get_successively_longer_paths(dir_path):
    assert(dir_path.endswith("/"))
    successively_longer_paths = []
    current_path = ""
    parent = None
    while("/" in dir_path):
        index = dir_path.find("/")
        name = dir_path[:index+1]
        current_path += name
        successively_longer_paths.append((current_path, parent))
        dir_path = dir_path[index+1:]
        parent = current_path
    return successively_longer_paths

def create_new_dup_calc_info(dir_path, dir_dup_calc_info):
    dir_dup_calc_info[dir_path] = {"md5_of_md5s" : None, "unresolved_sub_dirs_count" : 0,
                                   "children" : [], "parent" : None, "total_bytes" : None}

def update_md5_of_md5s_and_total_bytes(dir_path, dir_dup_calc_info, md5_cksm_for_file_path,
                                       total_bytes_by_file_path, cloned_tree_roots_by_md5_of_md5s):
    list_of_md5s = []
    total_bytes = 0
    for child in dir_dup_calc_info[dir_path]["children"]:
        if child.endswith("/"):
            list_of_md5s.append(dir_dup_calc_info[child]["md5_of_md5s"])
            total_bytes += dir_dup_calc_info[child]["total_bytes"]
        else:
            list_of_md5s.append(md5_cksm_for_file_path[child])
            total_bytes += total_bytes_by_file_path[child]
    list_of_md5s.sort()
    hasher = hashlib.sha256()
    for md5 in list_of_md5s:
        hasher.update(md5)
    md5_of_md5s = hasher.hexdigest()
    dir_dup_calc_info[dir_path]["md5_of_md5s"] = md5_of_md5s
    dir_dup_calc_info[dir_path]["total_bytes"] = total_bytes
    # To start with, all dirs are added to 'cloned_tree_roots_by_md5_of_md5s' and non tree roots are removed later
    if md5_of_md5s not in cloned_tree_roots_by_md5_of_md5s:
        cloned_tree_roots_by_md5_of_md5s[md5_of_md5s]= []
    cloned_tree_roots_by_md5_of_md5s[md5_of_md5s].append(dir_path)

def determine_clones(dir_dup_calc_info, total_bytes_by_file_path, cloned_tree_roots_by_md5_of_md5s,
                     cloned_file_paths_with_prefixes_by_md5, cloned_file_paths_with_prefix_md5s_by_total_bytes,
                     cloned_tree_md5_of_md5s_by_total_bytes):
    
    # Remove all md5-s with only a single file path followed by all md5-of-md5s with only a single dir_path
    # The deletes cannot be done while the dir is being stepped through but are done later
    uncloned_names = []
    for md5 in cloned_file_paths_with_prefixes_by_md5:
        if len(cloned_file_paths_with_prefixes_by_md5[md5]) == 1:
            uncloned_names.append(md5)
    for md5 in uncloned_names:
        del cloned_file_paths_with_prefixes_by_md5[md5]
    uncloned_names = []
    for md5_of_md5s in cloned_tree_roots_by_md5_of_md5s:
        if len(cloned_tree_roots_by_md5_of_md5s[md5_of_md5s]) == 1:
            uncloned_names.append(md5_of_md5s)
    for md5_of_md5s in uncloned_names:
        del cloned_tree_roots_by_md5_of_md5s[md5_of_md5s]

    # Identify cloned dir sets whose parents are also clones
    parents_are_clones = {}
    for md5_of_md5s in cloned_tree_roots_by_md5_of_md5s:
        parents_are_clones[md5_of_md5s] = True
        parent_md5_of_md5 = None
        parents = []
        for dir_path in cloned_tree_roots_by_md5_of_md5s[md5_of_md5s]:
            parent = dir_dup_calc_info[dir_path]["parent"]
            if parent == None or parent in parents: # Latter condition means common parents
                parents_are_clones[md5_of_md5s] = False
                break
            parents.append(parent)
            if parent_md5_of_md5 == None:
                parent_md5_of_md5 = dir_dup_calc_info[parent]["md5_of_md5s"]
                continue
            elif parent_md5_of_md5 != dir_dup_calc_info[parent]["md5_of_md5s"]:
                parents_are_clones[md5_of_md5s] = False
                break
                
    # Set prefixes on cloned file paths that also belong to cloned dirs
    for md5 in cloned_file_paths_with_prefixes_by_md5:
        for index in range(len(cloned_file_paths_with_prefixes_by_md5[md5])):
            (dir_path, _) = os.path.split(cloned_file_paths_with_prefixes_by_md5[md5][index])
            dir_path += "/"
            md5_of_md5s = dir_dup_calc_info[dir_path]["md5_of_md5s"]
            if md5_of_md5s not in cloned_tree_roots_by_md5_of_md5s:
                continue
            while parents_are_clones[md5_of_md5s] == True:
                parent = dir_dup_calc_info[dir_path]["parent"]
                if parent == None:
                    break
                dir_path = parent
                md5_of_md5s = dir_dup_calc_info[parent]["md5_of_md5s"]
            cloned_file_paths_with_prefixes_by_md5[md5][index] =\
                dir_path + "::" + cloned_file_paths_with_prefixes_by_md5[md5][index]

    # Removed cloned file paths all of whose entries are in cloned trees
    md5s_to_remove = []
    for md5 in cloned_file_paths_with_prefixes_by_md5:
        flag = True
        for index in range(len(cloned_file_paths_with_prefixes_by_md5[md5])):
            if "::" not in cloned_file_paths_with_prefixes_by_md5[md5][index]:
                flag = False
                break
        if flag:
            md5s_to_remove.append(md5)
    for md5_to_remove in md5s_to_remove:
        del cloned_file_paths_with_prefixes_by_md5[md5_to_remove]

    # Finally removed all non tree root entries in cloned_tree_roots_by_md5_of_md5s
    md5_of_md5s_to_remove = []
    for md5_of_md5s in parents_are_clones:
        if parents_are_clones[md5_of_md5s]:
            md5_of_md5s_to_remove.append(md5_of_md5s)
    for md5_of_md5s in md5_of_md5s_to_remove:
        del cloned_tree_roots_by_md5_of_md5s[md5_of_md5s]

    # Set up tree total bytes
    for md5_of_md5s in cloned_tree_roots_by_md5_of_md5s:
        total_bytes = None
        for dir_path in cloned_tree_roots_by_md5_of_md5s[md5_of_md5s]:
            if total_bytes == None:
                total_bytes = dir_dup_calc_info[dir_path]["total_bytes"]
                break
        if total_bytes not in cloned_tree_md5_of_md5s_by_total_bytes:
            cloned_tree_md5_of_md5s_by_total_bytes[total_bytes] = []
        cloned_tree_md5_of_md5s_by_total_bytes[total_bytes].append(md5_of_md5s)

    # Set up file total bytes
    for md5 in cloned_file_paths_with_prefixes_by_md5:
        file_path_with_prefix = cloned_file_paths_with_prefixes_by_md5[md5][0]
        if "::" in file_path_with_prefix:
            file_path = file_path_with_prefix[file_path_with_prefix.find("::") +  2 : ]
        else:
            file_path = file_path_with_prefix
        total_bytes = total_bytes_by_file_path[file_path]
        if total_bytes not in cloned_file_paths_with_prefix_md5s_by_total_bytes:
            cloned_file_paths_with_prefix_md5s_by_total_bytes[total_bytes] = []
        cloned_file_paths_with_prefix_md5s_by_total_bytes[total_bytes].append(md5)

def verify_files_integrity(args):
    dir_list_pairs = args[0:-3]
    dup_non_tree_files_list_file_name = args[-3]
    dup_trees_list_file_name = args[-2]
    log_file_name = args[-1]

    if len(dir_list_pairs) % 2:
        err = "First set of names is not a set of (dir + file) pairs, has odd number of entries"
        raise UsageError(err)

    # [ (dir-to-scan, dir-list-file-name), (dir-to-scan, dir-list-file-name). (..., ...) ]
    dir_list_info = []

    for index in range(len(dir_list_pairs)):
        if index % 2:
            dir_list_info.append((dir_list_pairs[index-1], dir_list_pairs[index]))

    try:

        for (_, dir_list_file_name) in dir_list_info:
            validate_file_or_dir(dir_list_file_name, is_file=True,
                                 is_write=False)

        validate_file_or_dir(dup_non_tree_files_list_file_name, is_file=True, is_write=False)
        validate_file_or_dir(dup_trees_list_file_name, is_file=True, is_write=False)
        dup_non_tree_files_list_file = open(dup_non_tree_files_list_file_name, "r")
        dup_trees_list_file = open(dup_trees_list_file_name, "r")
        rename_msg = rename_file_on_overwrite(log_file_name)
        if rename_msg is not None:
            print(rename_msg)
        validate_file_or_dir(log_file_name, is_file=True, is_write=True)
        log_file = open(log_file_name, "w")

    except IOError as err:
        raise UsageError(str(err))

    # Key is file path, value is (size, atime, mtime, md5_checksum)
    file_info = {}

    # Key is dir path, value is [ [child-files], [child-dirs], md5-of-md5s, total-bytes ]
    # (md5-of-md5s is md5 of string formed by sorting+concatenating md5-s of child files and md5-of-md5-s of child dirs.
    dir_info = {}
    # Key is dir path of empty dir or a dir whose only children are empty dirs, value is ""
    empty_dirs = {}

    try:
        for (scanned_dir, dir_list_file_name) in dir_list_info:
            with open(dir_list_file_name) as dir_list_file:
                print("Reading ", dir_list_file_name)
                update_file_info(dir_list_file, file_info, log_file)
            with open(dir_list_file_name) as dir_list_file:
                print("Verifying filenames base ", dir_list_file_name)
                line_number = 1
                for line in dir_list_file:
                    if line.startswith(scanned_dir) == False:
                        log_file.write(RUNTIME_ERROR_PREFIX + " Line " + str(line_number) + "(" + line + ")" +\
                                       " does not start with " +\
                                       scanned_dir + " in file: " + dir_list_file_name + ")\n")
                    line_number += 1

        print("Verifying file list")
        for file_path in file_info:
            (size, _, _, md5_checksum) = file_info[file_path]
            if os.path.isfile(file_path) == False:
                log_file.write(RUNTIME_ERROR_PREFIX + " (file: " + file_path + " not found)\n")
                continue
            stat_info = os.stat(file_path)
            if stat_info[stat.ST_SIZE] != size:
                log_file.write(RUNTIME_ERROR_PREFIX + " (Recorded size " + str(size) + " actual size " +\
                               str(stat_info[stat.ST_SIZE]) + " for file: " + file_path + ")\n")
#            actual_md5_checksum = str(get_file_md5(file_path))
#            if actual_md5_checksum != md5_checksum:
#                log_file.write(RUNTIME_ERROR_PREFIX + " (Recorded md5 " + str(md5_checksum) + " actual md5 " +\
#                               str(actual_md5_checksum) + " for file: " + file_path + ")\n")

        print("Recalculating md5-of-md5-s for verification ")
        errors = False
        for (scanned_dir, _) in dir_list_info:
            for root, dirs, files in os.walk(scanned_dir, topdown = False):
                parent = root + "/"
                # Handle empty dirs
                if files == []:
                    if dirs == []:
                        empty_dirs[parent] = ""
                        continue
                    all_empty = True
                    for dir in dirs:
                        dir_path = os.path.join(root, dir) + "/"
                        if dir_path not in empty_dirs:
                            all_empty = False
                            break
                    if all_empty:
                        empty_dirs[parent] = ""
                        continue
                assert root not in dir_info
                dir_info[parent] = [files, dirs, None, None]
                unrecorded_files_or_dirs = update_parent_info(parent, dirs, files, file_info,
                                                                  dir_info, empty_dirs, log_file)
                if unrecorded_files_or_dirs:
                    errors = True
        if errors:
            print("Errors, aborting")
            return

        print("Verifying dup trees list")
        dirs_seen_so_far = verify_dup_dirs_integrity(dup_trees_list_file, dup_trees_list_file_name, dir_info, log_file)
        print("Verifying dup files list")
        verify_dup_files_integrity(dup_non_tree_files_list_file, dup_non_tree_files_list_file_name, file_info, dirs_seen_so_far, log_file)

    except IOError as err:
        raise RuntimeError(str(err))

def update_file_info(dir_file, file_info, err_file):
    line_number = 1
    for line in dir_file:
        (file_path, size, atime, mtime, md5_checksum) = read_dir_file_line(line, err_file, line_number)
        if file_path is None:
            return
        file_info[file_path] = (size, atime, mtime, md5_checksum)
        line_number += 1
        
def update_parent_info(parent, dirs, files, file_info, dir_info, empty_dirs, log_file):
    md5s_or_md5_of_md5s = []
    total_bytes = 0
    unrecorded_files = False
    unrecorded_dirs = False
    for file in files:
        file_path = os.path.join(parent, file)
        if file_path not in file_info:
            log_file.write(RUNTIME_ERROR_PREFIX + " Unrecorded file " + file_path + "\n")
            unrecorded_files = True
            continue
        (bytes, _, _, md5_checksum) = file_info[file_path]
        md5s_or_md5_of_md5s.append(md5_checksum)
        total_bytes += bytes
    for dir in dirs:
        dir_path = os.path.join(parent, dir) + "/"
        if dir_path in empty_dirs:
            continue
        if dir_path not in dir_info:
            log_file.write(RUNTIME_ERROR_PREFIX + " Unrecorded directory " + dir_path + "\n")
            unrecorded_files = True
            continue
        else:
            [ _, _, md5_of_md5s, bytes ] = dir_info[dir_path]
            md5s_or_md5_of_md5s.append(md5_of_md5s)
            total_bytes += bytes

    md5s_or_md5_of_md5s.sort()
    hasher = hashlib.sha256()
    for md5 in md5s_or_md5_of_md5s:
        hasher.update(md5)
    dir_info[parent][2] = hasher.hexdigest()
    dir_info[parent][3] = total_bytes
    return (unrecorded_files or unrecorded_dirs)
    
def verify_dup_dirs_integrity(dup_trees_list_file, dup_trees_list_file_name, dir_info, log_file):

    # Key is dir path marked. Value is str of line number where (first) seen. Used to ensure no higher dir is listed
    dirs_seen_so_far = {}

    line_number = 1
    for line in dup_trees_list_file:
        (md5_of_md5s, total_bytes, dirs_list) = process_dup_trees_list_file_line(line, dup_trees_list_file_name, line_number, log_file)
        if md5_of_md5s == None:
            continue
        for dir in dirs_list:
            if dir not in dir_info:
                log_file.write(RUNTIME_ERROR_PREFIX + " Dir " + dir + " not seen in disk scan in file " +\
                               dup_trees_list_file_name + " line " + str(line_number) +"\n")
                continue
            if dir in dirs_seen_so_far:
                log_file.write(RUNTIME_ERROR_PREFIX + " Dir " + dir +  " seen previously in line " +\
                               dirs_seen_so_far[dir] + " in file " +\
                               dup_trees_list_file_name + " line " + str(line_number) +"\n")
            else:
                dirs_seen_so_far[dir] = str(line_number)
            if md5_of_md5s != dir_info[dir][2]:
                log_file.write(RUNTIME_ERROR_PREFIX + " Dir " + dir +  " scanned md5-of-md5-s " +\
                               dir_info[dir][2] + ", md5-of-md5-s " + md5_of_md5s + " in file " +\
                               dup_trees_list_file_name + " line " + str(line_number) +"\n")
            if total_bytes != dir_info[dir][3]:
                log_file.write(RUNTIME_ERROR_PREFIX + " Dir " + dir +  " scanned total-bytes " +\
                               str(dir_info[dir][3]) + ", total-bytes " + str(total_bytes) + " in file " +\
                               dup_trees_list_file_name + " line " + str(line_number) +"\n")
        line_number += 1

    for dir in dirs_seen_so_far:
        successively_longer_paths = get_successively_longer_paths(dir)
        for successively_longer_path in successively_longer_paths:
            if successively_longer_path == dir:
                break
            if successively_longer_path in dirs_seen_so_far:
                log_file.write(RUNTIME_ERROR_PREFIX + " Dir " + dir + " in file " +\
                               dup_trees_list_file_name + " line " + dirs_seen_so_far[dir] +\
                               " has parent " +  successively_longer_path + " also listed at file line " +\
                                dirs_seen_so_far[successively_longer_path] +"\n")

    return dirs_seen_so_far


def verify_dup_files_integrity(dup_non_tree_files_list_file, dup_non_tree_files_list_file_name, file_info, dirs_seen_so_far, log_file):
    line_number = 1
    for line in dup_non_tree_files_list_file:
        (md5, total_bytes, files_list) =  process_dup_non_tree_files_list_file_line(line, dup_non_tree_files_list_file_name, line_number, log_file)
        if md5 == None:
            continue
        for (root_of_dup_tree, file_path) in files_list:
            if file_path not in file_info:
                log_file.write(RUNTIME_ERROR_PREFIX + " File " + file_path + " not seen in disk scan in file " +\
                               dup_non_tree_files_list_file_name + " line " + str(line_number) +"\n")
                continue
            if md5 != file_info[file_path][3]:
                log_file.write(RUNTIME_ERROR_PREFIX + " File " + file_path + " scanned md5-of-md5-s " +\
                               file_info[file_path][3] + ", md5-of-md5-s " + md5 + " in file " +\
                               dup_non_tree_files_list_file_name + " line " + str(line_number) +"\n")
            if total_bytes != file_info[file_path][0]:
                log_file.write(RUNTIME_ERROR_PREFIX + " File " + file_path + " scanned total-bytes " +\
                               str(file_info[file_path][0]) + ", total-bytes " + str(total_bytes) + " in file " +\
                               dup_non_tree_files_list_file_name + " line " + str(line_number) +"\n")
            if root_of_dup_tree is None:
                (dir_path, _) = os.path.split(file_path)
                dir_path += "/"
                if (dir_path) in dirs_seen_so_far:
                    log_file.write(RUNTIME_ERROR_PREFIX + " File " + file_path + "'s dir seen earlier in dup trees file line " +\
                                   dirs_seen_so_far[dir_path] +"\n")
        line_number += 1

def make_dups_remove_script(args):
    dup_non_tree_files_list_file_name = args[0]
    dup_trees_list_file_name = args[1]
    script_output_file_name = args[2]
    log_file_name = args[3]
    next_higher_priority_remove_paths = args[4:]

    try:

        validate_file_or_dir(dup_non_tree_files_list_file_name, is_file=True, is_write=False)
        validate_file_or_dir(dup_trees_list_file_name, is_file=True, is_write=False)
        rename_msg = rename_file_on_overwrite(script_output_file_name)
        if rename_msg is not None:
            print(rename_msg)
        validate_file_or_dir(script_output_file_name, is_file=True, is_write=True)
        rename_msg = rename_file_on_overwrite(log_file_name)
        if rename_msg is not None:
            print(rename_msg)
        validate_file_or_dir(log_file_name, is_file=True, is_write=True)
        for next_higher_priority_remove_path in next_higher_priority_remove_paths:
            validate_file_or_dir(next_higher_priority_remove_path, is_file=False, is_write=False)
        dup_non_tree_files_list_file = open(dup_non_tree_files_list_file_name)
        dup_trees_list_file = open(dup_trees_list_file_name)
        script_output_file = open(script_output_file_name, "w")
        log_file = open(log_file_name, "w")

    except IOError as err:
        raise UsageError(str(err))


    # Note on handling files;Files that are parts of processed trees are not independently processed by the duplicates
    # files deletion code (since we do not want to disturb the contents of trees). As a result while out of a list
    # of cloned dirs, only one will get retained, when it comes to files we may see multiple files being retained (because
    # they are parts of trees

    # Key is md5_of_md5s, value is [retained_dir, [list_of_deleted_clones]]
    delete_dir_info_by_md5_of_md5s = {}
    # Key is md5, value is [[list_of_retained_files], [list_of_deleted_duplicates]]
    delete_file_info_by_md5 = {}
    # Key is total size in bytes, value is md5_of_md5s
    deleted_dirs_md5_of_md5s_by_size = {}
    # Key is size in bytes, value is md5
    deleted_files_md5_by_size = {}
    # Used to record deleted trees so during file dedup we will know if any dup file belongs to a deleted tree
    # Key is dir, value is 0
    deleted_dirs = {}

    line_number = 1
    for line in dup_trees_list_file:
        (md5_of_md5s, total_bytes, dirs_list) = process_dup_trees_list_file_line(line, dup_trees_list_file_name, line_number, log_file)
        if total_bytes == 765122:
            flag = 1
        else:
            flag = 0
        if md5_of_md5s == None:
            continue
        
        dirs_to_delete = []
        if flag:
            print(" remove paths " + str(next_higher_priority_remove_paths))
        for next_higher_priority_remove_path in next_higher_priority_remove_paths:
            if len(dirs_list) == 1:
                break
            retry_this_remove_path = True
            while retry_this_remove_path:
                retry_this_remove_path = False
                if len(dirs_list) == 1:
                    break
                if flag:
                    print(" next_higher_priority_remove_path " + next_higher_priority_remove_path + " dirs_list: ")
                    for index in range(len(dirs_list)):
                        print("\t" + str(index) + ": " + dirs_list[index])
                for index in range(len(dirs_list)):
                    dir = dirs_list[index]
                    if dir.startswith(next_higher_priority_remove_path):
                        if flag:
                            print("Deleting " + dir)
                        dirs_to_delete.append(dir)
                        del dirs_list[index]
                        retry_this_remove_path = True
                        break
        # If more than one dir remains after applying all remove paths, just select the first entry for retention
        if flag:
            print("Final dirs list: ")
            for index in range(len(dirs_list)):
                print("\t" + str(index) + ": " + dirs_list[index])
        if len(dirs_list) > 1:
            dirs_to_delete.extend(dirs_list[1:])
            dirs_list = dirs_list[0:1]
        dir_to_retain = dirs_list[0]
        if flag:
            print(" dir_to_retain " + dir_to_retain)
        delete_dir_info_by_md5_of_md5s[md5_of_md5s] = [dir_to_retain, []]
        deleted_dirs_md5_of_md5s_by_size[total_bytes] = md5_of_md5s
        for dir_to_delete in dirs_to_delete:
            delete_dir_info_by_md5_of_md5s[md5_of_md5s][1].append(dir_to_delete)
            deleted_dirs[dir_to_delete] = 0
        line_number += 1

    line_number = 1
    for line in dup_non_tree_files_list_file:
        (md5, total_bytes, files_list) =  process_dup_non_tree_files_list_file_line(line, dup_non_tree_files_list_file_name, line_number, log_file)
        if md5 == None:
            continue

        files_to_retain = []
        for index in range(len(files_list)):
            (root_of_dup_tree, file_path) = files_list[index]
            # Remove files that are parts of trees since the trees have already been processed and the file should not be handled here   
            if root_of_dup_tree is not None:
                if root_of_dup_tree not in deleted_dirs:
                    # This file is in a tree that will not be deleted
                    files_to_retain.append(file_path)
                del files_list[index]
                break
        files_to_delete = []
        if files_to_retain != []:
            for index in range(len(files_list)):
                (_, file_path) = files_list[index]
                files_to_delete.append(file_path)
        elif files_list != []:
            for next_higher_priority_remove_path in next_higher_priority_remove_paths:
                if len(files_list) == 1:
                    break
                retry_this_remove_path = True
                while retry_this_remove_path:
                    retry_this_remove_path = False
                    if len(files_list) == 1:
                        break
                    for index in range(len(files_list)):
                        (_, file_path) = files_list[index]
                        if file_path.startswith(next_higher_priority_remove_path):
                            files_to_delete.append(file_path)
                            del files_list[index]
                            retry_this_remove_path = True
                            break
            # If more than one file remains after applying all remove paths, just select the first entry for retention
            if len(files_list) > 1:
                for index in range(len(files_list) - 1):
                    (_, file_path) = files_list[index + 1]
                    files_to_delete.append(file_path)
                files_list = files_list[0:1]
            (_, file_path) = files_list[0]
            files_to_retain.append(file_path)
            delete_file_info_by_md5[md5] = [files_to_retain, files_to_delete]
            deleted_files_md5_by_size[total_bytes] = md5
        line_number += 1

    delete_sizes = deleted_dirs_md5_of_md5s_by_size.keys()
    delete_sizes.sort(reverse = True)
    for total_bytes in delete_sizes:
        md5_of_md5s = deleted_dirs_md5_of_md5s_by_size[total_bytes]
        entry = delete_dir_info_by_md5_of_md5s[md5_of_md5s]
        script_output_file.write("# " + entry[0] + " " + str(total_bytes) + "\n")
        out_line = "rm -rf"
        for dir_to_delete in entry[1]:
            out_line += (" \"" + dir_to_delete + "\"")
        script_output_file.write(out_line + "\n")

    delete_sizes = deleted_files_md5_by_size.keys()
    delete_sizes.sort(reverse = True)
    for total_bytes in delete_sizes:
        md5 = deleted_files_md5_by_size[total_bytes]
        entry = delete_file_info_by_md5[md5]
        txt = ""
        for retained_file in entry[0]:
            txt += (" " + retained_file)
        script_output_file.write("#" + txt + " " + str(total_bytes) + "\n")
        out_line = "rm "
        for file_to_delete in entry[1]:
            out_line += (" \"" + file_to_delete + "\"")
        script_output_file.write(out_line + "\n")

    script_output_file.close()

def makedupsremovescript(args):
    pass

def get_dirs_within_path(path):
    for root, dirs, files in os.walk(path):
        return dirs

def get_files_within_path(path):
    for root, dirs, files in os.walk(path):
        return files

def list_diff_files(dcmp, output_file):
    left_list = []
    left_list.extend(dcmp.left_only)
    left_list.extend(dcmp.diff_files)
    right_list = []
    right_list.extend(dcmp.right_only)
    right_list.extend(dcmp.diff_files)
    (left_list, right_list) = remove_dups_based_on_cksms(dcmp.left, left_list, dcmp.right, right_list, )
    if len(left_list):
        output_file.write(dcmp.left + "\n")
        output_file.write("\t" + str(left_list) + "\n")
    if len(right_list):
        output_file.write(dcmp.right + "\n")
        output_file.write("\t" + str(right_list) + "\n")
    for common_dir in dcmp.common_dirs:
        sub_dcmp = dcmp.subdirs[common_dir]
        list_diff_files(sub_dcmp, output_file)

def remove_dups_based_on_cksms(left_path, left_list, right_path, right_list):
    left_md5 = {}
    for left_file in left_list:
        path = os.path.join(left_path, left_file)
        if os.path.isfile(path):
            left_md5[get_file_md5(path)] = left_file
    dups_detected = []
    for right_file in right_list:
        path = os.path.join(right_path, right_file)
        if os.path.isfile(path):
            md5 = get_file_md5(path)
            if md5 in left_md5:
                dups_detected.append((left_md5[md5], right_file))
    for (left_file, right_file) in dups_detected:
        left_list.remove(left_file)
        right_list.remove(right_file)
    return (left_list, right_list)

def read_dir_file_line(line, err_file, line_number):
    if line.startswith(RUNTIME_ERROR_PREFIX):
        err_file.write(str(line_number) + ": " + line.strip() + "\n")
        return (None, None, None, None, None)
    words = line.strip().split("\t")
    if len(words) < 5:
        err_file.write(RUNTIME_ERROR_PREFIX +\
                       " Bad line; expecting (tab-separated) file-path size atime mtime md5-cksm" +\
                       " in dir-list-file line " + str(line_number) + "\n")
        return (None, None, None)
    errs = ""
    file_path = words[0]
    size = None
    atime = None
    mtime = None
    try:
        size = int(words[1])
    except ValueError as err:
        errs += " Size value " + words[1] + " not int."
    try:
        atime = int(words[2])
    except ValueError as err:
        errs += " Atime value " + words[2] + " not int."
    try:
        mtime = int(words[3])
    except ValueError as err:
        errs += " Mtime value " + words[3] + " not int."
    if errs != "":
        err_file.write(RUNTIME_ERROR_PREFIX + " Bad line; (" + errs + ")" +\
                       " in dir-list-file line " + str(line_number) + "\n")
        return (None, None, None, None, None)
    return (file_path, size, atime, mtime, words[4])

def process_dup_trees_list_file_line(line, file_name, line_number, err_file):
    if line.startswith(RUNTIME_ERROR_PREFIX):
        err_file.write(str(line).strip() + " in file " + file_name + " line " + str(line_number) + "\n")
        return (None, None, None)
    words = line.strip().split("\t")
    if len(words) < 3:
        err_file.write(RUNTIME_ERROR_PREFIX + " Bad line; expecting (tab-separated) md5 total-bytes dir-names-list" +\
                       " in file " + file_name + " line " + str(line_number) + "\n")
        return (None, None, None)
    try:
        return (words[0], int(words[1]), words[2:])
    except ValueError as err:
        err_file.write(RUNTIME_ERROR_PREFIX +\
                       " Bad line; non-numeric total-bytes; expecting (tab-separated) md5 total-bytes dir-names-list" +\
                       " in file " + file_name + " line " + str(line_number) + "\n")
        return (None, None, None)

def process_dup_non_tree_files_list_file_line(line, file_name, line_number, err_file):
    if line.startswith(RUNTIME_ERROR_PREFIX):
        err_file.write(str(line).strip() + " in file " + file_name + " line " + str(line_number) + "\n")
        return (None, None, None)
    words = line.strip().split("\t")
    if len(words) < 3:
        err_file.write(RUNTIME_ERROR_PREFIX + " Bad line; expecting (tab-separated) md5 total-bytes file-names-list" + " in file " +\
                       file_name + " line " + str(line_number) + "\n")
        return (None, None, None)
    try:
        files_list = []
        for word in words[2:]:
            if "::" in word:
                index = word.find("::")
                file_path = word[index + len("::") : ]
                root_of_dup_tree = word[:index]
            else:
                file_path = word
                root_of_dup_tree = None
            files_list.append( (root_of_dup_tree, file_path) )

        return (words[0], int(words[1]), files_list)
    except ValueError as err:
        err_file.write(RUNTIME_ERROR_PREFIX +\
                       " Bad line; non-numeric total-bytes; expecting (tab-separated) md5 total-bytes dir-names-list" +\
                       " in file " + file_name + " line " + str(line_number) + "\n")
        return (None, None, None)

def rename_file_on_overwrite(file_name):
    if os.path.isfile(file_name) == True:
        rename = file_name + datetime.datetime.now().strftime(
            "-before-%Y-%m-%d-%H-%M-%S")
        os.rename(file_name, rename)
        return "Renaming " + file_name + " to " + rename
    return None

def rename_dir_on_overwrite(dir_name):
    if os.path.isdir(dir_name) == True:
        rename = dir_name + datetime.datetime.now().strftime(
            "-before-%Y-%m-%d-%H-%M-%S")
        os.rename(dir_name, rename)
        return "Renaming " + dir_name + " to " + rename
    return None

def validate_file_or_dir(file_or_dir_name, is_file, is_write,
                         no_over_write = True):
    if is_write:
        if os.path.exists(file_or_dir_name):
            if no_over_write:
                raise UsageError(file_or_dir_name + " cannot be overwritten")
            if is_file:
                if os.path.isfile(file_or_dir_name) == False:
                    raise UsageError(file_or_dir_name +
                                     " not found or is not a file")
            else:
                if os.path.isdir(file_or_dir_name) == False:
                    raise UsageError(file_or_dir_name +
                                     " not found or is not a dir")
            if os.access(file_or_dir_name, os.W_OK) == False:
                raise UsageError(
                    "You do not appear to have write permissions in " +
                    file_or_dir_name)
    else:
        if is_file:
            if os.path.isfile(file_or_dir_name) == False:
                raise UsageError(file_or_dir_name +
                                 " not found or is not a file")
        else:
            if os.path.isdir(file_or_dir_name) == False:
                raise UsageError(file_or_dir_name +
                                 " not found or is not a dir")
        if os.access(file_or_dir_name, os.R_OK) == False:
            raise UsageError("You do not appear to have read permissions in " +
                file_or_dir_name)

def add_file_stats(out_line, file_path):
    stat_info = os.stat(file_path)
    out_line += "\t" + str(stat_info[stat.ST_SIZE])
    out_line += "\t" + str(stat_info[stat.ST_ATIME])
    out_line += "\t" + str(stat_info[stat.ST_MTIME])
    out_line += "\t" + str(get_file_md5(file_path))
    return out_line

def get_file_md5(file_path):
    fd = open(file_path)
    hasher = hashlib.sha256()
    blocksize=1048576
    buf = fd.read(blocksize)
    while len(buf) > 0:
        hasher.update(buf)
        buf = fd.read(blocksize)
    return hasher.hexdigest()

def update_file_time(file_path, atime, mtime):
    os.utime(file_path, (atime, mtime))

def main():

    valid_args_list = [
        ("getdirlist", ["directory-to-scan", "out-file"], get_dir_list),
        ("matchdircopies",
            ["directory-list-file-golden", "directory-list-file-test",
             "golden-errors-file", "test-errors-file",
             "golden-only-file", "test-only-file",
             "size-or-cksm_mismatches-file", "name-matches-file"],
         match_dir_copies),
        ("updatefiletimes",
            ["directory-to-update", "directory-list-file-golden",
             "directory-list-file-test", "log-file"],
         update_file_times),
        ("comparedirsmatchnames",
            ["1st-dir", "2nd-dir", "output-file",],
         compare_dirs_match_names),
        ("listdups",
            ["directory-list-file", "...", "dup-non-tree-files-list-file", "dup-trees-list-file"],
         list_dups),
        ("verifyfilesintegrity",
            ["first-scanned-directory","first-directory-list-file",
             "...",
             "dup-non-tree-files-list-file", "dup-trees-list-file", "log-file"],
         verify_files_integrity),
        ("makedupsremovescript",
            ["dup-non-tree-files-list-file", "dup-trees-list-file", "script-output-file",
             "log-file", "next-higher-priority-remove-path", "..."],
         make_dups_remove_script),
    ]

    try:
        if len(sys.argv) == 1:
            raise UsageError("Missing args")
        valid_op_flag = False
        for valid_args in valid_args_list:
            # valid_args[0] is op. valid_args[1] is list of required args for that op. valid_args(3) is func to call
            if valid_args[0] == sys.argv[1]:
                valid_op_flag = True
                valid_arg_count_flag = True
                if "..." not in valid_args[1]:
                    if len(sys.argv) != len(valid_args[1]) + 2:
                        valid_arg_count_flag = False
                else:
                    if len(sys.argv) < len(valid_args[1]) + 2 - 1: # The -1 is to exclude the ... term
                        valid_arg_count_flag = False
                if valid_arg_count_flag == False:
                    raise UsageError(
                        "Wrong number of arguments for operation ' " +
                        sys.argv[1] + " ' ")

                valid_args[2](sys.argv[2:])
                break
        if valid_op_flag == False:
            raise UsageError("Unrecognized operation " +  sys.argv[1])

    except UsageError as err:
        print(err.msg)
        Usage(valid_args_list)
        sys.exit(1)
    except RuntimeError as err:
        print(err.msg)
        sys.exit(2)

if __name__ == "__main__":
    main()