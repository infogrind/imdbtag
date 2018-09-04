# imdbtag

A script to name movie files according to imdb (or other DB) results

## Installation

### Homebrew

Due to lack of popularity :'( the script is not available in Homebrew's default
tap. Here's how to get it from the author's personal tap:

```sh
$ brew tap infogrind/tap
$ brew install imdbtag
```

### Manual

First clone the repository.

```sh
$ git clone https://github.com/infogrind/imdbtag.git && cd imdbtag
```

And run the command for installing the package.

```sh
$ python setup.py install
```

(You might have to run this as root, due to the required permissions.)

## Usage

    imdbtag [options] <directory|file> [, <directory|file>, ...]
    imdbtag [options] -d <directory>
    
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


## Running Locally

To run the tool locally, e.g. for development, use `pipenv` (see e.g. [this
page](https://docs.python-guide.org/dev/virtualenvs/) for usage instructions).
Run it as follows:

```sh
pipenv run python setup.py install
pipenv run imdbtag
```

This will use `pipenv` to install a virtualenv, normally under `~/.local/share`.
The first time you run it, it will take a bit longer because all the
dependencies have to be installed.


## Testing

### End-to-end Test

Run the `teste2e` script:

```sh
./teste2e
```

For the same reason as described under *Running Locally* above, this may take a
bit longer the first time it is run.

Requirements:

* `mktemp` (should be included in standard Unix-like distributions, including
  Mac OS)
* `pipenv` (install it e.g. using `pip`)

### Quick API Self-Test

To verify that the API works properly, perform the following steps within a
Python shell (this requires the script with all dependencies to be properly
installed):

    import imdbtag.apis.tmdbapi
    imdbtag.apis.tmdbapi._selftest()
