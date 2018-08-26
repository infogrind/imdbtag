#!/usr/bin/python

import sys
import os
import ConfigParser
from movie import Movie

verbose = False
configfile = '~/.imdbtagrc'

try:
    import tmdb.tmdb as tmdb
except ImportError:
    sys.stderr.write("You bad boy! You need to install the tmdb package!\n")
    sys.stderr.write("See github.com/doganaydin/themoviedb\n")
    sys.exit(1)

try:
    config = ConfigParser.ConfigParser()
    config.read(os.path.expanduser(configfile))
    api_key = config.get('general', 'api_key')
    tmdb.configure(api_key)
except ConfigParser.NoSectionError:
    sys.stderr.write("No section [general] found in config file " + configfile +
            "\n")
    sys.exit(1)
except ConfigParser.NoOptionError:
    sys.stderr.write("No api_key property found in config file %s\n" % configfile)
    sys.exit(1)

def _selftest():
    global verbose
    verbose = True
    print("Running some tests")
    print("Getting movie \"Fight Club\" by ID")
    movie = api_get_movie(550)
    print("Movie info from tmdb: '" + movie.nice_title() + "'")
    
    print("Querying by string")
    results = api_search_movie("fight club")
    if len(results) == 0:
        print("No results found")
    else:
        print("Results found:")
        i = 0
        for m in results:
            print("Result %d: %s" % (i, m.nice_title()))
            i = i + 1

def api_get_movie(id):
    tmdb_m = tmdb.Movie(id)
    return _tmdb2movie(tmdb_m)

def api_search_movie(querystr_enc):
    # Convert to ascii, because of a bug in urlllib (can't search for unicode)
    querystr = querystr_enc.encode('ascii', 'ignore')

    r = []
    movies = tmdb.Movies(querystr, True) # True means only get first page results
    for m in movies.iter_results():
        r.append(_tmdbhash2movie(m))
    return r

# TODO marius/2012-12-29: Refactor the two 2movie functions

def _tmdb2movie(tmdb_m):
  """Converts a movie object of the tmdb package into our own movie class."""
  out_encoding = sys.stdout.encoding or "UTF-8"
  
  # TMDb has no "index" field
  idx = ""

  return Movie(
      tmdb_m.get_original_title().encode(out_encoding, 'replace'),
      tmdb_m.get_release_date() and tmdb_m.get_release_date()[0:4] or '',
      idx,
      str(tmdb_m.get_id()),
      '',  # no "kind" field in tmdb
      tmdb_m.get_vote_average() and str(tmdb_m.get_vote_average()) or ''
      )

def _tmdbhash2movie(m):
  """Converts a movie hash object of the tmdb package into our own movie class."""
  out_encoding = sys.stdout.encoding or "UTF-8"
  
  # TMDb has no "index" field
  idx = ""

  return Movie(
      m['original_title'].encode(out_encoding, 'replace'),
      # Only keep first 4 digits of release date
      m['release_date'] and m['release_date'][0:4] or '',
      idx,
      str(m['id']),
      '',  # no "kind" field in tmdb
      m['vote_average'] and str(m['vote_average']) or ''
      )

def _debug(s):
  if verbose:
    sys.stderr.write("DEBUG: " + s + "\n")


if __name__ == "__main__":
    print("Import this module from your script.")
    _selftest()
