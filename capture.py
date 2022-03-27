import os
import time
from datetime import datetime
from uuid import uuid4

import Jetson.GPIO as GPIO
import cv2

from utils import gstreamer_pipeline, current_milli_time, Constants, ImageOperations


class Node(Constants):
    event_id = None
    logs = []
    pir_pin = 7

    def setup_sensors(self):
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(self.infrared, GPIO.OUT)
        GPIO.setup(self.led_pin, GPIO.OUT)
        GPIO.setup(self.gnd_pin, GPIO.OUT)
        GPIO.setup(self.red_pin, GPIO.OUT)
        GPIO.setup(self.yellow_pin, GPIO.OUT)
        GPIO.setup(self.green_pin, GPIO.OUT)
        GPIO.setup(self.pir_pin, GPIO.IN)

    def run(self):
        self.setup_sensors()

        while True:

            if not self.should_capture:
                time.sleep(self.rest_interval)
                continue

            if not self.open_camera():
                self.send_log("Unable to open camera: " + datetime.now().strftime('%H:%M:%S'))
                time.sleep(self.rest_interval)
                continue

            self.event_id = uuid4().hex
            pir_val = GPIO.input(7)
            frames = self.capture(self.motion_interval)
            is_motion, contours = self.motion_detection(frames)

            if is_motion:
                frames += self.capture(self.video_interval)
                self.close_camera()
                self.make_event(frames, is_motion)
                self.logs.append((self.event_id, contours))
            else:
                self.close_camera()
                if contours > 0 and pir_val == 1: # save the event in false folder
                    self.make_event(frames, is_motion)                    
                
                if self.should_log:
                    if self.logs:
                        self.send_log('Events Captured: {}, PIR:{}'.format(str(self.logs), pir_val))
                        self.logs = []
                    self.send_log('Event: {}, max contours:{}, PIR:{}'.format(self.event_id, contours, pir_val))
                time.sleep(self.rest_interval)

    def make_event(self, frames, ismotion=True):
        if ismotion:
            event_path = os.path.join(self.events_dir, self.event_id)
        else:
            event_path = os.path.join(self.false_dir, self.event_id)


        if not os.path.exists(event_path):
            os.makedirs(event_path)

        for filename, frame in frames:
            cv2.imwrite(event_path + '/' + filename, frame)

    def night_vision(self, on):
        if on:
            GPIO.output(self.led_pin, GPIO.HIGH)
            GPIO.output(self.gnd_pin, GPIO.LOW)
        else:
            GPIO.output(self.led_pin, GPIO.LOW)
            GPIO.output(self.gnd_pin, GPIO.HIGH)

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

    def rest(self):
        GPIO.output(self.infrared, GPIO.LOW)

    def open_camera(self):
        self.night_vision(on=not self.is_sunlight(datetime.now()))
        self.infrared_switch(on=not self.is_sunlight(datetime.now()))

        self.camera = cv2.VideoCapture(gstreamer_pipeline(flip_method=0), cv2.CAP_GSTREAMER)
        if self.camera.isOpened():
            for skip in range(35):
                _ = self.camera.read()

            return True
        return False

    def capture(self, interval):
        frames = []
        for sec in range(interval):
            ret_val, frame = self.camera.read()
            if not self.is_sunlight(datetime.now()):
                frame = ImageOperations.convert_image_to_gray(frame)

            frames.append((str(current_milli_time()) + '.jpg', frame))

            for skip in range(self.frames_per_sec - 1):
                _ = self.camera.read()

        return frames

    def motion_detection(self, frames):
        max_contours = []
        _, first_frame = frames[0]

        for _, frame in frames:
            diff = ImageOperations.error_image_gray_histmatch(first_frame, frame)
            diff = ImageOperations.convert_to_binary(diff)
            diff = cv2.erode(diff, None, iterations=1)
            diff = cv2.dilate(diff, None, iterations=3)
            cnts, _ = cv2.findContours(diff.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            max_contour = max([cv2.contourArea(cnt) for cnt in cnts] or [0])
            max_contours.append(max_contour)

            threshold = self.day_threshold if self.is_sunlight(datetime.now()) else self.night_threshold

            if threshold < max_contour:
                return True, max_contour

        return False, max_contours

    def is_sunlight(self, dt):
        return self.sunrise.time() < dt.time() < self.sunset.time()

    def infrared_switch(self, on):
        if on:
            GPIO.output(self.infrared, GPIO.HIGH)
        else:
            GPIO.output(self.infrared, GPIO.LOW)

    def close_camera(self):
        self.infrared_switch(on=False)
        self.camera.release()


if __name__ == "__main__":
    node = Node()
    try:
        node.run()
    except KeyboardInterrupt:
        node.close_camera()
