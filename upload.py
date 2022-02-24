import os
import shutil
import time
from datetime import datetime

import cv2
import requests
from PIL import Image

from utils import Constants
from utils import ImageOperations


class UploadManager(Constants):

    def send_image(self, event, item, width, height):
        item_path = os.path.join(self.upload_dir, event, item)
        file_dt = datetime.fromtimestamp(float(item[:-4]) / 1000)
        im = cv2.imread(item_path)
        # add footer here
        short_txt, long_txt = self.get_copy_rights(file_dt)
        #im = ImageOperations.addFooter(im, short_txt, long_txt)
        temp_item_path = os.path.join(self.temp_dir, item)
        file, ext = os.path.splitext(temp_item_path)
        im_resize = cv2.resize(im, (width, height))
        cv2.imwrite(file + '.jpg', im_resize,  [cv2.IMWRITE_JPEG_QUALITY, 90])
        payload = {'uuid': event, 'date': time.strftime("%Y-%m-%d", time.localtime())}
        files = [('file', (item, open(temp_item_path, 'rb'), 'image/jpg'))]
        try:
            response = requests.request("POST", self.image_url, headers=self.headers_im, data=payload, files=files)
            if response.status_code == 201:
                self.send_log('Upload success for Event "{}" & Image Time: "{}" with'.format(event, file_dt))
                return True
        except Exception as e:
            pass

        self.send_log('Upload failed for Event "{}" & Image Time: "{}" with'.format(event, file_dt))
        return False

    def run(self):
        print('checking for uploads...')
        while True:
            if self.should_update:
               self.update()

            events = os.listdir(self.upload_dir)
            if not events:
                time.sleep(1)
            else:
                event = sorted(events, key=lambda e: os.stat(os.path.join(self.upload_dir, e)).st_ctime, reverse=True)[0]
                items = os.listdir(os.path.join(self.upload_dir, event))
                if items:
                    item = items[0]
                    self.send_image(event, item, width=640, height=480)  # - Hardcoded
                    self.move_to_done(event, item)
                else:
                    shutil.rmtree(os.path.join(self.upload_dir, event))

    def move_to_done(self, event, item):
        item_path = os.path.join(self.upload_dir, event, item)
        done_item_path = os.path.join(self.done_dir, event)
        if not os.path.exists(done_item_path):
            os.makedirs(done_item_path)
        shutil.move(item_path, os.path.join(done_item_path, item))
        os.remove(os.path.join(self.temp_dir, item))

    def get_copy_rights(self, file_dt):
        long_txt = file_dt.strftime('%b %d, %Y     %H:%M:%S') + '     ' + self.name + '     ' + 'POWERED BY LUMS'
        shrt_txt = file_dt.strftime('%d.%m.%y  %H:%M') + '  ' + "".join(e[0] for e in self.name.split()) + '  LUMS'
        return shrt_txt, long_txt


if __name__ == "__main__":
    UploadManager().run()
