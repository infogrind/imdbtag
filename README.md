# imdbtag

A script to name movie files according to imdb (or other DB) results

## Usage

    imdbscript [options] <directory|file> [, <directory|file>, ...]
    imdbscript [options] -d <directory>
    
    The first version renames the files and directories given on the command line.
    The second version renames all files and directories in the directory specified
    with -d. 
    
    Options: -h    Display help text.
             -i    Always ask for confirmation
             -f    Force mode: Ignore existing .name and .imdb files.
             -o    Offline mode: Runs without user interaction and displays a
                   summary at the end. Ideal for cron jobs.
             -c    Clear mode: Remove all tagging information (all .imdb, .rating,
                   .name, .ignore files).
             -q    Quiet mode: Do not display any progress information. (This
                   makes mostly sense in offline mode.)
             -s    Print a summary at the end of the processing.
             -t    Add string " (TV Series)" to directory name for series.
             -r    Recovery mode: Re-process previously renamed directories to
                   correct them.
             -v    Verbose output (for debugging)
             -F <perm>
                   Explicitly specify file permissions. <perm> is the mode that all
                   created files should have, in octal base. E.g., -F 664
             -D <perm>
                   Explicitly specify directory permissions. This works like -F but
                   applies to created directories. E.g., -D 775


## Requirements

- [themoviedb](github.com/doganaydin/themoviedb) (though it seems no longer
  available on GitHub)
- [parse-torrent-name](https://github.com/divijbindlish/parse-torrent-name)
