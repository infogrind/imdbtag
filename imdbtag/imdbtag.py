#!/usr/bin/python


import sys
import os
import getopt
import re

# To use TheMovieDB.org
from .apis import tmdbapi

# Alternatively, to use IMDb, use the following import instead:
# (However, know that as of today 2012-12-29, IMDB search doesn't work anymore
# with IMDbPy.)
# from apis.imdbapi import *

# We use the useful parse-torrent-name library to parse the movie name; much
# better way to do it than the old, manual, regex-based way.
try:
    import PTN
except ImportError:
    sys.stderr.write("You need to install the PTN package!\n")
    sys.stderr.write("See github.com/divijbindlish/parse-torrent-name\n")
    sys.exit(1)

import warnings
warnings.filterwarnings('ignore', '.*no module named lxml.*')
warnings.filterwarnings('ignore', 'falling back to "beautifulsoup"')

# Global options with default values.
verbose = False
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

# Two lists for notifications in offline mode. The first is for notifications
# of renamings done, the second for unknown movies (where no IMDb match was
# found).
notifications_rename = []
notifications_unknown = []
notifications_nb_unchanged = 0
notifications_nb_ignored = 0


def main():
    args = parse_options(sys.argv[1:])

    # Make sure argument is present
    if not (len(args) >= 1 or dirmode):
        errmsg("Syntax error.\n")
        usage()
        sys.exit(2)

    # Print a banner if we are in recovery mode.
    if recoverymode:
        print_banner("Recovery Mode", 0)

    # Now do the actual processing, depending on whether we are in directory
    # mode or not.
    if dirmode:
        process_directory(directory)
    else:
        for b in args:
            # Need to strip trailing slash of directory names, otherwise
            # dirname and basename get confused.
            b = b.rstrip('/')
            process(os.path.dirname(b), os.path.basename(b))

    # If enabled, we display the summary.
    if summary:
        print_offline_notifications()


def process_directory(b):
    """Process the directory ``b``"""

    # Make sure the directory is valid.
    if not is_directory(b):
        errmsg("Directory " + b + " does not exist.\n")
        return

    entries = os.listdir(b)
    entries.sort()
    for f in entries:
        process(b, f)


def process(b, f):
    global notifications_nb_ignored

    # First check if the file or directory indicated by f actually exists.
    if not os.path.exists(os.path.join(b, f)):
        errmsg('"' + f + '" does not exist.')
        return

    if is_ignored(b, f):
        notifications_nb_ignored += 1
        status('Skipping "' + f + '".')

    # In clear mode, we remove all .imdb etc. files from directories.
    elif clearmode:
        if is_directory(os.path.join(b, f)):
            debug('Clearning directory "' + f + '".')
            clear_directory(b, f)
    # For a directory, we process it unless it contains an ".ignore" file.
    elif is_directory(os.path.join(b, f)):
        tag(b, f)

    # If there is a movie file that is not in its own directory, we ask the
    # user whether a directory should be made for the file. If yes, we continue
    # by processing the new directory; otherwise we skip the file.
    elif is_movie_file(f):
        debug("Found movie file without directory: " + f)

        # In recovery mode, only directories can be processed.
        if recoverymode:
            status('Skipping file "' + f + '" in recovery mode.')
        else:
            d = mkdir_and_move(b, f)
            if d != "":
                tag(b, d)


def tag(b, d):

    debug('Verifying whether "' + os.path.join(b, d) +
          '" is a valid directory.')
    assert(is_directory(os.path.join(b, d)))

    # In recovery mode, we first rename the directory to its original name and
    # then clear all special files (except the .original file).
    if recoverymode:
        if has_original_file(b, d):
            o = original_from_file(b, d)
            try:
                debug('Recovery mode: Clearing directory "' + d +
                      '" and renaming ' + 'it to "' + o + '".')
                clear_directory(b, d)
                rename_directory(b, d, o)
            except:
                errmsg('Could not rename "' + d + '" to "' + o +
                       '" in recovery mode.')
            else:
                d = o
        else:
            status('Skipping "' + d +
                   '" in recovery mode; no .original file found.')
            return

    n = get_correct_name(b, d)
    debug('get_correct_name() returned "' + n + '".')

    # If get_correct_name returns an empty string, the user has indicated that
    # the directory should be ignored. If we are in offline mode, it means that
    # no movie was found on IMDb.
    if n == "":
        if offlinemode:
            offline_notice_unknown(d)
        else:
            mark_ignored(b, d)
    else:
        # We can go ahead and rename.
        rename_directory(b, d, n)


