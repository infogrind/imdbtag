import sys
import os
import re
import logging

# To use TheMovieDB.org
from apis import tmdbapi

# Alternatively, to use IMDb, use the following import instead:
# (However, know that as of today 2012-12-29, IMDB search doesn't work anymore
# with IMDbPy.)
# from apis.imdbapi import *

# We use the useful parse-torrent-name library to parse the movie name; much
# better way to do it than the old, manual, regex-based way.
try:
    import PTN
except ImportError:
    logging.error("You need to install the PTN package!\n")
    logging.error("See github.com/divijbindlish/parse-torrent-name\n")
    sys.exit(1)

import warnings
warnings.filterwarnings('ignore', '.*no module named lxml.*')
warnings.filterwarnings('ignore', 'falling back to "beautifulsoup"')

# Global config object
basicConfig = {
        'askmode': False,
        'clearmode': False,
        'forcemode': False,
        'offlinemode': False,
        'fileperm': None,
        'dirperm': None,
        'quietmode': False,
        'tvlabel': False,
        'recoverymode': False,
        }


# Two lists for notifications in offline mode. The first is for notifications
# of renamings done, the second for unknown movies (where no IMDb match was
# found).
# Note: Using global variables is definitely not the nicest way to do this.
# This will have to be part of a next refactoring round, so I am adding a TODO
# marker for now.
notifications_rename = []
notifications_unknown = []
notifications_nb_unchanged = 0
notifications_nb_ignored = 0


# This method allows clients of the module to set certain global options. This
# is probably not the most beautiful way to handle this. For now, it is
# advisable not to change the options between different calls to module
# functions, you don't know what might happen. ;)
def setConfig(
        askmode=False,
        clearmode=False,
        forcemode=False,
        offlinemode=False,
        fileperm=None,
        dirperm=None,
        quietmode=False,
        tvlabel=False,
        recoverymode=False
        ):
    basicConfig['askmode'] = askmode
    basicConfig['clearmode'] = clearmode
    basicConfig['forcemode'] = forcemode
    basicConfig['offlinemode'] = offlinemode
    basicConfig['fileperm'] = fileperm
    basicConfig['dirperm'] = dirperm
    basicConfig['quietmode'] = quietmode
    basicConfig['tvlabel'] = tvlabel
    basicConfig['recoverymode'] = recoverymode


def process_directory(b):
    """Process the directory ``b``"""

    # Make sure the directory is valid.
    if not _is_directory(b):
        logging.error("Directory " + b + " does not exist.\n")
        return

    entries = os.listdir(b)
    entries.sort()
    for f in entries:
        process(b, f)


def process(b, f):
    global notifications_nb_ignored

    # First check if the file or directory indicated by f actually exists.
    if not os.path.exists(os.path.join(b, f)):
        logging.error('"' + f + '" does not exist.')
        return

    if _is_ignored(b, f):
        notifications_nb_ignored += 1
        logging.info('Skipping "' + f + '".')

    # In clear mode, we remove all .imdb etc. files from directories.
    elif basicConfig['clearmode']:
        if _is_directory(os.path.join(b, f)):
            logging.debug('Clearning directory "' + f + '".')
            _clear_directory(b, f)
    # For a directory, we process it unless it contains an ".ignore" file.
    elif _is_directory(os.path.join(b, f)):
        _tag(b, f)

    # If there is a movie file that is not in its own directory, we ask the
    # user whether a directory should be made for the file. If yes, we continue
    # by processing the new directory; otherwise we skip the file.
    elif _is_movie_file(f):
        logging.debug("Found movie file without directory: " + f)

        # In recovery mode, only directories can be processed.
        if basicConfig['recoverymode']:
            logging.info('Skipping file "' + f + '" in recovery mode.')
        else:
            d = _mkdir_and_move(b, f)
            if d != "":
                _tag(b, d)
    else:
        logging.info("Skipping %s (neither a directory nor a movie file)." % f)


