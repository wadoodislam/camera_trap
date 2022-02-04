import math
import os
import shutil
import time

import cv2
import numpy as np
import requests
from PIL import Image


ME = {
    "slots": [],
    "live": True,
    "description": "Lums Camera",
    "longitude": 74.6675,
    "latitude": 36.3138,
    "created_at": "2021-03-01T04:46:00.349508+05:00",
    "last_reported_at": None,
    "action": "TURN_ON",
    "video_interval": 15.0,
    "update_after": 1800.0,
    "user": 3
}


homedir = os.environ['HOME']
path = homedir + '/images/'
temp_path = homedir + '/temp/'
backups = homedir + '/backups/'

today = time.strftime("%Y-%m-%d", time.localtime())


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


def motion_detection(image_paths, target_mask_path=None, show=True, movement_threshold=1000,
                     max_movement_threshold=3000):
    motion_detected = False

    starting_index = 1
    first_frame = cv2.imread(image_paths[0])

    # check if blown out
    # if ImageOperations.blown_out_check(first_frame):
    #     first_frame = cv2.imread(image_paths[1])
    #     starting_index += 1

    for image_index in range(starting_index, len(image_paths)):
        image_2 = cv2.imread(image_paths[image_index])
        # image_2 = cv2.GaussianBlur(image_2,(5,5),0)
        diff = ImageOperations.error_image_gray(first_frame, image_2)
        diff = ImageOperations.convert_to_binary(diff)
        image_height, image_width = diff.shape
        diff = cv2.dilate(diff, None, iterations=2)
        # cv2.imshow("diff", diff)
        # cv2.waitKey(0)
        cnts, _ = cv2.findContours(diff.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in cnts:
            print("Contour Area: ", cv2.contourArea(cnt))
            if movement_threshold < cv2.contourArea(cnt) < max_movement_threshold:
                motion_detected = True
                break

            else:
                continue

    return motion_detected


def resizeUpload(w, h, fixed_uuid, image_path):
    print('uuid is ' + fixed_uuid)
    dest = homedir + '/backups/' + fixed_uuid + '/'
    url = 'https://tpilums.org.pk/core/api/image/'
    payload = {'uuid': fixed_uuid, 'date': today}
    headers = {'Authorization': 'Token 30c1072095e928170016de0da11e7975bc0f7e66'}

    entries = os.listdir(image_path)
    if not entries:
        print("nothing to upload")

    if not os.path.exists(temp_path):
        os.makedirs(temp_path)

    n = len(entries)

    print('number of images ' + str(n))

    for item in entries:

        print(item)
        b = os.path.getsize(image_path + item)
        print('file size ok')
        if b < 50000:
            os.remove(image_path + item)
            print("file size is lower than 5 kb .. Deleting file")
            break

        im = Image.open(image_path + item)
        f, e = os.path.splitext(temp_path + item)
        imResize = im.resize((w, h), Image.ANTIALIAS)
        imResize.save(f + '.jpg', 'JPEG', quality=90)

        files = [('file', (item, open(temp_path + item, 'rb'), 'image/jpg'))]
        response = requests.request("POST", url, headers=headers, data=payload, files=files)

        if response.status_code != 201:
            print('file upload failed : ' + str(response.status_code))
        if response.status_code == 201:
            print('file uploaded')
            if not os.path.exists(dest):
                os.makedirs(dest)
            shutil.move(image_path + item, dest)
            os.remove(temp_path + item)
        # os.remove(image_path + item)


if __name__ == "__main__":

    print("starting upload")
    time.sleep(1)

    entries = os.listdir(path)
    if not entries:
        print("nothing to upload")
    for entry in entries:

        image_path = path + entry + '/'

        images = sorted([os.path.join(image_path, capture) for capture in os.listdir(image_path)])

        if motion_detection(images):
            print('motion detected')
            resizeUpload(500, 375, entry, image_path)

            listimages = os.listdir(image_path)

            if not listimages:
                print('All images uploaded')
                dir = entry
                dpath = os.path.join(path, dir)
                shutil.rmtree(dpath)


        else:
            print('Nothing detected')
            print('Backing up')
            if not os.path.exists(backups):
                os.makedirs(backups)
            backup_path = backups + entry
            if os.path.exists(backups + entry):
                listimages = os.listdir(image_path)
                print(listimages)
                for item in listimages:
                    shutil.move(image_path + item, backup_path)
                dir = entry
                dpath = os.path.join(path, dir)
                shutil.rmtree(dpath)

            else:
                shutil.move(image_path, backups)
            # shutil.rmtree(image_path)
            # print('event deleted')