def clear_directory(b, d):
    assert(is_directory(os.path.join(b, d)))

    if is_ignored(b, d):
        remove_ignore_file(b, d)
    if has_imdb_file(b, d):
        remove_imdb_file(b, d)
    if has_name_file(b, d):
        remove_name_file(b, d)
    if has_rating_file(b, d):
        remove_rating_file(b, d)


def rename_directory(b, d, n):
    global notifications_nb_unchanged

    old = os.path.join(b, d)
    new = os.path.join(b, n)

    if cmp(old, new) == 0:
        status("Directory \"" + d + "\" is already named right.")
        notifications_nb_unchanged += 1
    elif os.path.exists(new):
        errmsg('Cannot rename "' + d + '" to "' + n +
               '", directory already exists.')
    else:
        status('Renaming "' + d + '" to "' + n + '".')
        try:
            os.rename(old, new)
            offline_notice_renamed(d, n)
        except OSError:
            errmsg('There was an error renaming "' + d + '" to "' + n + '".')
        else:
            # Save original directory name, but only if there is not yet an
            # .original file.
            if not has_original_file(b, n):
                set_original_file(b, n, d)


def mkdir_and_move(b, f):
    n, e = split_filename(f)
    if askmode and not confirm(
            prompt='Do you want to move the file "' + f +
            '" to the directory "' + n + '"? ',
            resp=True):
        return ""

    # Create the directory
    d = os.path.join(b, n)
    debug('Creating directory "' + d + '".')
    os.mkdir(d)

    # Update permissions if set
    if dirperm is not None:
        change_permissions(d, dirperm)

    # Move the file. We are doing this using a system command, since there is
    # no good 'move' interface in python. (We cannot use shutils.move, since
    # this would first copy the source to the destination and then delete the
    # source, which takes a long time with movie files.)
    debug('Moving "' + f + '" to "' + n + '".')
    r = os.system('mv "' + os.path.join(b, f) + '" "' + d + '"')

    # Check OS return code.
    if r == 0:
        return n
    else:
        errmsg("Could not create directory \"" + d + "\".")
        return ""


def get_correct_name(b, d):
    """Returns the correct name for the directory ``d``."""

    debug('Called get_correct_name("' + b + '", "' + d + '").')

    # This method determines the movie name as follows.
    # - If no .name file exists or if we are in force mode, we look up the
    #   movie using get_movie_for_directory().
    # - Otherwise, we are not in force mode and a .name file exists, so we can
    #   take the name from that file.
    # If get_movie_for_directory() returns an empty string, it means that no
    # movie could be determined for this directory, so we mark it as ignored in
    # future (unless we are in offline mode, in which case we need to add it to
    # the list of notifications).
    # Otherwise, we set the .name file with the returned name.

    if (not has_name_file(b, d)) or forcemode:
        if has_name_file(b, d):
            debug('Looking up "' + d + '" because force mode is enabled.')
        else:
            debug('No name file found for "' + d + '", looking up.')

        n = get_movie_for_directory(b, d)

        # We need to add "Unrated", etc. if present in the original title.
        if not n == "":
            n = add_title_attributes(d, n)
    else:
        debug('Using name from file for "' + d + '".')
        n = name_from_file(b, d)

    # Write the name to the file if it is not empty.
    if not n == "":
        set_name_file(b, d, n)

    # Finally we return the name.
    return n


def get_movie_for_directory(b, d):
        if not forcemode and has_imdb_file(b, d):
            debug('Found .imdb file for "' + d + '".')
            # We look up the movie on imdb according to its ID.  Because there
            # is an .imdb file but no .name file, it is reasonable to assume
            # that the script was already run once and the user chose not to
            # give a custom name.
            m = movie_by_id(id_from_file(b, d))
            n = m.nice_title()
        else:
            debug('Looking up "' + d + '" on IMDb with the user\'s help.')
            # Ask user to establish movie and custom name.
            m, n = movie_by_name(clean_name(d))

        # If a corresponding IMDb movie was found, then we set the .imdb file
        # and the rating file.
        if m is not None:
            set_imdb_file(b, d, m.id)
            set_rating_file(b, d, m.rating)

        return n


