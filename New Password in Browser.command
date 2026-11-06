#!/bin/sh
# New Password in Browser.command - opens the browser version from this folder.
# No server and no network. See web/README.md.
exec open "$(dirname "$0")/web/index.html"
