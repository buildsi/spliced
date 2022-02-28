# Copyright 2013-2021 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

## Spliced config schema

schema_url = "https://json-schema.org/draft-07/schema/#"

properties = {
    "splice": {"type": "string"},
    "splice_versions": {"type": "array", "items": {"type": "string"}},
    "package": {"type": "string"},
    "replace": {"type": ["string", "null"]},
    "command": {"type": ["string", "null"]},
}

spliced_schema = {
    "$schema": schema_url,
    "title": "Spliced Schema",
    "type": "object",
    "required": [
        "package",
        "splice",
    ],
    "properties": properties,
    "additionalProperties": False,
}

# The simplest form of aliases is key/value pairs
predictions = {
    "type": "object",
    "patternProperties": {
        "\\w[\\w-]*": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["binary", "prediction"],
                "properties": {
                    "binary": {"type": "string"},
                    "lib": {"type": "string"},
                    "prediction": {"type": "boolean"},
                    "return_code": {"type": "number"},
                    "message": {"type": "string"},
                },
                "additionalProperties": True,
            },
        },
    },
}


libs = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["paths", "dep"],
        "properties": {
            "paths": {"type": "array", "items": {"type": "string"}},
            "dep": {"type": "string"},
        },
    },
}

result_properties = {
    "type": "object",
    "required": [
        "experiment",
        "result",
        "success",
        "splice",
        "package",
        "binaries",
        "predictions",
        "libs",
    ],
    "properties": {
        "experiment": {"type": ["null", "string"]},
        "result": {"type": "string"},
        "success": {"type": "boolean"},
        "splice": {"type": "string"},
        "package": {"type": "string"},
        "binaries": {
            "type": "object",
            "properties": {
                "original": {"type": "array", "items": {"type": "string"}},
                "spliced": {"type": "array", "items": {"type": "string"}},
            },
        },
        "predictions": predictions,
        "libs": {
            "type": "object",
            "properties": {
                "original": libs,
                "spliced": libs,
                # If a splice fails, we still provide libs here
                "dep": libs,
                "replace": libs,
            },
            "spliced": {"type": "array", "items": {"type": "string"}},
        },
    },
}

spliced_result_schema = {
    "$schema": schema_url,
    "title": "Spliced Result Schema",
    "type": "array",
    "items": result_properties,
    "additionalProperties": False,
}