def add_title_attributes(d, s):
        # If the name is not empty, we check if the original directory name
        # contained the words "unrated" or "director's cut" and if so then we
        # add the respective word to the title.
        unrated = (re.search(r"unrated", d, re.I) != None)
        dircut = (re.search(r"director.?s.?cut", d, re.I) != None)
        telesync = (re.search(r"telesync", d, re.I) != None)
        remastered = (re.search(r"remastered", d, re.I) != None)

        if unrated and dircut:
            s = s + " (Unrated Director's Cut)"
        elif unrated:
            s = s + " (Unrated)"
        elif dircut:
            s = s + " (Director's Cut)"

        if remastered:
            s = s + " (remastered)"

        if telesync:
            s = s + " TELESYNC"

        return s


def movie_by_id(id):
    """Returns a Movie object corresponding to the IMDb id ``id``."""

    if not offlinemode:
        print "Getting extended movie information..."
    else:
        debug('Getting extended movie information for id ' + id + '...')

    return tmdbapi.api_get_movie(id)


def movie_by_name(s):

    m = imdb_search_movie(s)

    # We give the user the opportunity to add a custom title, but not in
    # offline mode.
    if not offlinemode:
        n = ask_custom_title(m)
    else:
        n = ""

    # If the user hasn't chosen a custom title but m is a valid movie object,
    # we take the name from it.
    if n == "" and m is not None:
        n = m.nice_title()

    # Before we return the movie, we fetch it again using movie_by_id() in
    # order to get the extended information such as the rating, unless speedy
    # mode is actived.
    if m is not None:
        return movie_by_id(m.id), n
    else:
        return m, n


def imdb_search_movie(s):

    if offlinemode:
        return imdb_search_movie_offline(s)
    else:
        return imdb_search_movie_interactive(s)


def imdb_search_movie_offline(s):
    results = imdb_query(s)
    if len(results) == 0:
        debug('Offline mode: No match found on IMDb for "' + s + '".')
        return None
    else:
        m = results[0]
        debug('Returning IMDb match "' + m.nice_title() + '" for query "' + s +
              '".')
        return m


def imdb_search_movie_interactive(s):
    results = imdb_query(s)
    print "Searching for movie '%s'" % s
    print_movie_list(s, results)

    # The main loop keeps asking for user input, until the user has made a
    # valid choice, in which case we break from the loop or exit the function.
    while True:
        if len(results) == 0:
            print """
            No results found. Please enter a new string to search for, or just
            press enter to skip IMDb search.
            """
        else:
            print """
            Enter correct # or enter another name for a new search.
            Just press enter to choose the first entry.
            Enter 'i' if you don't want to look up this movie in IMDb.
            """

        a = raw_input("> ")

        # Just pressing return is a shortcut for selecting the first movie in
        # the list (if the list is nonempty).
        if len(results) > 0 and a == "":
            a = '1'

        # If the user enters 'i', or if no movie is found and he presses just
        # enter, then no movie is returned (i stands for "ignore").
        if a == "i" or (a == "" and len(results) == 0):
            return None

        # If the user entered a number, take the corresponding entry from the
        # list.
        elif a.isdigit():
            n = int(a)
            # Check if the user entered an imdb ID
            if n > 1000:
                # Do a search by IMDb ID
                results = imdb_query(a)
                print_movie_list(a, results)
                continue
            elif n < 1 or n > len(results):
                print "Invalid number."
                continue

            m = results[n-1]
            sys.stdout.write('You selected "' + m.nice_title() +
                             '". Is this correct? ')

            if confirm(prompt="", resp=True):
                break
            else:
                continue

        else:
            # Do a new search.
            results = imdb_query(a)
            print_movie_list(a, results)
            continue

    return m


def ask_custom_title(m):
    while True:
        if m is None:
            print """
            Enter the name for this movie, or enter to ignore this directory in
            future.
            """
        else:
            print """
            Enter a custom title for this movie, or just enter if the name is
            fine.
            """

        n = raw_input("> ")

        if n != "":
            sys.stdout.write('You entered "' + n + '". Please confirm ')
            if confirm(prompt="", resp=True):
                break
        else:
            # Name is empty.
            if m is None:
                sys.stdout.write('You have chosen to ignore this directory. ' +
                                 'Please confirm ')

                if confirm(prompt="", resp=True):
                    break
            else:
                # No confirmation needed here.
                break

    return n


