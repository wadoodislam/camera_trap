import logging
import os
import time
from datetime import datetime
from uuid import uuid4
import requests

import Jetson.GPIO as GPIO
import cv2

from utils import gstreamer_pipeline, current_milli_time, Constants, ImageOperations


class Capture(Constants):
    event_id = None
    table = 'capture_logs'
    mask = None

    def __init__(self):
        super().__init__()
        logging.info('Script Started')
        self.read_params()
        self.download_roi_mask()
        self.read_roi_mask()

        with self.db:
            self.db.create_tables()

        logging.info(f'Checked Tables')

        self.put_log(
            [f'"{datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}"', '"SCRIPT_STARTED"', '1', f'"Capture Started"'])
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
                continue

            self.event_id = uuid4().hex
            pir1, pir2 = GPIO.input(self.motion1), GPIO.input(self.motion2)

            self.night_vision(on=not self.is_sunlight(datetime.now()))
            self.infrared_switch(on=not self.is_sunlight(datetime.now()))
            logging.info('Polling for Motion')
            frames = self.capture(self.motion_interval)
            is_motion, contours = self.motion_detection(frames)

            if is_motion:
                logging.debug(f'Motion Detected and Capturing Started')
                frames += self.capture(self.video_interval)
                self.write_event(frames)
                logging.debug(f'Event captured with contours {contours}')
                self.put_log([f'"{datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}"', '"EVENT_CAPTURED"', '1',
                              f'"UUID: {self.event_id}, Contours: {contours}, PIR: {pir1 + pir2}"'])
            elif not self.is_sunlight(datetime.now()):
                self.infrared_switch(on=False)
                time.sleep(self.rest_interval)

    def open_camera(self):
        self.camera = cv2.VideoCapture(gstreamer_pipeline(flip_method=0), cv2.CAP_GSTREAMER)
        if self.camera.isOpened():
            for skip in range(35):
                _ = self.camera.read()

            return True
        return False

    def capture(self, interval):
        frames = []
        for sec in range(interval):
            for skip in range(self.frames_per_sec - 1):
                _ = self.camera.read()

            ret_val, frame = self.camera.read()
            if not self.is_sunlight(datetime.now()):
                frame = ImageOperations.convert_image_to_gray(frame)

            frames.append((str(current_milli_time()) + '.jpg', frame))

        return frames

    def motion_detection(self, frames):
        max_contours = []
        _, first_frame = frames[0]

        for _, frame in frames:
            diff = ImageOperations.error_image_gray_histmatch(first_frame, frame)
            diff = ImageOperations.convert_to_binary(diff)
            logging.info()
            if self.mask is not None:
                diff = cv2.bitwise_and(diff, diff, mask=self.mask)
            diff = cv2.erode(diff, None, iterations=1)
            diff = cv2.dilate(diff, None, iterations=3)
            cnts, _ = cv2.findContours(diff.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            max_contour = max([cv2.contourArea(cnt) for cnt in cnts] or [0])
            max_contours.append(max_contour)

            threshold = self.day_threshold if self.is_sunlight(datetime.now()) else self.night_threshold

            if threshold < max_contour:
                return True, max_contour

        return False, max_contours

    def download_roi_mask(self):
        if self.ME['roi_mask']:
            try:
                response = requests.get(self.ME['roi_mask'])
            except Exception:
                logging.warn(f'Error while fetching roi_mask')
                pass
            else:
                open("roi_mask.png", "wb").write(response.content)
                logging.info("Downloaded ROI mask")
        else:
            logging.info("ROI mask not available")

    def read_roi_mask(self):
        try:
            self.mask = cv2.cvtColor(cv2.imread('roi_mask.png'), cv2.COLOR_BGR2GRAY)
        except Exception:
            logging.info("Couldn't find/open roi_mask.png")
            self.mask = None
            pass

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
    logging.basicConfig(format='%(asctime)s - capture:%(levelname)s - %(message)s', level=logging.DEBUG)
    capture = Capture()
    try:
        if capture.open_camera():
            capture.run()
        else:
            capture.put_log([f'"{datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}"',
                             '"CAMERA_ERROR"', '1', '"Unable to open camera!"'])
            logging.error('Unable to open camera!')
    except KeyboardInterrupt:
        capture.close_camera()
