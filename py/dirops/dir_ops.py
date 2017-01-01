__author__ = 'chitrabhanu'

import os, stat
import sys
import datetime
import hashlib
import time
from filecmp import dircmp

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

def get_dir_list(args):
    dir_name = args[0]
    out_file_name = args[1]

    try:

        validate_file_or_dir(dir_name, is_file=False, is_write=False)
        rename_msg = rename_file_on_overwrite(out_file_name)
        if rename_msg is not None:
            print rename_msg
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
                out_line += file_path[dir_name_len:] + " "
                out_line = add_file_stats(out_line, file_path)
                out_file.write(out_line+"\n")
            except IOError as err:
                out_file.write(RUNTIME_ERROR_PREFIX + "(non-fatal) " +
                               str(err) + " (file = " + file_path + ")\n")
                continue
    out_file.close()

def match_dir_lists(args):
    dir_list_file_golden_name = args[0]
    dir_list_file_test_name = args[1]
    golden_errors_file_name = args[2]
    test_errors_file_name = args[3]
    golden_only_file_name = args[4]
    test_only_file_name = args[5]
    size_mismatches_file_name = args[6]
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
            print rename_msg
        validate_file_or_dir(golden_errors_file_name, is_file=True,
                             is_write=True)
        golden_errors_file = open(golden_errors_file_name, "w")

        rename_msg = rename_file_on_overwrite(test_errors_file_name)
        if rename_msg is not None:
            print rename_msg
        validate_file_or_dir(test_errors_file_name, is_file=True, is_write=True)
        test_errors_file = open(test_errors_file_name, "w")

        rename_msg = rename_file_on_overwrite(golden_only_file_name)
        if rename_msg is not None:
            print rename_msg
        validate_file_or_dir(golden_only_file_name, is_file=True, is_write=True)
        golden_only_file = open(golden_only_file_name, "w")

        rename_msg = rename_file_on_overwrite(test_only_file_name)
        if rename_msg is not None:
            print rename_msg
        validate_file_or_dir(test_only_file_name, is_file=True, is_write=True)
        test_only_file = open(test_only_file_name, "w")

        rename_msg = rename_file_on_overwrite(size_mismatches_file_name)
        if rename_msg is not None:
            print rename_msg
        validate_file_or_dir(size_mismatches_file_name, is_file=True,
                             is_write=True)
        size_mismatches_file = open(size_mismatches_file_name, "w")

        rename_msg = rename_file_on_overwrite(name_matches_file_name)
        if rename_msg is not None:
            print rename_msg
        validate_file_or_dir(name_matches_file_name, is_file=True, is_write=True)
        name_matches_file = open(name_matches_file_name, "w")

    except IOError as err:
        raise UsageError(str(err))

    golden_dir_info = {}
    test_dir_info = {}

    try:
        update_dir_info(dir_list_file_golden, golden_dir_info, golden_errors_file)
        golden_errors_file.close()
        update_dir_info(dir_list_file_test, test_dir_info, test_errors_file)
        test_errors_file.close()

    except IOError as err:
        raise RuntimeError(str(err))

    name_matches_count = 0
    golden_only_count = 0
    golden_count = 0
    golden_total = len(golden_dir_info)
    for golden_dir_entry in golden_dir_info:
        golden_count += 1
        if (golden_count % 10000 ) == 0:
            print "Processed ", golden_count, "out of", golden_total,\
                "name_matches_count", name_matches_count,\
                "golden_only_count", golden_only_count
        if golden_dir_entry not in test_dir_info.keys():
            golden_only_count += 1
            golden_only_file.write(str(golden_dir_entry) + "\n")
        else:
            name_matches_count += 1
            name_matches_file.write(str(golden_dir_entry) + "\n")
            (golden_size, _, _, golden_cksm) = golden_dir_info[golden_dir_entry]
            (test_size, _, _, test_cksm) = test_dir_info[golden_dir_entry]
            if golden_size != test_size:
                size_mismatches_file.write("GOLDEN: " + str(golden_dir_entry) +
                                           str(golden_dir_info[
                                                   golden_dir_entry]) + "\n")
                size_mismatches_file.write("TEST: " + str(golden_dir_entry) +
                                           str(test_dir_info[
                                                   golden_dir_entry]) + "\n")
    golden_only_file.close()
    name_matches_file.close()
    size_mismatches_file.close()

    for test_dir_entry in test_dir_info:
        if test_dir_entry not in golden_dir_info.keys():
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
            print rename_msg
        validate_file_or_dir(log_file_name, is_file=True, is_write=True)
        log_file = open(log_file_name, "w")

    except IOError as err:
        raise UsageError(str(err))

    golden_dir_info = {}
    test_dir_info = {}

    try:
        update_dir_info(dir_list_file_golden, golden_dir_info, log_file)
        update_dir_info(dir_list_file_test, test_dir_info, log_file)
        dir_list_file_golden.close()
        dir_list_file_test.close()

    except IOError as err:
        raise RuntimeError(str(err))
    
    for test_dir_entry in test_dir_info:
        if "  " not in test_dir_entry:
            continue
        if test_dir_entry in golden_dir_info.keys():
            (golden_size, golden_atime, golden_mtime, golden_cksm) =\
                golden_dir_info[test_dir_entry]
            (test_size, test_atime, test_mtime, test_cksm) =\
                test_dir_info[test_dir_entry]
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

