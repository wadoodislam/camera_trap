import json
import math
import os
import smbus
import time
import psutil
import cv2
import numpy as np
from datetime import datetime, timedelta

import requests


# def gstreamer_pipeline(capture_width=640, capture_height=480, display_width=640, display_height=480, framerate=30, flip_method=2):
#     return (
#             "nvarguscamerasrc ! "
#             "video/x-raw(memory:NVMM), "
#             "width=(int)%d, height=(int)%d, "
#             "format=(string)NV12, framerate=(fraction)%d/1 ! "
#             "nvvidconv flip-method=%d ! "
#             "video/x-raw, width=(int)%d, height=(int)%d, format=(string)BGRx ! "
#             "videoconvert ! "
#             "video/x-raw, format=(string)BGR ! appsink"
#             % (
#                 capture_width,
#                 capture_height,
#                 framerate,
#                 flip_method,
#                 display_width,
#                 display_height,
#             )
#     )
def gstreamer_pipeline(capture_width=1280, capture_height=720,
    display_width=960,
    display_height=540,
    framerate=30,
    flip_method=0,
):
    return (
        "nvarguscamerasrc !"
        "video/x-raw(memory:NVMM), width=(int)%d, height=(int)%d, framerate=(fraction)%d/1 ! "
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
    ret = datetime.strptime(t[:19], '%Y-%m-%dT%H:%M:%S')
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


bus = smbus.SMBus(1)


def is_day_light():
    DEVICE, ONE_TIME_HIGH_RES_MODE_1 = 0x23, 0x20
    light = None

    for i in range(3):
        data = bus.read_i2c_block_data(DEVICE, ONE_TIME_HIGH_RES_MODE_1)
        light = (data[1] + (256 * data[0])) / 1.2

    return light > 500


class Constants:
    events_dir = os.environ['HOME'] + '/events/'
    upload_dir = os.environ['HOME'] + '/uploads/'
    temp_dir = os.environ['HOME'] + '/temp/'
    false_dir = os.environ['HOME'] + '/false/'
    done_dir = os.environ['HOME'] + '/done/'
    me_url = os.environ['SITE'] + '/core/api/camera/me/'
    logs_url = os.environ['SITE'] + '/core/api/logs/'
    image_url = os.environ['SITE'] + '/core/api/image/'
    ME = None

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
        self.update()

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
    def sunset(self):
        return dt_parse(str(self.ME['sunset']))

    @property
    def sunrise(self):
        return dt_parse(str(self.ME['sunrise']))

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
        payload = {"remaining_storage": self.get_disk_usage(), 'last_reported_at': datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}
        response = requests.request("PATCH", self.me_url, headers=self.headers, data=json.dumps(payload))
        self.ME = json.loads(response.text)

    def get_disk_usage(self):
        disk = psutil.disk_usage('/')
        # print (obj_Disk.total / (1024.0 ** 3))
        # print (obj_Disk.used / (1024.0 ** 3))
        return round(disk.free / (1024.0 ** 3), 3)