def _tag(b, d):

    logging.debug('Verifying whether "' + os.path.join(b, d) +
                  '" is a valid directory.')
    assert(_is_directory(os.path.join(b, d)))

    # In recovery mode, we first rename the directory to its original name and
    # then clear all special files (except the .original file).
    if basicConfig['recoverymode']:
        if _has_original_file(b, d):
            o = _original_from_file(b, d)
            try:
                logging.debug('Recovery mode: Clearing directory "' + d +
                              '" and renaming ' + 'it to "' + o + '".')
                _clear_directory(b, d)
                _rename_directory(b, d, o)
            except OSError:
                logging.error('Could not rename "' + d + '" to "' + o +
                              '" in recovery mode.')
            else:
                d = o
        else:
            logging.info('Skipping "' + d +
                         '" in recovery mode; no .original file found.')
            return

    n = _get_correct_name(b, d)
    logging.debug('_get_correct_name() returned "' + n + '".')

    # If get_correct_name returns an empty string, the user has indicated that
    # the directory should be ignored. If we are in offline mode, it means that
    # no movie was found on IMDb.
    if n == "":
        if basicConfig['offlinemode']:
            _offline_notice_unknown(d)
        else:
            _mark_ignored(b, d)
    else:
        # We can go ahead and rename.
        _rename_directory(b, d, n)


def _clear_directory(b, d):
    assert(_is_directory(os.path.join(b, d)))

    if _is_ignored(b, d):
        _remove_ignore_file(b, d)
    if _has_imdb_file(b, d):
        _remove_imdb_file(b, d)
    if _has_name_file(b, d):
        _remove_name_file(b, d)
    if _has_rating_file(b, d):
        _remove_rating_file(b, d)


def _rename_directory(b, d, n):
    global notifications_nb_unchanged

    old = os.path.join(b, d)
    new = os.path.join(b, n)

    if cmp(old, new) == 0:
        logging.info("Directory \"" + d + "\" is already named right.")
        notifications_nb_unchanged += 1
    elif os.path.exists(new):
        logging.error('Cannot rename "' + d + '" to "' + n +
                      '", directory already exists.')
    else:
        logging.info('Renaming "' + d + '" to "' + n + '".')
        try:
            os.rename(old, new)
            _offline_notice_renamed(d, n)
        except OSError:
            logging.error('There was an error renaming "' + d + '" to "' + n
                          + '".')
        else:
            # Save original directory name, but only if there is not yet an
            # .original file.
            if not _has_original_file(b, n):
                _set_original_file(b, n, d)


def _mkdir_and_move(b, f):
    n, e = _split_filename(f)
    if basicConfig['askmode'] and not _confirm(
            prompt='Do you want to move the file "' + f +
            '" to the directory "' + n + '"? ',
            resp=True):
        return ""

    # Create the directory
    d = os.path.join(b, n)
    logging.debug('Creating directory "' + d + '".')
    os.mkdir(d)

    # Update permissions if set
    if basicConfig['dirperm'] is not None:
        _change_permissions(d, basicConfig['dirperm'])

    # Move the file. We are doing this using a system command, since there is
    # no good 'move' interface in python. (We cannot use shutils.move, since
    # this would first copy the source to the destination and then delete the
    # source, which takes a long time with movie files.)
    logging.debug('Moving "' + f + '" to "' + n + '".')
    r = os.system('mv "' + os.path.join(b, f) + '" "' + d + '"')

    # Check OS return code.
    if r == 0:
        return n
    else:
        logging.error("Could not create directory \"" + d + "\".")
        return ""


