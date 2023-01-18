import os
import shutil
import logging
import time
from datetime import datetime, timedelta

import cv2
import requests
from Jetson import GPIO

from utils import Constants
from utils import ImageOperations


class UploadManager(Constants):
    table = 'upload_logs'

    def __init__(self):
        super().__init__()
        logging.info('Script Started')
        time.sleep(10)
        self.read_params()

        with self.db:
            self.db.create_tables()

        logging.info(f'Checked Tables')
        self.put_log([f'"{datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}"', '"SCRIPT_STARTED"', '1', f'"Upload Started"'])
        self.setup_sensors()
        self.bad_request_timer = None
        self.retry_request_timer = None
        GPIO.output(self.pin, GPIO.LOW)
        logging.info("4g turned ON at Reboot")
        self.lastuse_4g_at = datetime.now()
        self.is_4g_on = True

    def run(self):
        while True:
            if self.params_expired:
                self.read_params()
                if self.logging:
                    self.put_log([f'"{datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}"',
                                   '"ALIVE"', '1', f'"Upload Alive"'])
                    self.logging = False
            else:
                self.logging = True
            if self.should_stop_requesting():
                self.retry_request_timer = datetime.now()
                self.bad_request_timer = None
            events = os.listdir(self.events_dir)
            if not events:
                logging.info(str(self.should_turn_4g_off()))
                logging.info(str(self.is_4g_on))
                logging.info(str(self.lastuse_4g_at))
                if self.should_turn_4g_off() and self.is_4g_on:
                    GPIO.output(self.pin, GPIO.HIGH)
                    logging.info("4g turned OFF")
                    self.is_4g_on = False
                time.sleep(1)
            else:
                if not self.should_retry():
                    if self.is_4g_on:
                        GPIO.output(self.pin, GPIO.HIGH)
                        logging.info("4g turned OFF for 15 minutes; event upload unsuccessful")
                        self.is_4g_on = False
                    continue
                if self.should_retry():
                    if self.retry_request_timer is not None:
                        self.retry_request_timer = None
                if not self.is_4g_on:
                    GPIO.output(self.pin, GPIO.LOW)
                    logging.info("4g turned ON; event detected")
                    self.is_4g_on = True
                event = sorted(events, key=lambda e: os.stat(os.path.join(self.events_dir, e)).st_ctime, reverse=True)[0]
                items = os.listdir(os.path.join(self.events_dir, event))
                if items:
                    item = items[0]
                    temp_img_path = self.prepare_image(event, item, width=640, height=480)
                    if not temp_img_path:
                        self.put_log([f'"{datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}"',
                                      '"UPLOAD_FAILED"', '1', f'"Corrupted image found! UUID: {event}"'])
                        self.move_to_done(event, item)
                    elif self.send_image(event, item, temp_img_path):
                        self.move_to_done(event, item)
                    self.lastuse_4g_at = datetime.now()
                    if temp_img_path:
                        os.remove(os.path.join(self.temp_dir, item))
                else:
                    shutil.rmtree(os.path.join(self.events_dir, event))

    def send_image(self, event, item, temp_path):
        file_dt = datetime.fromtimestamp(float(item[:-4]) / 1000)
        payload = {'uuid': event, 'date': str(file_dt)}
        files = [('file', (item, open(temp_path, 'rb'), 'image/jpg'))]
        try:
            response = requests.request("POST", self.image_url, headers=self.headers_im, data=payload, files=files)
            if response.status_code in [201, 208]:
                self.put_log([f'"{datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}"',
                              '"UPLOAD_SUCCESS"', '1', f'"UUID: {event} & Image At: {file_dt}"'])
                logging.info(f'Successfully Uploaded Image At: {file_dt}')
        except Exception as e:
            if self.bad_request_timer is None:
                self.bad_request_timer = datetime.now()
            self.put_log([f'"{datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}"',
                          '"UPLOAD_FAILED"', '1', f'"UUID: {event} & Image At: {file_dt}"'])
            logging.info(f'Not uploaded image At: {file_dt}')
            pass
        else:
            if self.bad_request_timer is not None:
                self.bad_request_timer = None
            return True

        return False

    def move_to_done(self, event, item):
        item_path = os.path.join(self.events_dir, event, item)
        done_item_path = os.path.join(self.done_dir, event)
        if not os.path.exists(done_item_path):
            os.makedirs(done_item_path)
        shutil.move(item_path, os.path.join(done_item_path, item))

    def get_copy_rights(self, file_dt):
        long_txt = file_dt.strftime('%b %d, %Y     %H:%M:%S') + '     ' + self.name + '     ' + 'POWERED BY LUMS'
        shrt_txt = file_dt.strftime('%d.%m.%y  %H:%M') + '  ' + "".join(e[0] for e in self.name.split()) + '  LUMS'
        return shrt_txt, long_txt

    def prepare_image(self, event, item, width, height):
        item_path = os.path.join(self.events_dir, event, item)
        file_dt = datetime.fromtimestamp(float(item[:-4]) / 1000)
        im = cv2.imread(item_path)
        if im is None:
            return None

        short_txt, long_txt = self.get_copy_rights(file_dt)
        im = ImageOperations.addFooter(im, short_txt, long_txt)
        temp_item_path = os.path.join(self.temp_dir, item)
        file, ext = os.path.splitext(temp_item_path)
        im_resize = cv2.resize(im, (width, height))
        cv2.imwrite(file + '.jpg', im_resize, [cv2.IMWRITE_JPEG_QUALITY, 90])
        return temp_item_path

    def should_stop_requesting(self):
        if self.bad_request_timer is None:
            return False
        return datetime.now() > self.bad_request_timer + timedelta(seconds=150)

    def should_retry(self):
        if self.retry_request_timer is None:
            return True
        return datetime.now() > self.bad_request_timer + timedelta(seconds=900)

    def should_turn_4g_off(self):
        rn = datetime.now()
        future = self.lastuse_4g_at + timedelta(seconds=self.idol_4g_interval)
        return rn > future


if __name__ == "__main__":
    logging.basicConfig(format='%(asctime)s - upload:%(levelname)s - %(message)s', level=logging.DEBUG)
    UploadManager().run()
