import json
import math
import os
import time
from datetime import datetime, timedelta

import cv2
import numpy as np
import psutil
import requests


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
            im = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY, 1)
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
    def error_image_gray_histmatch(im1, im2, invert=False):
        im1_gray = ImageOperations.convert_image_to_gray(im1)
        im2_gray = ImageOperations.convert_image_to_gray(im2)

        im2_gray = ImageOperations.match_histograms(im2_gray, im1_gray)
        _result = cv2.absdiff(im1_gray, im2_gray.astype(np.uint8))
        _result = cv2.normalize(_result, dst=None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8U)
        if invert:
            _result = 255 - _result
        return _result

    @staticmethod
    def match_histograms(src_image, ref_image):
        """
        This implementation is 3x slower than that of scikit image
        This method matches the source image histogram to the
        reference signal
        :param image src_image: The original source image
        :param image  ref_image: The reference image
        :return: image_after_matching
        :rtype: image (array)
        """

        # Compute the histograms separately
        # The flatten() Numpy method returns a copy of the array c
        # collapsed into one dimension.
        src_hist, bin_0 = np.histogram(src_image.flatten(), 256, [0, 256])
        ref_hist, bin_3 = np.histogram(ref_image.flatten(), 256, [0, 256])

        # Compute the normalized cdf for the source and reference image
        # Get the cumulative sum of the elements
        src_cdf = src_hist.cumsum()
        ref_cdf = ref_hist.cumsum()

        # Normalize the cdf
        src_cdf = src_cdf / float(src_cdf.max())
        ref_cdf = ref_cdf / float(ref_cdf.max())

        # Make a separate lookup table for each color
        lookup_table = ImageOperations.calculate_lookup(src_cdf, ref_cdf)

        # Use the lookup function to transform the colors of the original
        # source image
        image_after_matching = cv2.LUT(src_image, lookup_table)

        # image_after_matching = cv2.convertScaleAbs(image_after_matching)

        return image_after_matching

    @staticmethod
    def calculate_lookup(src_cdf, ref_cdf):
        """
        This method creates the lookup table
        :param array src_cdf: The cdf for the source image
        :param array ref_cdf: The cdf for the reference image
        :return: lookup_table: The lookup table
        :rtype: array
        """
        lookup_table = np.zeros(256)
        lookup_val = 0
        for src_pixel_val in range(len(src_cdf)):
            lookup_val
            for ref_pixel_val in range(len(ref_cdf)):
                if ref_cdf[ref_pixel_val] >= src_cdf[src_pixel_val]:
                    lookup_val = ref_pixel_val
                    break
            lookup_table[src_pixel_val] = lookup_val
        return lookup_table

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

    @staticmethod
    def get_optimal_font_scale(text, height, width, argfontFace, argthickness):
        for scale in reversed(range(0, 60, 1)):
            textSize = cv2.getTextSize(text, fontFace=argfontFace, fontScale=scale / 100, thickness=argthickness)
            new_height = textSize[0][1]
            new_width = textSize[0][0]
            if new_width <= width and new_height <= height:
                return scale / 100
        return 1

    @staticmethod
    def addFooter(img, short_txt, long_txt):
        height, width, _ = img.shape

        # Check if it is a low resolution image and adjust the text bar height
        row = int(math.ceil(height * 0.95))  # Hardcoded to 0.95 based on exprical evidence
        textbar_height = height - row
        txtstr = long_txt

        if textbar_height < 11:  # Hardcoded to 11 based on exprical evidence
            row = height - 11
            txtstr = short_txt

        # Add black stip at the bottom
        textbar_height = height - row
        img[row:height, 0:width] = 0

        # Line thickness of 2 px
        thickness = 1

        # font
        font = cv2.FONT_HERSHEY_SIMPLEX

        # Assuming the image size and length of text won't change much, the function below should be called only once during init
        fntscl = ImageOperations.get_optimal_font_scale(txtstr, textbar_height, width, font, thickness)  # optimize

        # fontScale
        fontScale = fntscl  # Show be set once per machine, optimize

        color = (255, 255, 255)  # Blue color in BGR
        org = (2, int(math.ceil(height - 0.3 * textbar_height)))  # org
        # Using cv2.putText() method
        return cv2.putText(img, txtstr, org, font, fontScale, color, thickness, cv2.LINE_AA)


def get_disk_usage():
    disk = psutil.disk_usage('/')
    # print (obj_Disk.total / (1024.0 ** 3))
    # print (obj_Disk.used / (1024.0 ** 3))
    return round(disk.free / (1024.0 ** 3), 3)


class Constants:
    data_root = 'data_root'
    data_dir = os.environ['HOME'] + '/' + data_root
    events_dir = data_dir + '/events/'
    upload_dir = data_dir + '/uploads/'
    temp_dir = data_dir + '/temp/'
    false_dir = data_dir + '/false/'
    done_dir = data_dir + '/done/'
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
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
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
    def name(self):
        return self.ME['description'][:24]

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

    def send_log(self, message):
        try:
            response = requests.post(self.logs_url, headers=self.headers, data=json.dumps({'message': message}))
            if response.status_code != 201:
                print(response.text)
        except Exception as e:
            print(e.message)

    def update(self):
        payload = {"remaining_storage": get_disk_usage(),
                   'last_reported_at': datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}
        response = requests.request("PATCH", self.me_url, headers=self.headers, data=json.dumps(payload))
        self.ME = json.loads(response.text)
