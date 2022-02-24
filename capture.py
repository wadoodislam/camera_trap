import os
import shutil
import time
from datetime import datetime
from uuid import uuid4

import Jetson.GPIO as GPIO
import cv2

from utils import gstreamer_pipeline, current_milli_time, Constants, ImageOperations


class Node(Constants):
    event_id = None
    pir_pin = 7
    infrared = 12
    led_pin = 24
    gnd_pin = 23
    red_pin = 16
    green_pin = 22
    yellow_pin = 18

    def setup_sensors(self):
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(self.pir_pin, GPIO.IN)
        GPIO.setup(self.infrared, GPIO.OUT)
        GPIO.setup(self.led_pin, GPIO.OUT)
        GPIO.setup(self.gnd_pin, GPIO.OUT)
        GPIO.setup(self.red_pin, GPIO.OUT)
        GPIO.setup(self.yellow_pin, GPIO.OUT)
        GPIO.setup(self.green_pin, GPIO.OUT)

    @property
    def should_capture(self):
        if not self.ME['live']:
            return False
        return True

    def run(self):
        self.setup_sensors()

        while True:
            self.detect_motion()
            self.night_vision(on=not self.is_sunlight())
            if self.should_capture:
                self.capture(2)  # just capture after every 1 or 2 seconds to see if something is happening - Hardcoded
                if self.validate_event():  # something is happening then do a full event capture
                    self.capture(self.video_interval, True)
                    self.move_event(self.upload_dir)
                else:
                    self.move_event(self.false_dir)  # we can eliminate the additional validation and save some power
            else:
                time.sleep(self.video_interval)

    def validate_event(self):
        event_path = os.path.join(self.events_dir, self.event_id)
        images = sorted([os.path.join(event_path, img) for img in os.listdir(event_path)])

        if self.is_sunlight():
            return self.motion_detection(images, movement_threshold=self.day_threshold)

        return self.motion_detection(images, movement_threshold=self.night_threshold)

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

    def detect_motion(self):
        start_time = time.time()

        while GPIO.input(7) == 0:
            time.sleep(0.5)
            if self.should_update:
                self.update()
            if time.time() - start_time >= 2:  # Ideally use self.capture_interval - Hardcoded
                break

    def capture(self, interval, continue_event=False):
        cam = cv2.VideoCapture(gstreamer_pipeline(flip_method=0), cv2.CAP_GSTREAMER)

        if cam.isOpened():
            if not continue_event:
                self.event_id = uuid4().hex
                if not os.path.exists(self.events_dir + self.event_id):
                    os.makedirs(self.events_dir + self.event_id)

            for skip in range(35):  # to discard over exposure frames
                _ = cam.read()

            for sec in range(interval):  # change for number of pictures
                ret_val, frame = cam.read()
                if not self.is_sunlight():
                    frame = ImageOperations.convert_image_to_gray(frame)

                cv2.imwrite(self.events_dir + self.event_id + '/' + str(current_milli_time()) + '.jpg', frame)

                for skip in range(self.frames_per_sec - 1):
                    _ = cam.read()

            cam.release()
        else:
            self.send_log("Unable to open camera: " + datetime.now().strftime('%H:%M:%S'))

    def motion_detection(self, image_paths, movement_threshold=1000):
        starting_index = 1
        first_frame = cv2.imread(image_paths[0])
        max_contours = []

        for image_index in range(starting_index, len(image_paths)):
            image_2 = cv2.imread(image_paths[image_index])
            diff = ImageOperations.error_image_gray_histmatch(first_frame, image_2)
            diff = ImageOperations.convert_to_binary(diff)
            diff = cv2.erode(diff, None, iterations=1)
            diff = cv2.dilate(diff, None, iterations=3)
            cnts, _ = cv2.findContours(diff.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            max_contour = max([cv2.contourArea(cnt) for cnt in cnts] or [0])
            max_contours.append(max_contour)

            if movement_threshold < max_contour:
                self.send_log('Event: {}, index: {}, max contour:{}'.format(self.event_id, image_index, max_contour))
                return True

        self.send_log('Event: {}, max contours:{}'.format(self.event_id, max_contours))
        return False

    def is_sunlight(self):
        now = datetime.now()
        return self.sunrise.time() < now.time() < self.sunset.time()


if __name__ == "__main__":
    Node().run()
