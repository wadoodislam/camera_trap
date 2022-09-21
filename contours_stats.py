import logging
import statistics
from datetime import datetime

import Jetson.GPIO as GPIO
import cv2

from utils import gstreamer_pipeline, current_milli_time, Constants, ImageOperations


class Contours(Constants):
    event_id = None

    def __init__(self):
        self.read_params()
        self.setup_sensors()

    def run(self):
        self.night_vision(on=not self.is_sunlight(datetime.now()))
        self.infrared_switch(on=not self.is_sunlight(datetime.now()))
        logging.info('Polling for Motion')
        frames = self.capture(self.motion_interval)
        frames += self.capture(self.video_interval)
        contours = self.motion_detection(frames)
        self.infrared_switch(on=False)
        print(f'MAX contour:{max(contours)}')
        print(f'MEAN contour:{statistics.mean(contours)}')
        print(f'MIN contour:{min(contours)}')
        print(f'STD contour:{statistics.stdev(contours)}')
        print(f'MEAN + 1STD contour:{statistics.mean(contours) + 1 * statistics.stdev(contours)}')
        print(f'MEAN + 2STD contour:{statistics.mean(contours) + 2 * statistics.stdev(contours)}')

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
            ret_val, frame = self.camera.read()
            if not self.is_sunlight(datetime.now()):
                frame = ImageOperations.convert_image_to_gray(frame)

            frames.append((str(current_milli_time()) + '.jpg', frame))

            for skip in range(self.frames_per_sec - 1):
                _ = self.camera.read()

        return frames

    def motion_detection(self, frames):
        max_contours = []

        for i in range(len(frames)-1):
            _, frame_1 = frames[i]
            _, frame_2 = frames[i+1]

            diff = ImageOperations.error_image_gray_histmatch(frame_1, frame_2)
            diff = ImageOperations.convert_to_binary(diff)
            diff = cv2.erode(diff, None, iterations=1)
            diff = cv2.dilate(diff, None, iterations=3)
            cnts, _ = cv2.findContours(diff.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            max_contour = max([cv2.contourArea(cnt) for cnt in cnts] or [0])
            max_contours.append(max_contour)

        return max_contours

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
    contours = Contours()
    try:
        if contours.open_camera():
            contours.run()
            logging.error('Unable to open camera!')
    finally:
        contours.close_camera()
