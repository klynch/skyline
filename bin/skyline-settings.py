#!/usr/bin/env python

import argparse
import json
import redis

DEFAULT_SETTINGS = [
    ("skyline:config:alerts:rules", []),
    ("skyline:config:alerts:settings", {}),
    ("skyline:config:blacklist", []),
    ("skyline:config:whitelist", []),
]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Seed data.')
    parser.add_argument("-r", "--redis", default="redis://localhost:6379/", help="Redis instance to connect to")
    parser.add_argument("-i", "--import-file", help="The settings file to import. If an entry is missing from the file, it is set to an emtpy value")
    args = parser.parse_args()

    #Connecting to Redis
    r = redis.StrictRedis.from_url(args.redis)

    #Importing settings
    if args.import_file:
        with open(args.import_file) as f:
            settings = json.load(f)

            for key, default in DEFAULT_SETTINGS:
                value = settings.get(key, default)
                r.set(key, json.dumps(value))

    #Exporting settings
    settings = {}
    for key, default in DEFAULT_SETTINGS:
        settings[key] = default
        value = r.get(key)
        if value is not None:
            settings[key] = json.loads(value)

    print json.dumps(settings, indent=2)