def _get_correct_name(b, d):
    """Returns the correct name for the directory ``d``."""

    logging.debug('Called _get_correct_name("' + b + '", "' + d + '").')

    # This method determines the movie name as follows.
    # - If no .name file exists or if we are in force mode, we look up the
    #   movie using _get_movie_for_directory().
    # - Otherwise, we are not in force mode and a .name file exists, so we can
    #   take the name from that file.
    # If _get_movie_for_directory() returns an empty string, it means that no
    # movie could be determined for this directory, so we mark it as ignored in
    # future (unless we are in offline mode, in which case we need to add it to
    # the list of notifications).
    # Otherwise, we set the .name file with the returned name.

    if (not _has_name_file(b, d)) or basicConfig['forcemode']:
        if _has_name_file(b, d):
            logging.debug('Looking up "' + d +
                          '" because force mode is enabled.')
        else:
            logging.debug('No name file found for "' + d + '", looking up.')

        n = _get_movie_for_directory(b, d)

        # We need to add "Unrated", etc. if present in the original title.
        if not n == "":
            n = _add_title_attributes(d, n)
    else:
        logging.debug('Using name from file for "' + d + '".')
        n = _name_from_file(b, d)

    # Write the name to the file if it is not empty.
    if not n == "":
        _set_name_file(b, d, n)

    # Finally we return the name.
    return n


def _get_movie_for_directory(b, d):
        if not basicConfig['forcemode'] and _has_imdb_file(b, d):
            logging.debug('Found .imdb file for "' + d + '".')
            # We look up the movie on imdb according to its ID.  Because there
            # is an .imdb file but no .name file, it is reasonable to assume
            # that the script was already run once and the user chose not to
            # give a custom name.
            m = _movie_by_id(_id_from_file(b, d))
            n = m.nice_title()
        else:
            logging.debug('Looking up "' + d +
                          '" on IMDb with the user\'s help.')
            # Ask user to establish movie and custom name.
            m, n = _movie_by_name(_clean_name(d))

        # If a corresponding IMDb movie was found, then we set the .imdb file
        # and the rating file.
        if m is not None:
            _set_imdb_file(b, d, m.id)
            _set_rating_file(b, d, m.rating)

        return n


def _add_title_attributes(d, s):
        # If the name is not empty, we check if the original directory name
        # contained the words "unrated" or "director's cut" and if so then we
        # add the respective word to the title.
        unrated = (re.search(r"unrated", d, re.I) is not None)
        dircut = (re.search(r"director.?s.?cut", d, re.I) is not None)
        telesync = (re.search(r"telesync", d, re.I) is not None)
        remastered = (re.search(r"remastered", d, re.I) is not None)

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


def _movie_by_id(id):
    """Returns a Movie object corresponding to the IMDb id ``id``."""

    if not basicConfig['offlinemode']:
        print "Getting extended movie information..."
    else:
        logging.debug('Getting extended movie information for id ' +
                      id + '...')

    return tmdbapi.api_get_movie(id)


def _movie_by_name(s):

    m = _imdb_search_movie(s)

    # We give the user the opportunity to add a custom title, but not in
    # offline mode.
    if not basicConfig['offlinemode']:
        n = _ask_custom_title(m)
    else:
        n = ""

    # If the user hasn't chosen a custom title but m is a valid movie object,
    # we take the name from it.
    if n == "" and m is not None:
        n = m.nice_title()

    # Before we return the movie, we fetch it again using _movie_by_id() in
    # order to get the extended information such as the rating, unless speedy
    # mode is actived.
    if m is not None:
        return _movie_by_id(m.id), n
    else:
        return m, n


def _imdb_search_movie(s):

    if basicConfig['offlinemode']:
        return _imdb_search_movie_offline(s)
    else:
        return _imdb_search_movie_interactive(s)


def _imdb_search_movie_offline(s):
    results = _imdb_query(s)
    if len(results) == 0:
        logging.debug('Offline mode: No match found on IMDb for "' + s + '".')
        return None
    else:
        m = results[0]
        logging.debug('Returning IMDb match "' + m.nice_title() +
                      '" for query "' + s + '".')
        return m


