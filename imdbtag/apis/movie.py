#!/usr/bin/python

import re

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



# This is the most important line: it calls the main function if this program is
# called directly.
if __name__ == "__main__":
    print("Movie class, import this file from your scripts")