def imdb2movie(imdb_m):
    """Converts a movie object of the IMDbpy package into our own movie
    class."""
    out_encoding = sys.stdout.encoding or "UTF-8"

    # We set the variable idx depending on whether the imdb_m object has a
    # field called 'imdbIndex'.
    if 'imdbIndex' in imdb_m:
        idx = imdb_m['imdbIndex'].encode(out_encoding, 'replace')
    else:
        idx = ""

    return Movie(
            imdb_m['title'].encode(out_encoding, 'replace'),
            'year' in imdb_m and imdb_m['year'] or '',
            idx,
            imdb_m.movieID.encode(out_encoding, 'replace'),
            imdb_m['kind'].encode(out_encoding, 'replace'),
            'rating' in imdb_m and str(imdb_m['rating']) or ''
            )


def is_movie_file(f):
    # Simple check based on extension
    movieext = ['avi', 'mpg', 'mp4', 'mpeg', 'divx', 'mov', 'mkv', 'm4v']
    for e in movieext:
        if has_extension(f, e):
            return True

    return False


def has_extension(f, e):
    return get_extension(f).lower() == e.lower()


def get_extension(f):
    n, e = split_filename(f)
    return e


def split_filename(f):
    m = re.match(r"(.*)\.([\w]{1,3})", f)
    if m is None:
        return f, ""
    else:
        return m.group(1), m.group(2)


def mark_ignored(b, d):
    debug('Marking directory "' + d + '" as ignored.')
    touch_file(os.path.join(b, d, '.ignore'))


def is_ignored(b, f):
    # By default, we ignore directories that start with a dot or a colon.
    if re.match(r"^(\.|:).*", f):
        return True

    # Otherwise, a directory is ignored if it contains an .ignore file.
    return is_directory(os.path.join(b, f)) and has_file(b, f, '.ignore')


def has_name_file(b, d):
    return has_file(b, d, '.name')


def has_imdb_file(b, d):
    return has_file(b, d, '.imdb')


def has_rating_file(b, d):
    return has_file(b, d, '.rating')


def has_original_file(b, d):
    return has_file(b, d, '.original')


def is_writable(b, d):
    p = os.path.join(b, d)
    b = os.access(p, os.W_OK)
    if b:
        debug('Path "' + p + '" has write permission.')
    else:
        debug('Path "' + p + '" DOES NOT have write permission.')

    return b


def has_file(b, d, n):
    debug('Checking existence of file "' + os.path.join(b, d, n) + '".')
    return os.path.exists(os.path.join(b, d, n))


def name_from_file(b, d):
    return text_from_file(b, d, '.name')


def id_from_file(b, d):
    return re.sub('^tt', '', text_from_file(b, d, '.imdb'))


def rating_from_file(b, d):
    return text_from_file(b, d, '.rating')


def original_from_file(b, d):
    return text_from_file(b, d, '.original')


def text_from_file(b, d, f):
    fullpath = os.path.join(b, d, f)
    debug('Reading text from file "' + fullpath + '".')
    assert(os.path.exists(fullpath))
    fh = open(fullpath, 'r')
    s = fh.readline().rstrip('\n')
    fh.close()
    return s


def set_name_file(b, d, n):
    set_file(b, d, '.name', n)


def set_imdb_file(b, d, i):
    set_file(b, d, '.imdb', "tt" + i)


def set_rating_file(b, d, r):
    set_file(b, d, '.rating', r)


def set_original_file(b, d, s):
    set_file(b, d, '.original', s)


def set_file(b, d, f, s):
    fullpath = os.path.join(b, d, f)
    debug('Writing text "' + s + '" to file "' + fullpath + '".')
    try:
        fh = open(fullpath, 'w')
        fh.write(s + '\n')
        fh.close()
    except IOError:
        errmsg('Error: Could not write to file "' + fullpath + '".')
    else:
        if fileperm is not None:
            change_permissions(fullpath, fileperm)


def remove_ignore_file(b, d):
    remove_file(b, d, ".ignore")


def remove_imdb_file(b, d):
    remove_file(b, d, ".imdb")


def remove_name_file(b, d):
    remove_file(b, d, ".name")


def remove_rating_file(b, d):
    remove_file(b, d, ".rating")


