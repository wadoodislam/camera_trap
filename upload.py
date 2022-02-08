import os
import shutil
import time

import requests
from PIL import Image

from utils import Constants


class UploadManager(Constants):
    image_url = os.environ['SITE'] + '/core/api/image/'
    logs_url = os.environ['SITE'] + '/core/api/logs/'

    def send_image(self, event, item, width=500, height=375):
        item_path = os.path.join(self.upload_dir, event, item)
        im = Image.open(item_path)
        temp_item_path = os.path.join(self.temp_dir, item)
        file, ext = os.path.splitext(temp_item_path)
        im_resize = im.resize((width, height), Image.ANTIALIAS)
        im_resize.save(file + '.jpg', 'JPEG', quality=90)
        payload = {'uuid': event, 'date': time.strftime("%Y-%m-%d", time.localtime())}
        files = [('file', (item, open(temp_item_path, 'rb'), 'image/jpg'))]
        try:
            response = requests.request("POST", self.image_url, headers=self.headers_im, data=payload, files=files)
            if response.status_code != 201:
                log = {'message': 'Upload failed for Event "{}" & Item: "{}" with Status: {}'.format(event, item, response.status_code)}
                requests.post(self.logs_url, headers=self.headers, data=log)
                return False
        except Exception as e:
            return False
        return True

    def run(self):
        while True:
            events = os.listdir(self.upload_dir)
            if not events:
                time.sleep(1)
            else:
                event = sorted(events, key=lambda e: os.stat(os.path.join(self.upload_dir, e)).st_ctime, reverse=True)[0]
                items = os.listdir(os.path.join(self.upload_dir, event))
                if items:
                    item = items[0]
                    self.send_image(event, item, width=500, height=375)
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


if __name__ == "__main__":
    UploadManager().run()
