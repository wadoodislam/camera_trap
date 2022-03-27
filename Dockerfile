FROM nvcr.io/nvidia/l4t-base:r32.4.3

WORKDIR /src/

ARG MODE
ENV MODE $MODE

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

ENV DEBIAN_FRONTEND noninteractive

COPY . .
#COPY requirements.txt requirements.txt


