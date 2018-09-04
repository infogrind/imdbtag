#!/usr/bin/python


import sys
import os
import getopt
import logging

import imdbtag

# Global options with default values.
askmode = False
clearmode = False
forcemode = False
offlinemode = False
dirmode = False
directory = ''
fileperm = None
dirperm = None
quietmode = False
summary = False
tvlabel = False
recoverymode = False


def main():
    # Default logging level: info. We don't show "ERROR", "DEBUG", etc., as
    # this is meant for user consumption.
    logging.basicConfig(
            format='%(levelname)s: %(message)s',
            level=logging.INFO)  # Default logging level
    args = parse_options(sys.argv[1:])

    setModuleConfig()

    # Make sure argument is present
    if not (len(args) >= 1 or dirmode):
        logging.error("Syntax error.\n")
        usage()
        sys.exit(2)

    # Print a banner if we are in recovery mode.
    if recoverymode:
        imdbtag.print_banner("Recovery Mode", 0)

    # Now do the actual processing, depending on whether we are in directory
    # mode or not.
    if dirmode:
        imdbtag.process_directory(directory)
    else:
        for b in args:
            # Need to strip trailing slash of directory names, otherwise
            # dirname and basename get confused.
            b = b.rstrip('/')
            imdbtag.process(os.path.dirname(b), os.path.basename(b))

    # If enabled, we display the summary.
    if summary:
        imdbtag.print_offline_notifications()


def setModuleConfig():
    imdbtag.setConfig(
            askmode,
            clearmode,
            forcemode,
            offlinemode,
            fileperm,
            dirperm,
            quietmode,
            tvlabel,
            recoverymode
            )


def usage():
    print \
"""Usage: imdbtag [options] <directory|file> [, <directory|file>, ...]
             imdbtag [options] -d <directory>

The first version renames the files and directories given on the command line.
The second version renames all files and directories in the directory specified
with -d.

Options: -h      Display help text.
                 -i      Always ask for confirmation
                 -f      Force mode: Ignore existing .name and .imdb files.
                 -o      Offline mode: Runs without user interaction and displays a
                             summary at the end. Ideal for cron jobs.
                 -c      Clear mode: Remove all tagging information (all .imdb, .rating,
                             .name, .ignore files).
                 -q      Quiet mode: Do not display any progress information. (This
                             makes mostly sense in offline mode.)
                 -s      Print a summary at the end of the processing.
                 -t      Add string " (TV Series)" to directory name for series.
                 -r      Recovery mode: Re-process previously renamed directories to
                             correct them.
                 -v      Verbose output (for debugging)
                 -F <perm>
                             Explicitly specify file permissions. <perm> is the mode that all
                             created files should have, in octal base. E.g., -F 664
                 -D <perm>
                             Explicitly specify directory permissions. This works like -F but
                             applies to created directories. E.g., -D 775
"""


def parse_options(args):

    # Access global variables
    global forcemode, askmode, dirmode
    global directory, offlinemode, clearmode
    global fileperm, dirperm
    global quietmode, summary, tvlabel
    global recoverymode

    # Parse options using Getopt; display an error and exit if options could
    # not be parsed.
    try:
        opts, args = getopt.getopt(args, "hvifcord:qstF:D:")
    except getopt.GetoptError, err:
        logging.error(str(err))
        usage()
        sys.exit(2)

    # Set variables according to options
    for opt, val in opts:
        if opt == "-h":
            usage()
            sys.exit()

        if opt == "-c":
            clearmode = True
            logging.debug('Clear mode enabled.')

        elif opt == "-v":
            logging.getLogger().setLevel(logging.DEBUG)
            logging.info('Debug mode enabled.')

        elif opt == "-i":
            askmode = True
            logging.debug('Ask mode enabled.')

        elif opt == "-f":
            logging.debug('Force mode enabled.')
            forcemode = True

        elif opt == "-o":
            logging.debug('Offline mode enabled.')
            offlinemode = True

        elif opt == "-q":
            logging.debug('Quiet mode enabled.')
            logging.getLogger().setLevel(logging.WARN)

        elif opt == "-r":
            logging.debug('Recovery mode enabled.')
            recoverymode = True

        elif opt == "-s":
            logging.debug('Summary enabled')
            summary = True

        elif opt == "-t":
            logging.debug('TV series label enabled')
            tvlabel = True

        elif opt == "-d":
            directory = val
            logging.debug('Directory mode for directory "' + directory + '".')
            dirmode = True

        elif opt == "-F":
            try:
                fileperm = int(val, 8)
            except ValueError:
                logging.error('Illegal file permission specification.')
                fileperm = None
            else:
                logging.debug('Setting file permissions to ' + oct(fileperm))

        elif opt == "-D":
            try:
                dirperm = int(val, 8)
            except ValueError:
                logging.error('Illegal directory permission specification.')
                dirperm = None
            else:
                logging.debug('Setting directory permissions to ' +
                              oct(dirperm))

        else:
            assert False, "unhandled option"

        # Recovery mode and offline mode are incompatible.
        if recoverymode and offlinemode:
            logging.error('Recovery mode and offline mode are incompatible.')
            usage()
            sys.exit(2)

    return args