def remove_file(b, d, n):
    os.remove(os.path.join(b, d, n))


def touch_file(f):
    try:
        fh = open(f, 'w')
        fh.close()
    except IOError:
        errmsg('Error: Could not write to file "' + f + '".')
    else:
        if fileperm is not None:
            change_permissions(f, fileperm)


def change_permissions(p, perm):
    try:
        os.chmod(p, perm)
    except OSError:
        errmsg('Unable to change permissions of "' + p + '".')


def print_movie_list(q, l):
    if len(l) > 0:
        header = 'Results for query "' + q + '":'
        print header
        print "=" * len(header)

    c = 0
    for m in l:
        c += 1
        t = m.nice_title()
        k = m.kind
        if k != 'movie' and k != 'tv series':
            try:
                t = t + " (" + k + ")"
            except UnicodeDecodeError:
                errmsg('There was an Unicode problem')

        print "%2d: %s" % (c, t)


def imdb_query(n):

    in_encoding = sys.stdin.encoding or "UTF-8"
    out_encoding = sys.stdout.encoding or "UTF-8"

    debug("in_encoding = %s." % in_encoding)
    debug("out_encoding = %s." % out_encoding)

    if n.isdigit():
        id = int(n)
        r = []
        m = tmdbapi.api_get_movie(id)
        if m:
            r.append(m)
    else:
        title = unicode(n, in_encoding, 'replace')
        r = tmdbapi.api_search_movie(title)

    debug("Found %d possible movies." % len(r))

    # If there is a movie in r whose name is exactly n, then we move it to the
    # top of the list.
    r = move_to_top_if_exists(r, n)

    return r


def move_to_top_if_exists(r, n):
    c = 0
    for m in r:
        if c > 0 and m.nice_title() == n:
            mm = r.pop(c)
            r.insert(0, mm)
            debug('Found "' + n + '" in the list, moving to top.')
            break
        c += 1

    return r


def clean_name(s):

    debug('Determining clean name for "' + s + '"')
    info = PTN.parse(s)
    title = info['title']
    debug('Clean name is "' + title + '"')

    return title


def offline_notice_unknown(s):
    global notifications_unknown
    notifications_unknown.append(s)


def offline_notice_renamed(a, b):
    global notifications_rename
    notifications_rename.append([a, b])


def print_offline_notifications():
    global notifications_rename, notifications_unknown

    # If nothing has been renamed and quiet mode is enabled, just return.
    if len(notifications_rename) == 0 and quietmode:
            return

    # Width of screen in characters
    w = 80

    # Separator
    sep = " -> "

    if len(notifications_rename) > 0:
        print_banner("Renamed directories", w)
        for p in notifications_rename:
            (a, b) = p
            print limit_string(a, w) + "\n" + sep + limit_string(b, w - len(sep))

        print
        print str(len(notifications_rename)) + " directories renamed."
    else:
        print "No directories renamed."

    if len(notifications_unknown) > 0:
        print_banner("Directories without match", w)
        for d in notifications_unknown:
            print limit_string(d, w)

    if notifications_nb_unchanged > 0:
        print str(notifications_nb_unchanged) + " directories unchanged."
    if notifications_nb_ignored > 0:
        print str(notifications_nb_ignored) + " directories ignored."


def print_banner(s, w):
    # Default banner width is 80 characters.
    if w == 0:
        w = 80

    print
    print "=" * w
    print s
    print "=" * w


def limit_string(s, l):
    if len(s) <= l:
        return s + " " * (l - len(s))
    else:
        return s[0:l - 3] + "..."


