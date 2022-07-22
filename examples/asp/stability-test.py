#!/usr/bin/env python

# A simple wrapper to smeagle fact generation

import spliced.utils as utils
import spliced.predict.smeagle as smeagle
import argparse
import sys
import os

here = os.path.abspath(os.path.dirname(__file__))


def get_parser():
    parser = argparse.ArgumentParser(
        description="Smeagle Fact Generation",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument("A", help="library A (original)")
    parser.add_argument("B", help="library B (to splice in)")
    return parser


def main():

    p = get_parser()
    args, extra = p.parse_known_args()

    for path in [args.A, args.B]:
        if not path or not os.path.exists(path):
            sys.exit(f"{path} does not exist.")

    # Smeagle runner can run smeagle or print facts
    cli = smeagle.SmeagleRunner()

    # Generate facts to look at
    ## IMPORTANT keep namespace to lowercase a and b
    with open(os.path.join(here, "A.asp"), "w") as fd:
        cli.generate_facts(lib=args.A, out=fd, namespace="a")
    with open(os.path.join(here, "B.asp"), "w") as fd:
        cli.generate_facts(lib=args.B, out=fd, namespace="b")
    res = cli.stability_test(args.A, args.B)


if __name__ == "__main__":
    main()
