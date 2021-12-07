#!/usr/bin/env python

# Usage:
# starting with a results file in your ~/.spack/analyzers/spack-monitor, run as follows:
# python visualize-predictions.py ~/.spack/spack-monitor/analysis/curl/symbolator-predictions.json
# Note the directory name is the package being spliced

import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt

import shutil
import pandas
import sys
import json
import os

# Also validate to ensure we have the right format
from spliced.schemas import spliced_result_schema

here = os.environ.get("GITHUB_WORKSPACE") or os.getcwd()


def write_json(obj, filename):
    with open(filename, "w") as fd:
        fd.write(json.dumps(obj, indent=4))


def read_json(filename):
    with open(filename, "r") as fd:
        content = json.loads(fd.read())
    return content


template = """---
title: Package %s Experiment %s results
categories: packages
tags: [package]
permalink: /results/%s/%s/
%s
maths: 1
toc: 1
---
"""


def plot_heatmap(df, save_to=None):
    sns.set_theme(style="white")

    f, ax = plt.subplots(figsize=(30, 30))

    # Generate a custom diverging colormap
    cmap = sns.color_palette()
    # cmap = sns.diverging_palette(230, 20, as_cmap=True)

    # Draw the heatmap with the mask and correct aspect ratio
    p = sns.clustermap(
        df, cmap=cmap, center=0, square=True, linewidths=0.5, cbar_kws={"shrink": 0.5}
    )
    # used for heatmap
    # p.tick_params(labelsize=5)
    # p.set_xlabel("Splice", fontsize=12)
    # p.set_ylabel("Binary", fontsize=12)

    if save_to:
        plt.savefig(save_to)
    return plt


def main(pkg_dir):
    if not os.path.exists(pkg_dir):
        sys.exit("Cannot find %s" % pkg_dir)

    # There are TWO levels of informatoin
    # 1. The top level package / splice "was it successful or not (and if not why)
    # 2. The second level specific results for a splice "is this predicted to work (or not)"
    # For now I'm going to try and visualize the top, and then present the next levels in a table

    # We will create rows / cols for each splice
    rows = set()  # package
    cols = set()  # splices
    testers = set()

    # Unique result types
    result_types = set()

    package = os.path.basename(pkg_dir)

    # assumes same command across
    commands = set()

    # Results will be a table of results for each predictor
    results = {}

    # Assemble experiments
    for pkg in os.listdir(os.path.abspath(pkg_dir)):

        # These are matrix entries
        # curl-7.53.1-splice-zlib-with-zlib-experiment-curl
        for experiment in os.listdir(os.path.join(pkg_dir, pkg)):
            for result_file in os.listdir(os.path.join(pkg_dir, pkg, experiment)):
                result_file = os.path.join(pkg_dir, pkg, experiment, result_file)
                data = read_json(result_file)
                try:
                    jsonschema.validate(data, schema=spliced_result_schema)
                except:
                    print(
                        "%s is not valid for the current result schema." % result_file
                    )
                    continue

                for datum in data:

                    # Top level results for the visualization go here
                    cols.add(datum.get("splice"))
                    rows.add(datum.get("package"))
                    result_types.add(datum.get("result"))

                    for tester, resultlist in datum["predictions"].items():
                        if not resultlist:
                            continue
                        testers.add(tester)
                        if tester not in results:
                            results[tester] = []

                        # We can't assume the testers have the exact same testing set (but they can)
                        for res in resultlist:

                            # We add binaries/libs that we have predictions for
                            results[tester].append(
                                {
                                    "binary": res.get("binary"),
                                    "lib": res.get("lib"),
                                    "prediction": res.get("prediction"),
                                    "message": res.get("message"),
                                    "return_code": res.get("return_code"),
                                    "command": res.get("command"),
                                    "splice": datum.get("splice"),
                                    "package": datum.get("package"),
                                    "result": datum.get("result"),
                                }
                            )

    print("Found %s testers: %s" % (len(testers), " ".join(testers)))

    # Create top level data frame
    df = pandas.DataFrame(0, index=rows, columns=cols)

    # Assign each outcome a number
    outcomes = {result_type: i + 1 for i, result_type in enumerate(result_types)}

    # Populate outcomes
    for pkg in os.listdir(os.path.abspath(pkg_dir)):

        for experiment in os.listdir(os.path.join(pkg_dir, pkg)):
            for result_file in os.listdir(os.path.join(pkg_dir, pkg, experiment)):
                result_file = os.path.join(pkg_dir, pkg, experiment, result_file)
                data = read_json(result_file)
                try:
                    jsonschema.validate(data, schema=spliced_result_schema)
                except:
                    continue

                for datum in data:

                    # Top level results for the visualization go here
                    colname = datum.get("splice")
                    rowname = datum.get("package")
                    outcome = outcomes[datum.get("result")]
                    df.loc[rowname, colname] = outcome

    # Save results to file under docs
    experiment = experiment.split("-")[0]
    result_dir = os.path.join(here, "docs", "_results", package, experiment)
    if not os.path.exists(result_dir):
        os.makedirs(result_dir)

    listing = ""

    # Save the json to file
    write_json(results, os.path.join(result_dir, "results-list.json"))
    df.to_json(os.path.join(result_dir, "results-table.json"))
    write_json(outcomes, os.path.join(result_dir, "outcomes.json"))

    # Plot basics
    save_to = os.path.join(result_dir, "%s-%s.pdf" % (experiment, package))
    fig = plot_heatmap(df, save_to)
    save_to = os.path.join(result_dir, "%s-%s.png" % (experiment, package))
    fig = plot_heatmap(df, save_to)
    save_to = os.path.join(result_dir, "%s-%s.svg" % (experiment, package))
    fig = plot_heatmap(df, save_to)

    # Save the filenames for images
    listing += "png: %s-%s.png\n" % (experiment, package)
    listing += "svg: %s-%s.svg\n" % (experiment, package)
    listing += "pdf: %s-%s.pdf\n" % (experiment, package)

    # And the entry for the results
    listing += "results: results-list.json\n"
    listing += "outcomes: %s\n" % outcomes

    # Generate a markdown for each
    content = template % (package, experiment, package, experiment, listing)
    md = os.path.join(result_dir, "index.md")
    with open(md, "w") as fd:
        fd.write(content)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(
            "Please provide the path to a package folder: python visualize-predictions.py artifacts/curl"
        )
    main(sys.argv[1])
