import os
import shutil
import time
from datetime import datetime
from uuid import uuid4

import Jetson.GPIO as GPIO
import cv2

from utils import gstreamer_pipeline, current_milli_time, motion_detection, Constants, is_day_light


class Node(Constants):
    event_id = None
    pir_pin = 7
    infrared = 12
    led_pin = 23
    gnd_pin = 24
    red_pin = 16
    green_pin = 22
    yellow_pin = 18

    def setup_sensors(self):
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(self.pir_pin, GPIO.IN)
        GPIO.setup(self.infrared, GPIO.OUT)
        GPIO.setup(self.led_pin, GPIO.OUT)
        GPIO.setup(self.gnd_pin, GPIO.OUT)
        GPIO.setup(self.red_pin, GPIO.OUT)
        GPIO.setup(self.yellow_pin, GPIO.OUT)
        GPIO.setup(self.green_pin, GPIO.OUT)
        self.night_vision(on=False)

    @property
    def should_capture(self):
        if not self.ME['live']:
            return False
        return True

    def detect_motion(self):
        print("started motion detect")

        while GPIO.input(7) == 0:
            if self.should_update:
                self.update()
            time.sleep(0.5)

        print("motion detected")

    def capture(self):

        cap = cv2.VideoCapture(gstreamer_pipeline(flip_method=2), cv2.CAP_GSTREAMER)

        if cap.isOpened():
            if not is_day_light():
                self.night_vision(on=True)

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
            self.night_vision(on=False)
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

        if is_day_light():
            return motion_detection(images, movement_threshold=self.day_threshold)

        return motion_detection(images, movement_threshold=self.night_threshold)

    def move_event(self, to_dir):
        event_path = os.path.join(self.events_dir, self.event_id)
        shutil.move(event_path, to_dir)

    def night_vision(self, on):
        if on:
            GPIO.output(self.infrared, GPIO.HIGH)
            GPIO.output(self.led_pin, GPIO.LOW)
            GPIO.output(self.gnd_pin, GPIO.HIGH)
        else:
            GPIO.output(self.infrared, GPIO.LOW)
            GPIO.output(self.led_pin, GPIO.HIGH)
            GPIO.output(self.gnd_pin, GPIO.LOW)

    def green_on(self):
        GPIO.output(self.green_pin, GPIO.HIGH)

    def yellow_on(self):
        GPIO.output(self.yellow_pin, GPIO.HIGH)

    def red_on(self):
        GPIO.output(self.red_pin, GPIO.HIGH)

    def green_off(self):
        GPIO.output(self.green_pin, GPIO.LOW)

    def yellow_off(self):
        GPIO.output(self.yellow_pin, GPIO.LOW)

    def red_off(self):
        GPIO.output(self.red_pin, GPIO.LOW)


if __name__ == "__main__":
    Node().run()
