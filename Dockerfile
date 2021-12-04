FROM ghcr.io/buildsi/spliced-ubuntu-20.04:latest

WORKDIR /code
COPY . /code
RUN pip install -e .
ENTRYPOINT ["/code/docker/entrypoint.sh"]
