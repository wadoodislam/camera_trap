import os
import time
from datetime import datetime
from uuid import uuid4

import Jetson.GPIO as GPIO
import cv2

from utils import gstreamer_pipeline, current_milli_time, Constants, ImageOperations


class Capture(Constants):
    event_id = None
    table = 'capture_logs'

    def __init__(self):
        super().__init__()
        self.read_params()

        with self.db:
            self.db.create_tables()

        self.put_log([f'"{datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}"', '"SCRIPT_STARTED"', '1', f'"Capture Started"'])
        self.setup_sensors()

    def run(self):
        while True:
            if self.params_expired:
                self.read_params()
                if self.logging:
                    self.put_log([f'"{datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}"',
                                  '"ALIVE"', '1', f'"Capture Alive"'])
                    self.logging = False
            else:
                self.logging = True

            if not self.live:
                time.sleep(self.rest_interval)
                continue

            if not self.open_camera():
                self.put_log([f'"{datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}"',
                              '"CAMERA_ERROR"', '1', '"Unable to open camera!"'])
                time.sleep(self.rest_interval)
                continue

            pir1, pir2 = GPIO.input(self.motion1), GPIO.input(self.motion2)

            self.event_id = uuid4().hex

            frames = self.capture(self.motion_interval)
            is_motion, contours = self.motion_detection(frames)

            if is_motion:
                frames += self.capture(self.video_interval)
                self.close_camera()
                self.write_event(frames)
                self.put_log([f'"{datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}"', '"EVENT_CAPTURED"', '1',
                              f'"UUID: {self.event_id}, Contours: {contours}, PIR: {pir1 + pir2}"'])
            else:
                self.close_camera()
                time.sleep(self.rest_interval)

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

    def write_event(self, frames):
        event_path = os.path.join(self.events_dir, self.event_id)

        if not os.path.exists(event_path):
            os.makedirs(event_path)

        for filename, frame in frames:
            cv2.imwrite(event_path + '/' + filename, frame)

    def is_sunlight(self, dt):
        return self.sunrise.time() < dt.time() < self.sunset.time()

    def night_vision(self, on):
        if on:
            GPIO.output(self.filter_a, GPIO.HIGH)
            GPIO.output(self.filter_b, GPIO.LOW)
        else:
            GPIO.output(self.filter_a, GPIO.LOW)
            GPIO.output(self.filter_b, GPIO.HIGH)

    def infrared_switch(self, on):
        if on:
            self.pwm_obj.ChangeDutyCycle(self.pwm)
        else:
            self.pwm_obj.ChangeDutyCycle(0)

    def close_camera(self):
        self.infrared_switch(on=False)
        self.camera.release()

    def setup_sensors(self):
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(self.infrared, GPIO.OUT)
        self.pwm_obj = GPIO.PWM(self.infrared, 100)
        self.pwm_obj.start(0)
        GPIO.setup(self.filter_a, GPIO.OUT)
        GPIO.setup(self.filter_b, GPIO.OUT)
        GPIO.setup(self.motion1, GPIO.IN)
        GPIO.setup(self.motion2, GPIO.IN)


if __name__ == "__main__":
    capture = Capture()
    try:
        capture.run()
    except KeyboardInterrupt:
        capture.close_camera()
