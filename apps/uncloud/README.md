# OVERVIEW:

UNCLOUD ("Uncle CB's Locally Organized Useful Documents") maintains a catalog of
all useful documents on a laptop/desktop and also retrieves and manages photos,
videos, audio and documents from remote devices and services like phones,
scanners, Dropbox, and Google Photos. (Taking back control of your documents
from external storage services is the basis for the name 'UNCLOUD').

UNCLOUD is capable of linking multiple laptops/desktops, to automatically
replicate sets of files without user intervention - file changes made on any
machine eventually get replicated to all machines. This capability can
facilitate collaboration, backup, and managing "travel" data copies.

UNCLOUD supports the following operations (each updating the catalog as needed).

- IMPORT: Make local copies to a local Inbox folder of remote files.

- EXPORT: Copy files and directories from a local Outbox folder to a device.

- CLEANUP: Delete device files listed in a local Trashlist folder.

- ADMIN: Perform various administrative tasks.

# IMPLEMENTATION:

**FILES and DIRECTORIES:**

File-locators:

File-locators are single words encoding the device name (or host computer name
for local files) and full path of a local or remote file. File locators are
valid local machine file names.

File-locators look like this (note the . after the device name):
    <device name OR local host name>.<Full path with / replaced by __ >
Before replacing / by __ existing __ sequences are first escaped out by
replacing + by ++ then replacing __ by _+_ with the last step getting
repeated while any __ is still present in the string.
(In addition, any _/ text in the string is replaced by _@_ after first
replacing any @ in the original with @@. Otherwise any _/ would get changed
to ___ but incorrectly restored to /_ )

    File-locator examples:
        A file '/storage/emulated/0/xxx.txt' on an Android phone named yyy:
            yyy.__storage__emulated__0__xxx.txt
        A file '/tmp/__init.py__' on the local host (whose name is svrA):
            svrA.__tmp___+_init.py_+_
        A file '/tmp/__abc++pqr.txt__' on the local host (whose name is svrA) is
            svrA.__tmp___+_abc++++pqr.txt_+_
        A file '/tmp/abc___pqr.txt' on the local host (whose name is svrA) is
            svrA.__tmp__abc_+_+_pqr.txt
Note that deeply nested paths can lead to very long file locators that are in
danger of exceeding the maximum Linux file name size of 255 bytes. Such paths
are more likely in software packages than in user directories and it is best to
exclude packages from uncloud scanning (by specifying 'exclude_dirs' in the .ini
file entry for the device) and to archive the package, if needed, separately.

Catalog and Catalog-Index folders :

The catalog folder has one file for each unique MD5 checksum seen across all
local and remote files. (Files having the same MD5 are duplicates). Each file's
name is the MD5 and the contents are one line for each file copy (local or
remote) which has that MD5. Each line contains the following separated by tabs:

    File-locator File-modification-time File-size-on-Disk.

The Catalog-Index folder has one symbolic link for each local and each remote
file. The name of the link is the file's file-locator and the link target is the
catalog folder file for the file's MD5.

Commands and responses folders:

The commands folder contains commands-JSON files, each with a sequence of
UNCLOUD commands and associated parameters. On launch UNCLOUD processes all the
files it finds in this folder then exits.

(It does not further check for files added during the run. This implies that for
unattended UNCLOUD operation some sort of external mechanism will be needed to
periodically launch UNCLOUD, and insert and remove command files and response
- described below - files).

For each commands-JSON file processed, UNCLOUD creates a responses-JSON file in
the responses folder with responses (including errors encountered) to the
processed commands. A responses-JSON name is based on its commands-JSON name.

UNCLOUD attempts to process commands-JSON files in parallel (launching the first
command of each file in a separate 'thread of execution'). The actual number of
parallel launches is governed by various limits in the configuration file. These
limits may depend on the type of device (eg 'not more than 2 simultaneous Google
Photos downloads') or may apply to the entire run (eg 'not more than 10 parallel
transfers across all types of device'. In the code the term 'link' means any one
type of device while 'device' means a device of that type. For example local USB
ports are links while SD cards inserted into those ports are devices).

The responses directory is also used by each run to save a run log and a JSON
file corresponding to the .ini files passed as commandline args. A JSON is not
saved for runs for which the commandline is a JSON.

(Sample commands JSON files are available in this folder).

Inbox folder:

The IMPORT operation places files copied in from remotes in the inbox folder. The
remote file locator of each file is used as the file name in this folder. The
DRYRUN operation is the same as IMPORT except it just goes through the motions
but does not actually copy any files. It is done to get an idea of what would
have got copied. DRYRUN also logs the size of each transfer and also logs an
out-of-space situation on the local device.

Outbox folder:

The EXPORT operation copies files from the outbox folder to devices then removes
the files. The file locator of each file is used as the file name in this folder.
Files in the outbox are copies of files on the local machine and each is deleted
after it gets copied. Outbox files are not recorded in the Catalog.

Trashlist folder:

The trashlist folder holds a list of files to be deleted from devices. For each
file to be deleted a symbolic link is present in this folder. The name of the
link is the file's file-locator and the link points to the catalog folder file
for the file's MD5. (This folder resembles the Catalog-Index folder). Each
link is removed after the corresponding file gets deleted at the device.

**RUNTIME**

UNCLOUD can be configured for simultaneous parallel transfers if the type of
link (eg USB) and the type of source device (eg Android phone) both support it.
Note that while the total speedup may be less than what you expect due to
limitations of the underlying threading mechanism, this feature still allows you
to launch all your commands together.

Overall class structure. (Note that all file and directory names are based on
expected defaults and can be overridden by a different set of .ini file(s)):

1) Each type of link (eg USB) is handled by its own subclass of UncloudBase.

    1a) To implement a new type of link write a new subclass

    1b) UncloudBase is not "pure virtual". It does much of the heavy lifting.
    
   (There is no source-device-type subclass. To implement two devices with very
   different characteristics on the same type of link - eg a phone and a 
   camera both on a USB link - use two subclasees 'USB-phone' and USB-camera').

2) Subclass instances handle parallel transfers internally by spawning threads

3) The .ini or JSON configuration file specifies links, source devices,
and constraints on parallel transfers.

**CONFIG FILE HANDLING**

Config (.ini) files are read into memory by the Python standard library package
'configparser' (see Python docs for configparser info) as a 'sections/options'
hierarchy. The special section, DEFAULTS, is not read into memory but instead
its options are replicated into every other section. (Since these replicated
options are not part of the explicitly specified set of options for each section
they sometimes need special handling in code).

In this program sections/options are converted to a dict with sections as keys
and options as values. A seperate dict is created to hold the DEFAULTS (so they
can be identified if needed) and stored under a top level key "only_defaults".

A second virtual hierarchy has been implemented within some sections by having
two part option names with the two parts separated by a double underscore (eg
link0__option0). This means link0 is a subsection with option0 an option within
it. When converting to the dict, a sub dict is inserted; the option name becomes
link0 and the option value becomes a dict with option0 as a key.

**PyCharm DEBUGGING WARNING**

Using PyCharm on Linux, it has been observed that putting breakpoints in
non-main-thread code (ie the threads used to launch commands) can disrupt flow
of control.
