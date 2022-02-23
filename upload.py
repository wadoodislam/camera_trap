import json
import os
import shutil
import time
from datetime import datetime

import requests
from PIL import Image

from utils import Constants
from utils import ImageOperations


class UploadManager(Constants):    

    def send_image(self, event, item, width, height):
        item_path = os.path.join(self.upload_dir, event, item)
        im = Image.open(item_path)
        # add footer here
        im = ImageOperations.addFooter(im, file_name_t, ''): 
        temp_item_path = os.path.join(self.temp_dir, item)
        file, ext = os.path.splitext(temp_item_path)
        im_resize = im.resize((width, height), Image.ANTIALIAS)
        im_resize.save(file + '.jpg', 'JPEG', quality=90)
        payload = {'uuid': event, 'date': time.strftime("%Y-%m-%d", time.localtime())}
        files = [('file', (item, open(temp_item_path, 'rb'), 'image/jpg'))]
        try:
            response = requests.request("POST", self.image_url, headers=self.headers_im, data=payload, files=files)
            file_name_t = datetime.fromtimestamp(float(item[:-4])/1000)
            if response.status_code != 201:
                log = {'message': 'Upload failed for Event "{}" & Image Time: "{}" with Status: {}'.format(event, file_name_t, response.status_code)}
                requests.post(self.logs_url, headers=self.headers, data=json.dumps(log))
                return False
            log = {'message': 'Upload success for Event "{}" & Image Time: "{}" with Status: {}'.format(event, file_name_t, response.status_code)}
            requests.post(self.logs_url, headers=self.headers, data=json.dumps(log))
        except Exception as e:
            return False
        return True

    def run(self):
        print('checking for uploads...')
        while True:
            #if self.should_update:
            #    self.update()
            #    print('Updated from dashboard at: {}'.format(datetime.now()))

            events = os.listdir(self.upload_dir)
            if not events:
                time.sleep(1)
            else:
                event = sorted(events, key=lambda e: os.stat(os.path.join(self.upload_dir, e)).st_ctime, reverse=True)[0]
                items = os.listdir(os.path.join(self.upload_dir, event))
                if items:
                    item = items[0]
                    self.send_image(event, item, width=340, height=220) # - Hardcoded
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
