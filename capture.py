import json
import os
import shutil
import time
from datetime import datetime
from uuid import uuid4

import Jetson.GPIO as GPIO
import cv2
import requests

from utils import gstreamer_pipeline, current_milli_time, Constants, is_day_light, ImageOperations


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
        #print("started motion detect")        
        start_time = time.time()

        # flag = False
        # while not flag:
        while GPIO.input(7) == 0:
            if self.should_update:
                self.update()
            time.sleep(0.5)
            if time.time() - start_time >= 2: #Ideally use self.capture_interval - Hardcoded
                break

            # time.sleep(2)

            # if GPIO.input(7) != 0:
            #     flag = True

        #print("motion detected at: " + datetime.now().strftime('%H:%M:%S'))

    def capture(self, interval, continue_event= False):

        cap = cv2.VideoCapture(gstreamer_pipeline(flip_method=0), cv2.CAP_GSTREAMER)

        if cap.isOpened():
            if not is_day_light():
                self.night_vision(on=True)

            if  !continue_event  
                self.event_id = uuid4().hex

            if not os.path.exists(self.events_dir + self.event_id):
                os.makedirs(self.events_dir + self.event_id)

            #print("Starting capture at: " + datetime.now().strftime('%H:%M:%S'))

            for skip in range(35):  # to discard over exposure frames
                _ = cap.read()

            for sec in range(interval):  # change for number of pictures
                ret_val, frame = cap.read()
                if not is_day_light():
                    frame = ImageOperations.convert_image_to_gray(frame)

                cv2.imwrite(self.events_dir + self.event_id + '/' + str(current_milli_time()) + '.jpg', frame)

                for skip in range(self.frames_per_sec - 1):
                    _ = cap.read()

            #print("Done capturing at: " + datetime.now().strftime('%H:%M:%S'))
            cap.release()
            self.night_vision(on=False)
            return TRUE
        else:
            print("Unable to open camera: " + datetime.now().strftime('%H:%M:%S'))

    def run(self):
        while True:
            self.setup_sensors()
            self.detect_motion()


            if self.should_capture:
                #self.capture(self.check_interval): # just caputure after every 1 or 2 seconds to see if something is happening
                self.capture(2): # just caputure after every 1 or 2 seconds to see if something is happening - Hardcoded
                if self.validate_event() # something is happening then do a full event capture   
                    #self.move_event(self.trap_dir) # we should move this trap event to some other folder
                    self.capture(self.video_interval, True)
                else
                    self.move_event(self.temp_dir) # we can eliminate the additional validation and save some power

                GPIO.cleanup()
                #self.move_event(self.upload_dir if self.validate_event() else self.false_dir)
                self.move_event(self.upload_dir) # we can eliminate the additional validation and save some power
            else:
                time.sleep(self.video_interval)

    def validate_event(self):
        event_path = os.path.join(self.events_dir, self.event_id)
        images = sorted([os.path.join(event_path, img) for img in os.listdir(event_path)])

        if is_day_light():
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

    def motion_detection(self, image_paths, movement_threshold=1000, max_movement_threshold=3000):
        starting_index = 1
        first_frame = cv2.imread(image_paths[0])
        max_contours = []

        for image_index in range(starting_index, len(image_paths)):
            image_2 = cv2.imread(image_paths[image_index])
            #diff = ImageOperations.error_image_gray(first_frame, image_2)
            diff = ImageOperations.error_image_gray_histmatch(first_frame, image_2)            
            diff = ImageOperations.error_image_gray(first_frame, image_2)
            diff = ImageOperations.convert_to_binary(diff)
            diff = cv2.erode(diff, None, iterations=1)
            diff = cv2.dilate(diff, None, iterations=3)
            cnts, _ = cv2.findContours(diff.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            if len(cnts) > 0:
              contours = [cv2.contourArea(cnt) for cnt in cnts]
              max_contour = max(contours)              
            else:
              max_contour = 0

            max_contours.append(max_contour)

            if movement_threshold < max_contour:
                log = {
                    'message': 'Event: {}, index: {}, max contour:{}'.format(self.event_id, image_index, max_contour)
                }
                requests.post(self.logs_url, headers=self.headers, data=json.dumps(log))
                return True

        print("Event ID: {}, Contour Areas: {}".format(self.event_id, max_contours))
        log = {
            'message': 'Event: {}, max contours:{}'.format(self.event_id, max_contours)
        }
        requests.post(self.logs_url, headers=self.headers, data=json.dumps(log))
        return False


if __name__ == "__main__":
    Node().run()
