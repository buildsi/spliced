#!/bin/bash

set -e

echo $PWD
ls 

if [ ! -f "${INPUT_YAML}" ]; then
    printf "${INPUT_YAML} does not exist\n"
    exit
fi

COMMAND="spliced matrix ${INPUT_YAML}"

if [ ! -z "${INPUT_CONTAINER}" ]; then
    COMMAND="${COMMAND} --container ${INPUT_CONTAINER}"
fi

printf "${COMMAND}\n"
${COMMAND}
echo $?