def list_duplicate_files(args):
    dir_list_file_names = args[0:-3]
    duplicates_list_file_name = args[len(args)-3]
    full_dup_dirs_list_file_name = args[len(args)-2]
    part_dup_dirs_list_file_name = args[len(args)-1]

    try:

        for dir_list_file_name in dir_list_file_names:
            validate_file_or_dir(dir_list_file_name, is_file=True,
                                 is_write=False)

        rename_msg = rename_file_on_overwrite(duplicates_list_file_name)
        if rename_msg is not None:
            print rename_msg
        validate_file_or_dir(duplicates_list_file_name, is_file=True, is_write=True)
        duplicates_list_file = open(duplicates_list_file_name, "w")

        rename_msg = rename_file_on_overwrite(full_dup_dirs_list_file_name)
        if rename_msg is not None:
            print rename_msg
        validate_file_or_dir(full_dup_dirs_list_file_name, is_file=True, is_write=True)
        full_dup_dirs_list_file = open(full_dup_dirs_list_file_name, "w")

        rename_msg = rename_file_on_overwrite(part_dup_dirs_list_file_name)
        if rename_msg is not None:
            print rename_msg
        validate_file_or_dir(part_dup_dirs_list_file_name, is_file=True, is_write=True)
        part_dup_dirs_list_file = open(part_dup_dirs_list_file_name, "w")

    except IOError as err:
        raise UsageError(str(err))

    # Key is md5 checksum, value is list of file-paths having that md5 (checksum)
    file_paths_for_md5_cksm = {}
    # Key is md5 checksum, value is size of all files having that checksum. 
    file_size_for_md5_cksm = {}
    # Key is dir-nm, value is [ [md5] ]. One entry for each directory where for
    # one or more files in it, at least one copy (same contents, possibly
    # different name) has been found. Another dictionary, 'dirs_with_not_all_files_duped'
    # holds the names of directories in this list for which at least one file is
    # not duplicated elsewhere. Any directory in this list but not in that has
    # all of its files duplicated and is separately reported.
    dirs_with_dup_files = {}
    # Key is dir-nm, value is "". Created from dirs_with_dup_files by locating dirs
    # in that list that are not fully duplicated
    dirs_with_not_all_files_duped = {}
    # List of lists, one entry for each set of directories all of which have the
    # same set of duplicate files and for each set of directories without files
    # whose subdirectories might be clones. Each entry's a list of the directories'
    # names
    clones_list = []
    # List of indexes of clones_list entries that are not be be processed either
    # because they contain subdirectories that are not clones or because their
    # parent directories are fully cloned and hence using only the parents will
    # suffice.
    clone_skip_flags_list = []
    # Key is dir-nm, value is the index of the clones_list index containing dir
    clone_index_for_cloned_dir = {}

    try:
        for dir_list_file_name in dir_list_file_names:
            dir_list_file = open(dir_list_file_name)
            print "Reading ", dir_list_file_name
            update_dup_info(dir_list_file, file_paths_for_md5_cksm,
                            file_size_for_md5_cksm, duplicates_list_file)
            dir_list_file.close()

    except IOError as err:
        raise RuntimeError(str(err))

    print "Number of unique files: ", len(file_paths_for_md5_cksm)
    print "Counting directories with duplicated files"
    update_dup_dir_info(file_paths_for_md5_cksm, dirs_with_dup_files)
    print "Number of directories with duplicated files: ", len(dirs_with_dup_files)


    print "Printing duplicates-list-file"
    for dup_entry in file_paths_for_md5_cksm:
        if len(file_paths_for_md5_cksm[dup_entry]) == 1:
            continue
        duplicates_list_file.write(dup_entry + ": " +
                                str(file_paths_for_md5_cksm[dup_entry]) + "\n")

    print "Determining partially duplicated directories," \
        " writing ERRORS to duplicates-list-file"
    try:
        for dir_list_file_name in dir_list_file_names:
            dir_list_file = open(dir_list_file_name)
            print "Re-reading ", dir_list_file_name
            get_partial_dups(dir_list_file, dirs_with_dup_files,
                             dirs_with_not_all_files_duped, duplicates_list_file)
            dir_list_file.close()

    except IOError as err:
        raise RuntimeError(str(err))

    duplicates_list_file.close()

    print "Identifying mutually-duplicated dirs (also printing names of duplicated FILES from not-fully-duplicated dirs)"
    print "**************************************************"
    print "Note that the code as currently written counts each set of duplicate files WITHIN any directory as a single"
    print "    file for comparison purposes when identifying duplicate sets of directories. This may lead to members of"
    print "    such sets containing different numbers of files due to the presence of duplicates."
    print "**************************************************"
    for this_dir in dirs_with_dup_files:
        other_dirs_with_these_keys = {}
        this_dir_name_has_been_printed = False
        for md5 in dirs_with_dup_files[this_dir]:
            for file_path in file_paths_for_md5_cksm[md5]:
                (file_dir,_) = os.path.split(file_path)
                if file_dir == this_dir:
                    continue
                if file_dir not in other_dirs_with_these_keys:
                    other_dirs_with_these_keys[file_dir] = [md5]
                else:
                    other_dirs_with_these_keys[file_dir].append(md5)
        full_matches = [this_dir]
        for that_dir in other_dirs_with_these_keys:
            if this_dir not in dirs_with_not_all_files_duped and \
                            that_dir not in dirs_with_not_all_files_duped and\
                            set(dirs_with_dup_files[this_dir]) == \
                            set(dirs_with_dup_files[that_dir]):
                full_matches.append(that_dir)
            else:
                # Partial match, print file name pairs common to both dirs
                if this_dir_name_has_been_printed == False:
                    part_dup_dirs_list_file.write(this_dir + "\n")
                    this_dir_name_has_been_printed = True
                part_dup_dirs_list_file.write("\t" + that_dir + "\n")
                this_name = None
                that_name = None
                for key in other_dirs_with_these_keys[that_dir]:
                    for path in file_paths_for_md5_cksm[key]:
                        (dir,name) = os.path.split(path)
                        if dir == this_dir:
                            this_name = name
                        elif dir == that_dir:
                            that_name = name
                    if this_name != that_name:
                        part_dup_dirs_list_file.write("\t\t" + this_name + "*" +
                                                      that_name + "\n")
                    else:
                        part_dup_dirs_list_file.write("\t\t" + this_name +"\n")
        if len(full_matches) > 1:
            clone_index = -1
            for full_match in full_matches:
                if full_match in clone_index_for_cloned_dir:
                    if clone_index != -1:
                        assert clone_index ==  clone_index_for_cloned_dir[full_match]
                    else:
                        clone_index = clone_index_for_cloned_dir[full_match]
            if clone_index == -1:
                clone_index = len(clones_list)
                clones_list.append([])
                clone_skip_flags_list.append(False)
            for full_match in full_matches:
                entry = os.path.abspath(full_match)
                if entry not in clone_index_for_cloned_dir:
                    clones_list[clone_index].append(entry)
                    clone_index_for_cloned_dir[entry] = clone_index
    print "Printing fully-'cloned' dirs"
    prune_clones_list(clones_list, clone_skip_flags_list, clone_index_for_cloned_dir)
    for clone_index in range(len(clones_list)):
        if clone_skip_flags_list[clone_index]:
            continue
        clones_list_entry = clones_list[clone_index]
        if len(clones_list_entry):
            full_dup_dirs_list_file.write(str(clones_list_entry) + "\n")
    full_dup_dirs_list_file.close()
    part_dup_dirs_list_file.close()

