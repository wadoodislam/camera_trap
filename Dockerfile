FROM nvcr.io/nvidia/l4t-base:r32.4.3

WORKDIR /src/

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
RUN apt-get upgrade && apt-get update
RUN apt-get install python3-pip
COPY . .
#COPY requirements.txt requirements.txt