def _imdb_search_movie_interactive(s):
    results = _imdb_query(s)
    print "Searching for movie '%s'" % s
    _print_movie_list(s, results)

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
                results = _imdb_query(a)
                _print_movie_list(a, results)
                continue
            elif n < 1 or n > len(results):
                print "Invalid number."
                continue

            m = results[n-1]
            sys.stdout.write('You selected "' + m.nice_title() +
                             '". Is this correct? ')

            if _confirm(prompt="", resp=True):
                break
            else:
                continue

        else:
            # Do a new search.
            results = _imdb_query(a)
            _print_movie_list(a, results)
            continue

    return m


def _ask_custom_title(m):
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
            if _confirm(prompt="", resp=True):
                break
        else:
            # Name is empty.
            if m is None:
                sys.stdout.write('You have chosen to ignore this directory. ' +
                                 'Please confirm ')

                if _confirm(prompt="", resp=True):
                    break
            else:
                # No confirmation needed here.
                break

    return n


def _imdb2movie(imdb_m):
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


def _is_movie_file(f):
    # Simple check based on extension
    movieext = ['avi', 'mpg', 'mp4', 'mpeg', 'divx', 'mov', 'mkv', 'm4v']
    for e in movieext:
        if _has_extension(f, e):
            return True

    return False


def _has_extension(f, e):
    return _get_extension(f).lower() == e.lower()


def _get_extension(f):
    n, e = _split_filename(f)
    return e


def _split_filename(f):
    m = re.match(r"(.*)\.([\w]{1,3})", f)
    if m is None:
        return f, ""
    else:
        return m.group(1), m.group(2)


def _mark_ignored(b, d):
    logging.debug('Marking directory "' + d + '" as ignored.')
    _touch_file(os.path.join(b, d, '.ignore'))


def _is_ignored(b, f):
    # By default, we ignore directories that start with a dot or a colon.
    if re.match(r"^(\.|:).*", f):
        return True

    # Otherwise, a directory is ignored if it contains an .ignore file.
    return _is_directory(os.path.join(b, f)) and _has_file(b, f, '.ignore')


def _has_name_file(b, d):
    return _has_file(b, d, '.name')


def _has_imdb_file(b, d):
    return _has_file(b, d, '.imdb')


def _has_rating_file(b, d):
    return _has_file(b, d, '.rating')


def _has_original_file(b, d):
    return _has_file(b, d, '.original')


def _has_file(b, d, n):
    logging.debug('Checking existence of file "' +
                  os.path.join(b, d, n) + '".')
    return os.path.exists(os.path.join(b, d, n))


def _name_from_file(b, d):
    return _text_from_file(b, d, '.name')


def _id_from_file(b, d):
    return re.sub('^tt', '', _text_from_file(b, d, '.imdb'))


def _rating_from_file(b, d):
    return _text_from_file(b, d, '.rating')


def _original_from_file(b, d):
    return _text_from_file(b, d, '.original')


def _text_from_file(b, d, f):
    fullpath = os.path.join(b, d, f)
    logging.debug('Reading text from file "' + fullpath + '".')
    assert(os.path.exists(fullpath))
    fh = open(fullpath, 'r')
    s = fh.readline().rstrip('\n')
    fh.close()
    return s


def _set_name_file(b, d, n):
    _set_file(b, d, '.name', n)


def _set_imdb_file(b, d, i):
    _set_file(b, d, '.imdb', "tt" + i)


def _set_rating_file(b, d, r):
    _set_file(b, d, '.rating', r)


def _set_original_file(b, d, s):
    _set_file(b, d, '.original', s)


def _set_file(b, d, f, s):
    fullpath = os.path.join(b, d, f)
    logging.debug('Writing text "' + s + '" to file "' + fullpath + '".')
    try:
        fh = open(fullpath, 'w')
        fh.write(s + '\n')
        fh.close()
    except IOError:
        logging.error('Error: Could not write to file "' + fullpath + '".')
    else:
        if basicConfig['fileperm'] is not None:
            _change_permissions(fullpath, basicConfig['fileperm'])


def _remove_ignore_file(b, d):
    _remove_file(b, d, ".ignore")


