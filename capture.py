import json
import os
import shutil
import time
from datetime import datetime, timedelta
from uuid import uuid4

import Jetson.GPIO as GPIO
import cv2
import requests

from utils import gstreamer_pipeline, current_milli_time, motion_detection, Constants, dt_parse

pir_pin = 7
infrared = 13


class Node(Constants):
    url = os.environ['SITE'] + '/core/api/camera/me/'
    event_id = None
    ME = None

    def __init__(self):
        Constants.__init__(self)
        self.update()

    @staticmethod
    def setup_sensors():
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(pir_pin, GPIO.IN)
        GPIO.setup(infrared, GPIO.OUT)
        GPIO.output(infrared, GPIO.HIGH)

    @property
    def should_capture(self):
        if not self.ME['live']:
            return False

        # if time not in slots:
        #  return False
        return True

    @property
    def should_update(self):
        if datetime.now() < self.last_reported_at + timedelta(seconds=self.update_after):
            return False
        return True

    @property
    def video_interval(self):
        return self.ME['video_interval']

    @property
    def day_threshold(self):
        return self.ME['day_threshold']

    @property
    def night_threshold(self):
        return self.ME['night_threshold']

    @property
    def update_after(self):
        return self.ME['update_after']

    @property
    def last_reported_at(self):
        return dt_parse(str(self.ME['last_reported_at']))

    @property
    def frames_per_sec(self):
        return self.ME['frames_per_sec']

    def update(self):
        # hdd = psutil.disk_usage('/')
        payload = {
            "remaining_storage": 100
        }
        response = requests.request("PATCH", self.url, headers=self.headers, data=json.dumps(payload))
        self.ME = json.loads(response.text)

    def detect_motion(self):
        print("started motion detect")

        while GPIO.input(7) == 0:
            if self.should_update:
                self.update()
            time.sleep(0.5)  # why is this line here. Do we need to make it wait?

        print("motion detected")

    def capture(self):
        GPIO.output(infrared, GPIO.LOW)
        cap = cv2.VideoCapture(gstreamer_pipeline(flip_method=2), cv2.CAP_GSTREAMER)

        if cap.isOpened():
            self.event_id = uuid4().hex

            if not os.path.exists(self.events_dir + self.event_id):
                os.makedirs(self.events_dir + self.event_id)

            print("Starting capture at: " + datetime.now().strftime('%H:%M:%S'))

            for skip in range(35):  # to discard over exposure frames
                _ = cap.read()

            for sec in range(self.video_interval):  # change for number of pictures
                ret_val, frame = cap.read()
                cv2.imwrite(self.events_dir + self.event_id + '/' + str(current_milli_time()) + '.jpg', frame)

                for skip in range(self.frames_per_sec - 1):
                    _ = cap.read()

            print("Done capturing at: " + datetime.now().strftime('%H:%M:%S'))
            cap.release()
            GPIO.output(infrared, GPIO.HIGH)
        else:
            print("Unable to open camera")

    def run(self):
        while True:
            self.setup_sensors()
            self.detect_motion()

            if self.should_capture:
                self.capture()

            GPIO.cleanup()
            self.move_event(self.upload_dir if self.validate_event() else self.false_dir)

    def validate_event(self):
        event_path = os.path.join(self.events_dir, self.event_id)
        images = sorted([os.path.join(event_path, img) for img in os.listdir(event_path)])

        if True:  # check if the its' day light.
            return motion_detection(images, movement_threshold=self.day_threshold)

        return motion_detection(images, movement_threshold=self.night_threshold)

    def move_event(self, to_dir):
        event_path = os.path.join(self.events_dir, self.event_id)
        shutil.move(event_path, to_dir)


if __name__ == "__main__":
    Node().run()