def get_dirs_within_path(path):
    for root, dirs, files in os.walk(path):
        return dirs

def get_files_within_path(path):
    for root, dirs, files in os.walk(path):
        return files

def prune_clones_list(clones_list, clone_skip_flags_list,
                      clone_index_for_cloned_dir):
    clone_index_for_path = {}
    # One entry per clone index value, holding list of descendant paths which
    # have not yet been verified to be clones of the descendants of the other
    # paths at this clone index
    uncloned_descendant_paths = []
    # One entry per clone index value, holding list of clone indexes of
    # decendant paths verified to be clones of the descendants of the other
    # paths at this clone index
    cloned_descendant_indexes = []
    leaf_path_already_processed = {}
    for clone_index in range(len(clones_list)):
        clones_list_entry = clones_list[clone_index]
        clones_list_entry.sort()
        uncloned_descendant_paths.append([])
        cloned_descendant_indexes.append([])
        for path in clones_list_entry:
            assert path not in clone_index_for_path
            clone_index_for_path[clone_index] = clone_index
            dirs = get_dirs_within_path(path)
            if len(dirs):
                leaf_path_already_processed[path] = False
                for dir in dirs:
                    uncloned_descendant_paths[clone_index].append(os.path.join(path, dir))
    for leaf_path in leaf_path_already_processed:
        if leaf_path_already_processed[leaf_path]:
            continue
        all_are_leaves = True
        clone_index = clone_index_for_path[leaf_path]
        for clone in clones_list[clone_index]:
            if clone not in leaf_path_already_processed:
                all_are_leaves = False
            else:
                leaf_path_already_processed[clone] = True
        if all_are_leaves == False:
            continue
        process_set_of_cloned_nodes(clone_index, clones_list,
                clone_skip_flags_list, clone_index_for_cloned_dir,
                clone_index_for_path, uncloned_descendant_paths,
                                    cloned_descendant_indexes)
    for clone_index in range(len(clones_list)):
        if len(uncloned_descendant_paths[clone_index]):
            clone_skip_flags_list[clone_index] = True
        else:
            for index in cloned_descendant_indexes[clone_index]:
                clone_skip_flags_list[index] = True