def _remove_imdb_file(b, d):
    _remove_file(b, d, ".imdb")


def _remove_name_file(b, d):
    _remove_file(b, d, ".name")


def _remove_rating_file(b, d):
    _remove_file(b, d, ".rating")


def _remove_file(b, d, n):
    os.remove(os.path.join(b, d, n))


def _touch_file(f):
    try:
        fh = open(f, 'w')
        fh.close()
    except IOError:
        logging.error('Error: Could not write to file "' + f + '".')
    else:
        if basicConfig['fileperm'] is not None:
            _change_permissions(f, basicConfig['fileperm'])


def _change_permissions(p, perm):
    try:
        os.chmod(p, perm)
    except OSError:
        logging.error('Unable to change permissions of "' + p + '".')


def _print_movie_list(q, l):
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
                logging.error('There was an Unicode problem')

        print "%2d: %s" % (c, t)


def _imdb_query(n):

    in_encoding = sys.stdin.encoding or "UTF-8"
    out_encoding = sys.stdout.encoding or "UTF-8"

    logging.debug("in_encoding = %s." % in_encoding)
    logging.debug("out_encoding = %s." % out_encoding)

    if n.isdigit():
        id = int(n)
        r = []
        m = tmdbapi.api_get_movie(id)
        if m:
            r.append(m)
    else:
        title = unicode(n, in_encoding, 'replace')
        r = tmdbapi.api_search_movie(title)

    logging.debug("Found %d possible movies." % len(r))

    # If there is a movie in r whose name is exactly n, then we move it to the
    # top of the list.
    r = _move_to_top_if_exists(r, n)

    return r


def _move_to_top_if_exists(r, n):
    c = 0
    for m in r:
        if c > 0 and m.nice_title() == n:
            mm = r.pop(c)
            r.insert(0, mm)
            logging.debug('Found "' + n + '" in the list, moving to top.')
            break
        c += 1

    return r


def _clean_name(s):

    logging.debug('Determining clean name for "' + s + '"')
    info = PTN.parse(s)
    title = info['title']
    logging.debug('Clean name is "' + title + '"')

    return title


def _offline_notice_unknown(s):
    global notifications_unknown
    notifications_unknown.append(s)


def _offline_notice_renamed(a, b):
    global notifications_rename
    notifications_rename.append([a, b])


def print_offline_notifications():
    global notifications_rename, notifications_unknown

    # If nothing has been renamed and quiet mode is enabled, just return.
    if len(notifications_rename) == 0 and basicConfig['quietmode']:
            return

    # Width of screen in characters
    w = 80

    # Separator
    sep = " -> "

    if len(notifications_rename) > 0:
        print_banner("Renamed directories", w)
        for p in notifications_rename:
            (a, b) = p
            print(_limit_string(a, w) + "\n" + sep +
                  _limit_string(b, w - len(sep)))

        print
        print str(len(notifications_rename)) + " directories renamed."
    else:
        print "No directories renamed."

    if len(notifications_unknown) > 0:
        print_banner("Directories without match", w)
        for d in notifications_unknown:
            print _limit_string(d, w)

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


def _limit_string(s, l):
    if len(s) <= l:
        return s + " " * (l - len(s))
    else:
        return s[0:l - 3] + "..."


def _is_directory(d):
    return os.path.exists(d) and os.path.isdir(d)


def _confirm(prompt=None, resp=False):
        """prompts for yes or no response from the user. Returns True for yes and
        False for no.

        'resp' should be set to the default value assumed by the caller when
        user simply types ENTER.

        >>> _confirm(prompt='Create Directory?', resp=True)
        Create Directory? [y]|n:
        True
        >>> _confirm(prompt='Create Directory?', resp=False)
        Create Directory? [n]|y:
        False
        >>> _confirm(prompt='Create Directory?', resp=False)
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
        if self.kind == 'tv series' and basicConfig['tvlabel']:
            t = t + " (TV Series)"

        return t
