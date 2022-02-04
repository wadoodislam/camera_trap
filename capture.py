import json
import os
import time
from datetime import datetime, timedelta
from uuid import uuid4
import requests
import Jetson.GPIO as GPIO
import cv2

from utils import gstreamer_pipeline, current_milli_time

pir_pin = 7
infrared = 13
GPIO.setmode(GPIO.BOARD)
GPIO.setup(pir_pin, GPIO.IN)
GPIO.setup(infrared, GPIO.OUT)
GPIO.output(infrared, GPIO.HIGH)


class Node:
    image_path = os.environ['HOME'] + '/images/'
    url = os.environ['SITE'] + '/core/api/camera/me/'
    ME = {
        "live": False,
        "description": "Lums Camera",
        "last_reported_at": datetime.now(),
        "action": None,
        "video_interval": 15,
        "frames_per_sec": 30,
        "update_after": 300.0,
        "slots": [],
    }

    def __init__(self, token):
        self.headers = {
            'Authorization': 'Token ' + token,
            'Content-Type': 'application/json'
        }

    @property
    def should_capture(self):
        if not self.ME['live']:
            return False

        # if time not in slots:
        #  return False
        return True

    @property
    def video_interval(self):
        return self.ME['video_interval']

    @property
    def update_after(self):
        return self.ME['update_after']

    @property
    def frames_per_sec(self):
        return self.ME['frames_per_sec']

    def update(self):
        if datetime.now() < self.ME['last_reported_at'] + timedelta(seconds=self.update_after):
            return

        payload = {
            "description": "Staging Lab Node"
        }
        response = requests.request("PATCH", self.url, headers=self.headers, data=json.dumps(payload))
        self.ME = json.loads(response.text)

    def detect_motion(self):
        print("started motion detect")

        while GPIO.input(7) == 0:
            self.update()
            time.sleep(0.5)

        print("motion detected")

    def capture(self):
        GPIO.output(infrared, GPIO.LOW)
        cap = cv2.VideoCapture(gstreamer_pipeline(flip_method=2), cv2.CAP_GSTREAMER)

        if cap.isOpened():
            event_id = uuid4().hex

            if not os.path.exists(self.image_path + event_id):
                os.makedirs(self.image_path + event_id)

            print("Starting capture")

            for skip in range(35):  # to discard over exposure frames
                _ = cap.read()

            for sec in range(self.video_interval):  # change for number of pictures
                ret_val, frame = cap.read()
                cv2.imwrite(self.image_path + event_id + '/' + str(current_milli_time()) + '.jpg', frame)

                for skip in range(self.frames_per_sec - 1):
                    _ = cap.read()

            print("done capturing")
            cap.release()
            GPIO.output(infrared, GPIO.HIGH)
        else:
            print("Unable to open camera")

    def run(self):
        while True:
            self.detect_motion()

            if self.should_capture:
                self.capture()

            GPIO.cleanup()


node = Node(token=os.environ['TOKEN'])


if __name__ == "__main__":
    print("Initializing")
    node.run()