def process_set_of_cloned_nodes(clone_index, clones_list, clone_skip_flags_list,
        clone_index_for_cloned_dir, clone_index_for_path, uncloned_descendant_paths,
                                cloned_descendant_indexes):
    parent_paths = []
    parent_clone_index = None
    parents_have_same_clone_index = True
    # Set when parents contain no files and are hence potential clones
    parents_are_potential_clones = True
    for index in range(len(clones_list[clone_index])):
        current_path = clones_list[clone_index][index]
        parent_path = os.path.abspath(os.path.join(current_path, ".."))
        parent_paths.append(parent_path)
        if parent_path in clone_index_for_path:
            parents_are_potential_clones = False
            if parent_clone_index is not None:
                if clone_index_for_path[parent_path] != parent_clone_index:
                    parents_have_same_clone_index = False
                    break
            else:
                parent_clone_index = clone_index_for_path[parent_path]
        else:
            if len(get_files_within_path(parent_path)) != 0:
                parents_are_potential_clones = False
    if parents_are_potential_clones:
        # All parents contain no files and are hence potential clones. Enter
        # them as a new clone entry
        parent_clone_index = len(clones_list)
        clones_list.append([])
        clone_skip_flags_list.append(False)
        uncloned_descendant_paths[parent_clone_index].append([])
        cloned_descendant_indexes[parent_clone_index].append([])
        for parent_path in parent_paths:
            clones_list[parent_clone_index].append(parent_path)
            clone_index_for_cloned_dir[parent_path] = parent_clone_index
            dirs = get_dirs_within_path(parent_path)
            for dir in dirs:
                uncloned_descendant_paths[parent_clone_index].append(os.path.join(parent_path, dir))
            uncloned_descendant_paths[parent_clone_index].extend()
    if parents_have_same_clone_index:
        if len(set(parent_paths)) == len(parent_paths):
            return
        cloned_descendant_indexes[parent_clone_index] = clone_index
        # TBD: Remove this clone_index's paths from the uncloned dirs list. If list thus becomes empty, then recurse back into this function
        


