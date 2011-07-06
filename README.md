# Introduction
The Google Reader search index only contains recently-tagged items, where "recently" means roughly "within the past year" and "tagged" means any tag (read, starred, shared, or user-provided). This script touches all of an account's starred, shared, liked, noted and read items so that they can show up in the index. Note that it may take a while to run, especially if you have a lot of read items.

# Usage

    $ python google-reader-touch.py

You will be prompted for your Google Account credentials ([ClientLogin](http://code.google.com/p/google-reader-api/wiki/Authentication) is used for authentication, your password is not persistent anywhere).

# TODO

* Mode to clean up touch tags