def strip_word(s, w):
    """Removes all occurrences of the word ``w`` from the string ``s``. If there
    are spaces on the left and the right, they will be compacted into a single
    space after replacement.
    The method is case-insensitive.
    """

    # Compile the regular expression and disable case-sensitivity.
    wr1 = re.compile(" " + w + " ", re.I)
    wr2 = re.compile(w, re.I)

    # Case 1: Spaces on both sides.
    s = wr1.sub(" ", s)

    # All other cases: just remove it.
    s = wr2.sub("", s)

    return s


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
    global verbose, forcemode, askmode, dirmode
    global directory, offlinemode, clearmode
    global fileperm, dirperm
    global quietmode, summary, tvlabel
    global recoverymode

    # Parse options using Getopt; display an error and exit if options could not
    # be parsed.
    try:
        opts, args = getopt.getopt(args, "hvifcord:qstF:D:")
    except getopt.GetoptError, err:
        errmsg(str(err))
        usage()
        sys.exit(2)

    # Set variables according to options
    for opt, val in opts:
        if opt == "-h":
            usage()
            sys.exit()

        if opt == "-c":
            clearmode = True
            debug('Clear mode enabled.')

        elif opt == "-v":
            verbose = True
            debug('Verbose mode enabled.')

        elif opt == "-i":
            askmode = True
            debug('Ask mode enabled.')

        elif opt == "-f":
            debug('Force mode enabled.')
            forcemode = True

        elif opt == "-o":
            debug('Offline mode enabled.')
            offlinemode = True

        elif opt == "-q":
            debug('Quiet mode enabled.')
            quietmode = True

        elif opt == "-r":
            debug('Recovery mode enabled.')
            recoverymode = True

        elif opt == "-s":
            debug('Summary enabled')
            summary = True

        elif opt == "-t":
            debug('TV series label enabled')
            tvlabel = True

        elif opt == "-d":
            directory = val
            debug('Directory mode for directory "' + directory + '".')
            dirmode = True

        elif opt == "-F":
            try:
                fileperm = int(val, 8)
            except ValueError:
                errmsg('Illegal file permission specification.')
                fileperm = None
            else:
                debug('Setting file permissions to ' + oct(fileperm))

        elif opt == "-D":
            try:
                dirperm = int(val, 8)
            except ValueError:
                errmsg('Illegal directory permission specification.')
                dirperm = None
            else:
                debug('Setting directory permissions to ' + oct(dirperm))

        else:
            assert False, "unhandled option"

        # Recovery mode and offline mode are incompatible.
        if recoverymode and offlinemode:
            errmsg('Recovery mode and offline mode are incompatible.')
            usage()
            sys.exit(2)

    return args


def debug(s):
    if verbose:
        sys.stderr.write("DEBUG: " + s + "\n")


def status(s):
    if not quietmode:
        print(s)


def errmsg(s):
    sys.stderr.write("ERROR: " + s + "\n")


def is_directory(d):
    return os.path.exists(d) and os.path.isdir(d)


def confirm(prompt=None, resp=False):
        """prompts for yes or no response from the user. Returns True for yes and
        False for no.

        'resp' should be set to the default value assumed by the caller when
        user simply types ENTER.

        >>> confirm(prompt='Create Directory?', resp=True)
        Create Directory? [y]|n:
        True
        >>> confirm(prompt='Create Directory?', resp=False)
        Create Directory? [n]|y:
        False
        >>> confirm(prompt='Create Directory?', resp=False)
        Create Directory? [n]|y: y
        True

        """

        if prompt is None:
                prompt = 'Confirm'

        if resp:
                prompt = '%s [%s]|%s: ' % (prompt, 'y', 'n')
        else:
                prompt = '%s [%s]|%s: ' % (prompt, 'n', 'y')

        while True:
                ans = raw_input(prompt)
                if not ans:
                        return resp
                if ans not in ['y', 'Y', 'n', 'N']:
                        print 'Please enter y or n.'
                        continue
                if ans == 'y' or ans == 'Y':
                        return True
                if ans == 'n' or ans == 'N':
                        return False


class Movie:
    def __init__(self, title, year, index, id, kind, rating):
        self.title = title
        self.year = year
        self.index = index
        self.id = id
        self.kind = kind
        self.rating = rating

    def nice_title(self):
        # We only add the index if it is II or more.
        if self.index != '' and self.index != 'I':
            yearstr = "(" + str(self.year) + "-" + self.index + ")"
        else:
            # The file doesn't have an index.
            yearstr = "(" + str(self.year) + ")"

        # Replace : with - in title
        t = re.sub(r"([\w]):\s", r"\1 - ", self.title)

        # Replace ampersands with and
        t = re.sub(r"\s*&\s*", r" and ", t)

        # Replace slash with dash
        t = re.sub(r"/", r"-", t)

        # Add year
        t = t + " " + yearstr

        # If it is a TV series, add this to the name.
        if self.kind == 'tv series' and tvlabel:
            t = t + " (TV Series)"

        return t


# This is the most important line: it calls the main function if this program
# is called directly.
if __name__ == "__main__":
    main()