def make_full_paths(args):
    dir_path = args[0]
    dir_list_file_name = args[1]
    full_paths_list_file = args[2]

    try:

        validate_file_or_dir(dir_path, is_file=False, is_write=False)
        validate_file_or_dir(dir_list_file_name, is_file=True, is_write=False)
        dir_list_file = open(dir_list_file_name)

        rename_msg = rename_file_on_overwrite(full_paths_list_file)
        if rename_msg is not None:
            print rename_msg
        validate_file_or_dir(full_paths_list_file, is_file=True, is_write=True)
        full_paths_list_file = open(full_paths_list_file, "w")

    except IOError as err:
        raise UsageError(str(err))

    try:
        update_to_full_paths(dir_path, dir_list_file, full_paths_list_file)

    except IOError as err:
        raise RuntimeError(str(err))

    full_paths_list_file.close()

def compare_dirs(args):
    dir1 = args[0]
    dir2 = args[1]
    output_file = args[2]

    try:

        validate_file_or_dir(dir1, is_file=False, is_write=False)
        validate_file_or_dir(dir2, is_file=False, is_write=False)

        rename_msg = rename_file_on_overwrite(output_file)
        if rename_msg is not None:
            print rename_msg
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

def update_to_full_paths(dir_base, dir_file, full_paths_file):
    line_number = 1
    for line in dir_file:
        (file_path, size, atime, mtime, md5_checksum) =\
            read_dir_file_line(line, full_paths_file, line_number)
        if file_path is None:
            return
        full_paths_file.write(os.path.join(dir_base, file_path) + " " +
                              str(size) + " " + str(atime) + " " + str(mtime) +
                              " " + md5_checksum + "\n")
        line_number += 1

def get_partial_dups(dir_file, dirs_with_dup_files, dirs_with_not_all_files_duped,
                     err_file):
    line_number = 1
    for line in dir_file:
        (file_path, size, atime, mtime, md5_checksum) = read_dir_file_line(line, err_file, line_number)
        if file_path is None:
            return
        (file_dir, _) = os.path.split(file_path)

        if file_dir in dirs_with_dup_files and md5_checksum not in dirs_with_dup_files[file_dir]:
            dirs_with_not_all_files_duped[file_dir] = ""
        line_number += 1

def update_dup_info(dir_file, file_paths_for_md5_cksm, file_size_for_md5_cksm,
                    err_file):
    line_number = 1
    for line in dir_file:
        (file_path, size, _, _, md5_checksum) = read_dir_file_line(line, err_file, line_number)
        if file_path is None:
            return
        if md5_checksum in file_paths_for_md5_cksm:
            if size != file_size_for_md5_cksm[md5_checksum]:
                    err_file.write("ERROR: line " + str(line_number) +
                                   ": Sz msmtch (key=" + md5_checksum + ")" +
                                    " size-1 " + str(file_size_for_md5_cksm[md5_checksum]) +
                                    " file-1 " + file_paths_for_md5_cksm[md5_checksum][0] +
                                    " size-2 " + str(size) +
                                    " file-2 " + file_path + "\n")
            file_paths_for_md5_cksm[md5_checksum].append((file_path))
        else:
            file_paths_for_md5_cksm[md5_checksum] = [file_path]
            file_size_for_md5_cksm[md5_checksum] = size
        line_number += 1

