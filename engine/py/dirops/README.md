# UNCHAOSS: Directory Operations: Common Code

## Overview 

This directory has a Python script with commandline options to 

* Generate a summary list of all files (including within subdirectories) of all files in a specified directory. For each file the full-path, size-in-bytes, access-time, modification-time, and MD5-checksum are generated.
* Identify mismatches between two directory copies.
* Compare all files across two directories and print name mismatches
* Identify all duplicate files across a set of directories. (Filenames are not used in identifying duplicates. Instead two files are assumed to be duplicates when they have identical sizes and identical MD5 checksums).
* Update all files' access and update times in a directory to match those from another directory. (This is needed when a directory is backed up without saving the files' modification times - so that the copies have their creation times set to the time of the backup. Sometimes you will want to know when the original file was created - perhaps because it helps you identify files from old directories. You should then remember to run this command to retrieve the times from the originals into your backups).

There are other Python packages that provide this functionality, however, none appear to document their function calls, in-memory data structures and intermediate file contents with a view to allowing easy customization.

*NOTE: The program writes some messages to stdout.*

## Setup

The first step is to run the 'getdirlist' command on each of your directories to produce a summary, one line per file. Other commands act on this summary. (The exception is the 'comparedirs' command which does not use a summary). Summaries from multiple directory scans can be concatenated into a single summary for use by any command.

This step can take a long time since every single file is opened and read to form an MD5 checksum.

*At this time all files must be accessible from the machine where this code runs.  Since this can create a huge space requirement on that machine, it is being considered to add support to open files across a network but this is currently not implemented.*

## Overall Invocation

python dirops.py <Command> <arguments>

## Commands

### "getdirlist" (prepare a summary of a directory)

**Invocation** *python dirops.py getdirlist directory-to-scan out-file*

This command scans all of the files in *directory-to-scan* and writes ione line per file to the summary file *out-file*.

The arguments are as follows. 

1. *directory-to-scan* Directory to scan
2. 'out-file' Summary file name.

Each summary file line contains

1. File name.
2. File size.
3. File access time.
4. File modification time.
5. File MD5 checksum.

### "matchdircopies" (identify mismatches between two directory copies)

**Invocation:** *python dirops.py matchdircopies directory-list-file-golden directory-list-file-test golden-errors-file test-errors-file golden-only-file test-only-file size-or-cksm_mismatches-file name-matches-file*


This command compares two directories using their summary files and identifies mismatches. This is useful to

* Verify the accuracy and completeness of a backup.
* Identify post-backup updates to a previously backed up directory

The arguments are as follows. The directories being compared are termed 'golden' and 'test'. The directories themselves need not be accessible; this command uses only the summaries:

1. *directory-list-file-golden* 'Golden' directory summary file.
2. *directory-list-file-test* 'Test' directory summary file.
3. *golden-errors-file* File to which (any) syntax errors in *directory-list-file-golden* are written.
4. *test-errors-file* File to which (any) syntax errors in *directory-list-file-test* are written.
5. *golden-only-file* File to which a list of files found only in the 'golden' directory are written.
6. *test-only-file* File to which a list of files found only in the 'test' directory are written. 
7. *size-or-cksm_mismatches-file* File to which a list of files with the same name but different sizes or MD5 checksums is written. 
8. *name-matches-file* File to which a list of files with the same name is written. Note that if they differ in size or checksum they will also be written to the *size-or-cksm_mismatches-file*.
*

### "comparedirs" (Compare all files across two directories and print name mismatches)

**Invocation:** *python dirops.py comparedirs 1st-dir 2nd-dir output-file*

This command compares files across two direcotries and lists files that are present only in either directory. It runs fast and does not use sizes or checksums and so will miss files with the same contents but having different names in the two directories.

The arguments are as follows.

1. *1st-dir* First directory to compare.
2. *2nd-dir* Second directory to compare.
3. *output-file* A file to which the list of mismatches is written.

### "listduplicatefiles" (Identify duplicate files and subdirectories across one or more directories)

**Invocation:** *python dirops.py directory-list-file [directory-list-file(s)] duplicates-list-file full-dup-dirs-list-file part-dup-dirs-list-file*

This command identifies and prints duplicate file names and duplicate directory names from across multuiple directories.

The arguments are as follows. 

1. *directory-list-file* Summary file for one of the source directories. This argument can repeat.
2. *duplicates-list-file* File to which duplicate files are written. All duplicates go on one line.
3. *full-dup-dirs-list-file* File to which names of fully duplicated direcories are written, one set per line.
4. *part-dup-dirs-list-file* File to which names of partially duplicated direcories are written, one set per line. (The idea is that directories that do not appear in this file do not contain any duplicate files and hence need further attention).

### "updatefiletimes" (Update the access and modification times of files in a directory copy to match source directory)

**Invocation:** *python dirops.py updatefiletimes directory-to-update directory-list-file-golden directory-list-file-test log-file*

This command updates access and modification times of files in a copied directory to those of the same files in the original directory.

The arguments are as follows. The directories being compared are termed 'golden' (original) and 'test' (copy): The 'test' directory must be accessible if any of the files end up getting modified:

1. *directory-to-update* The copied directory.
2. *directory-list-file-golden* 'Golden directory summary file.
3. *directory-list-file-test* 'Test' directory summary file.
4. *log-file* A file to which the list of changes is written.

