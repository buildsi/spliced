#!/usr/bin/env python

# A simple wrapper to smeagle fact generation

import spliced.utils as utils
import spliced.predict.smeagle as smeagle
import argparse
import sys
import os


def get_parser():
    parser = argparse.ArgumentParser(
        description="Smeagle Fact Generation",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument("jsonfile", help="json file with Smeagle facts")
    return parser


def main():

    p = get_parser()
    args, extra = p.parse_known_args()

    if not args.jsonfile or not os.path.exists(args.jsonfile):
        sys.exit(f"{args.jsonfile} does not exist.")

    # Smeagle runner can run smeagle or print facts
    cli = smeagle.SmeagleRunner()
    data = utils.read_json(args.jsonfile)

    # We can accept a path (will run smeagle) or the raw data, so
    # it is important to provide a kwarg here!
    cli.generate_facts(data=data)


if __name__ == "__main__":
    main()
