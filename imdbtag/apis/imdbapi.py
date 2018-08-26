#!/usr/bin/python

import sys
from movie import Movie

verbose = False

try:
    import imdb
except ImportError:
    sys.stderr.write("You bad boy! You need to install the IMDbPY package!\n")
    sys.exit(1)

# The IMDb object
i = imdb.IMDb()

def _selftest():
    global verbose
    verbose = True
    print("Running some tests")
    print("Getting movie \"Fight Club\" by ID")
    movie = api_get_movie(137523)
    print("Movie info from IMDb: '" + movie.nice_title() + "'")
    
    print("Querying by string")
    results = api_search_movie("fight club")
    if len(results) == 0:
        print("No results found")
    else:
        print("Results found:")
        i = 0
        for m in results:
            print("Result " + i + ": " + m.nice_title())
            i = i + 1

def api_get_movie(id):
    global i
    imdb_m = i.get_movie(id)
    _debug("found title: \"" + imdb_m['title'] + "\"")
    return _imdb2movie(imdb_m)

def api_search_movie(querystr):
    global i
    r = []
    results = i.search_movie(querystr)
    for m in results:
        r.append(_imdb2movie(m))
    return r

def _imdb2movie(imdb_m):
  """Converts a movie object of the IMDbpy package into our own movie class."""
  out_encoding = sys.stdout.encoding or "UTF-8"
  
  # We set the variable idx depending on whether the imdb_m object has a field
  # called 'imdbIndex'.
  if imdb_m.has_key('imdbIndex'):
    idx = imdb_m['imdbIndex'].encode(out_encoding, 'replace')
  else:
    idx = ""

  return Movie(
      imdb_m['title'].encode(out_encoding, 'replace'),
      imdb_m.has_key('year') and imdb_m['year'] or '',
      idx,
      imdb_m.movieID.encode(out_encoding, 'replace'),
      imdb_m['kind'].encode(out_encoding, 'replace'),
      imdb_m.has_key('rating') and str(imdb_m['rating']) or ''
      )

def _debug(s):
  if verbose:
    sys.stderr.write("DEBUG: " + s + "\n")


if __name__ == "__main__":
    print("Import this module from your script.")
    _selftest()