def update_dup_dir_info(file_paths_for_md5_cksm, dirs_with_dup_files):
    for md5_checksum in file_paths_for_md5_cksm:
        if(len(file_paths_for_md5_cksm[md5_checksum]) == 1):
            continue
        for file_path in file_paths_for_md5_cksm[md5_checksum]:
            (file_dir, _) = os.path.split(file_path)
            if file_dir in dirs_with_dup_files:
                dirs_with_dup_files[file_dir].append(md5_checksum)
            else:
                dirs_with_dup_files[file_dir] = [md5_checksum]

def update_dir_info(dir_file, dir_info, err_file):
    line_number = 1
    for line in dir_file:
        (file_path, size, atime, mtime, md5_checksum) = read_dir_file_line(line, err_file, line_number)
        if file_path is None:
            return
        dir_info[file_path] = (size, atime, mtime, md5_checksum)
        line_number += 1
        
def read_dir_file_line(line, err_file, line_number):
    if line.startswith(RUNTIME_ERROR_PREFIX):
        err_file.write(str(line_number) + ": " + line.strip() + "\n")
        return
    words = line.split()
    file_path = words[0]
    addl_words = 0
    if len(words) < 5:
        err_file.write(str(line_number) + ": (Bad line, not five words) " +
                       line.strip() + "\n")
        return
    elif len(words) > 5:
        addl_words = len(words) - 5
        file_path_len = line.find(words[0])
        file_path_len += len(words[0])
        for index in range(addl_words):
            file_path_len = line.find(words[index+1], file_path_len)
            file_path_len += len(words[index+1])
        file_path = line[:file_path_len].strip()
    errs = ""
    size = None
    atime = None
    mtime = None
    try:
        size = int(words[addl_words + 1])
    except ValueError as err:
        errs += " Size value " + words[addl_words + 1] + " not int."
    try:
        atime = int(words[addl_words + 2])
    except ValueError as err:
        errs += " Atime value " + words[addl_words + 2] + " not int."
    try:
        mtime = int(words[addl_words + 3])
    except ValueError as err:
        errs += " Mtime value " + words[addl_words + 3] + " not int."
    if errs != "":
        err_file.write(str(line_number) + ": (" + errs + ") " + line.strip() +
                       "\n")
        return (None, None, None, None, None)
    return (file_path, size, atime, mtime, words[addl_words + 4])

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
    out_line += str(stat_info[stat.ST_SIZE]) + " "
    out_line += str(stat_info[stat.ST_ATIME]) + " "
    out_line += str(stat_info[stat.ST_MTIME]) + " "
    out_line += str(get_file_md5(file_path)) + " "
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
        ("matchdirlists",
            ["directory-list-file-golden", "directory-list-file-test",
             "golden-errors-file", "test-errors-file",
             "golden-only-file", "test-only-file",
             "size-mismatches-file", "name-matches-file"],
         match_dir_lists),
        ("updatefiletimes",
            ["directory-to-update", "directory-list-file-golden",
             "directory-list-file-test", "log-file"],
         update_file_times),
        ("listduplicatefiles",
            ["directory-list-file", "...", "duplicates-list-file",
             "full-dup-dirs-list-file", "part-dup-dirs-list-file"],
         list_duplicate_files),
        ("makefullpaths",
            ["directory-path", "directory-list-file", "full-paths-list-file",],
         make_full_paths),
        ("comparedirs",
            ["1st-dir", "2nd-dir", "output-file",],
         compare_dirs)
    ]

    try:
        if len(sys.argv) == 1:
            raise UsageError("Missing args")
        valid_op_flag = False
        for valid_args in valid_args_list:
            if valid_args[0] == sys.argv[1]:
                valid_op_flag = True
                valid_arg_count_flag = True
                if "..." not in valid_args:
                    if len(sys.argv) != len(valid_args[1]) + 2:
                        valid_arg_count_flag = False
                else:
                    if len(sys.argv) < len(valid_args[1]) + 1:
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
        print err.msg
        Usage(valid_args_list)
        sys.exit(1)
    except RuntimeError as err:
        print err.msg
        sys.exit(2)

if __name__ == "__main__":
    main()