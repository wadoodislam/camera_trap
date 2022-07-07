FROM nvcr.io/nvidia/l4t-base:r32.4.3

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

#ENV OPENBLAS_CORETYPE ARMV8
gst-launch-1.0 nvarguscamerasrc ! 'video/x-raw(memory:NVMM), width=(int)1280, height=(int)720, framerate=(fraction)30/1' ! nvvidconv flip-method=0 ! 'video/x-raw, width=(int)960, height=(int)540, format=(string)BGRx'

WORKDIR /src/

RUN apt-get upgrade && apt-get update
RUN apt-get install -y python3-pip

RUN python3 -m pip install --upgrade pip

COPY ../requirements.txt requirements.txt

RUN pip3 install -r requirements.txt
