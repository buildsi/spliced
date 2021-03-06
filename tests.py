#!/usr/bin/python


# from deepdiff import DeepDiff

import spliced.utils as utils
import spliced.predict.smeagle as smeagle
import argparse
import sys
import os

import pytest
import json
import shutil
import sys
import os
import io

here = os.path.abspath(os.path.dirname(__file__))

args = [x for x in sys.argv if not x.startswith("-")]
if len(args) > 2:
    examples_dir = os.path.abspath(args[-1])
else:
    examples_dir = os.path.join(here, "examples", "smeagle")
sys.path.insert(0, here)

# Load all examples
tests = []

skips = ["Makefile", "README.md", "build.sh"]

# Add remainder
for name in os.listdir(examples_dir):
    if name in skips:
        continue
    if (
        not name.startswith("_")
        and not name.startswith(".")
        and not name.endswith(".md")
    ):
        tests.append((name, "facts.json"))


def write_file(data, filename):
    with open(filename, "w") as fd:
        fd.write(data)


def read_json(filename):
    with open(filename, "r") as fd:
        content = json.loads(fd.read())
    return content


def read_file(filename):
    with open(filename, "r") as fd:
        content = fd.read()
    return content


def check_facts(asp, asp_file):
    expected = read_file(asp_file)
    assert asp == expected


@pytest.mark.parametrize("name,facts", tests)
def test_examples(tmp_path, name, facts):

    # Smeagle runner can run smeagle or print facts
    cli = smeagle.SmeagleRunner()
    facts_file = os.path.join(examples_dir, name, facts)
    if not os.path.exists(facts_file):
        return
    data = utils.read_json(facts_file)

    # Write facts to string to compare to
    out = io.StringIO()
    print(facts_file)
    cli.generate_facts(data=data, out=out, lib_basename=True)
    atoms = out.getvalue()
    out.close()
    print(atoms)

    # Do we have a facts file to validate?
    asp_file = os.path.join(examples_dir, name, "atoms.asp")
    truth = os.path.join(examples_dir, name, "atoms.truth.asp")
    if not os.path.exists(truth):
        truth = asp_file

    # Check facts (nodes and relations)
    if os.path.exists(truth):
        check_facts(atoms, truth)
    write_file(atoms, asp_file)
