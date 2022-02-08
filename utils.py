import math
import os
import time

import cv2
import numpy as np
from datetime import datetime, timedelta



def gstreamer_pipeline(capture_width=640, capture_height=480, display_width=640, display_height=480, framerate=30, flip_method=2):
    return (
            "nvarguscamerasrc ! "
            "video/x-raw(memory:NVMM), "
            "width=(int)%d, height=(int)%d, "
            "format=(string)NV12, framerate=(fraction)%d/1 ! "
            "nvvidconv flip-method=%d ! "
            "video/x-raw, width=(int)%d, height=(int)%d, format=(string)BGRx ! "
            "videoconvert ! "
            "video/x-raw, format=(string)BGR ! appsink"
            % (
                capture_width,
                capture_height,
                framerate,
                flip_method,
                display_width,
                display_height,
            )
    )


def dt_parse(t):
    ret = datetime.strptime(t[:-6], '%Y-%m-%dT%H:%M:%S.%f')
    # if t[-6] == '+':
    #     ret += timedelta(hours=int(t[-5:-3]), minutes=int(t[-2:]))
    # elif t[-6] == '-':
    #     ret -= timedelta(hours=int(t[-5:-3]), minutes=int(t[-2:]))
    return ret


def current_milli_time():
    return round(time.time() * 1000)


class ImageOperations:

    @staticmethod
    def convert_image_to_gray(im):
        if len(im.shape) == 3:
            im = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
        return im

    @staticmethod
    def __convert_image_to_hsv(im):
        return cv2.cvtColor(im, cv2.COLOR_BGR2HSV_FULL)

    @staticmethod
    def __convert_to_hls(im):
        return cv2.cvtColor(im, cv2.COLOR_BGR2HLS_FULL)

    @staticmethod
    def error_image_hsv(im1, im2, invert=False):
        im1 = ImageOperations.__convert_image_to_hsv(im1)
        im2 = ImageOperations.__convert_image_to_hsv(im2)
        _result = cv2.cvtColor(cv2.cvtColor(cv2.absdiff(im1, im2), cv2.COLOR_HSV2RGB), cv2.COLOR_RGB2GRAY)
        _result = cv2.normalize(_result, dst=None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8U)
        if invert:
            _result = 255 - _result
        return _result

    @staticmethod
    def error_image_gray(im1, im2, invert=False):
        im1_gray = ImageOperations.convert_image_to_gray(im1)
        im2_gray = ImageOperations.convert_image_to_gray(im2)
        _result = cv2.absdiff(im1_gray, im2_gray)
        _result = cv2.normalize(_result, dst=None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8U)
        if invert:
            _result = 255 - _result
        return _result

    @staticmethod
    def gamma_correction(image):
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        hue, sat, val = cv2.split(hsv)
        mid = 0.5
        mean = np.mean(val)
        gamma = math.log(mid * 255) / math.log(mean)
        gamma = 1 / gamma
        look_up_table = np.array([((i / 255.0) ** gamma) * 255
                                  for i in np.arange(0, 256)]).astype("uint8")
        val_gamma = cv2.LUT(val, look_up_table)
        hsv_gamma = cv2.merge([hue, sat, val_gamma])
        image = cv2.cvtColor(hsv_gamma, cv2.COLOR_HSV2BGR)
        return image

    @staticmethod
    def image_masking(sample_aligned, target_mask):
        target_mask = cv2.resize(target_mask, (sample_aligned.shape[1], sample_aligned.shape[0]))
        result_image = cv2.bitwise_and(sample_aligned, target_mask)
        return result_image

    @staticmethod
    def convert_to_binary(image, thresh=125):
        _, thresh = cv2.threshold(image, thresh=thresh, maxval=255, type=cv2.THRESH_BINARY)  # 125 default
        return thresh

    @staticmethod
    def blown_out_check(image, thresh=1):
        binary_image = ImageOperations.convert_to_binary(image) / 255.0
        w, h, _ = binary_image.shape
        exposure = np.sum(binary_image) / (w * h)
        print("Exposure: ", exposure)
        if exposure > thresh:
            return True

        return False

    @staticmethod
    def frame_percentage_change(image):
        image_width, image_height = image.shape
        change = (np.sum(image) / 255) / (image_width * image_height) * 100
        return change


def motion_detection(image_paths, target_mask_path=None, show=True, movement_threshold=1000, max_movement_threshold=3000):
    starting_index = 1
    first_frame = cv2.imread(image_paths[0])

    for image_index in range(starting_index, len(image_paths)):
        image_2 = cv2.imread(image_paths[image_index])
        diff = ImageOperations.error_image_gray(first_frame, image_2)
        diff = ImageOperations.convert_to_binary(diff)
        diff = cv2.dilate(diff, None, iterations=2)
        cnts, _ = cv2.findContours(diff.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in cnts:
            if movement_threshold < cv2.contourArea(cnt):
                print("Motion Frame: ", image_index)
                print("Contour Area: ", cv2.contourArea(cnt))
                return True

    return False


class Constants:
    events_dir = os.environ['HOME'] + '/events/'
    upload_dir = os.environ['HOME'] + '/uploads/'
    temp_dir = os.environ['HOME'] + '/temp/'
    false_dir = os.environ['HOME'] + '/false/'
    done_dir = os.environ['HOME'] + '/done/'
    url = None

    headers = {
        'Authorization': 'Token ' + os.environ['TOKEN'],
        'Content-Type': 'application/json'
    }
    headers_im = {
        'Authorization': 'Token ' + os.environ['TOKEN'],
    }

    def __init__(self):
        if not os.path.exists(self.events_dir):
            os.makedirs(self.events_dir)
        if not os.path.exists(self.upload_dir):
            os.makedirs(self.upload_dir)
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)
        if not os.path.exists(self.false_dir):
            os.makedirs(self.false_dir)
        if not os.path.exists(self.done_dir):
            os.makedirs(self.done_dir)
