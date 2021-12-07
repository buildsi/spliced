#!/bin/bash

set -e

echo $PWD
ls 

if [ ! -d "${INPUT_ARTIFACTS}" ]; then
    printf "${INPUT_ARTIFACTS} does not exist\n"
    exit
fi

# If we don't have the docs directory yet, copy it there
if [ ! -d "${INPUT_DOCS}" ]; then
    printf "Output directory ${INPUT_DOCS} does not exist yet, copying...\n"
    cp -R ${ACTION_PATH}/docs ${INPUT_DOCS}
fi

if [ -z ${INPUT_EXPERIMENT+x} ]; then 
    for dirname in $(ls ${INPUT_ARTIFACTS}); do
        printf "python visualize-predictions.py artifacts/$dirname\n"
        python ${ACTION_PATH}/scripts/visualize-predictions.py artifacts/$dirname
    done   
else 

    # Make sure experiment directory exists first
    dirname=${INPUT_ARTIFACTS}/${INPUT_EXPERIMENT}
    if [ ! -d "{dirname}" ]; then
        printf "${dirname}d does not exist\n"
        exit
    fi

    printf "python visualize-predictions.py ${INPUT_ARTIFACTS}/${INPUT_EXPERIMENT}\n"
    python ${ACTION_PATH}/scripts/visualize-predictions.py ${INPUT_ARTIFACTS}/${INPUT_EXPERIMENT}
fi
