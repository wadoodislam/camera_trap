import logging
import json
from datetime import datetime, timedelta

import requests

from utils import Constants, get_disk_usage, format_logs


class Monitor(Constants):

    def __init__(self):
        super(Monitor, self).__init__()
        logging.info('Script Started')
        self.fetch_params()
        self.download_roi_mask()

        with self.db:
            self.db.create_tables()

        logging.info(f'Checked Tables')

    def run(self):
        while True:
            if self.params_expired:
                self.fetch_params()
                self.send_logs()

    def fetch_params(self):
        try:
            payload = {
                "remaining_storage": get_disk_usage(),
                'last_reported_at': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
            }
            response = requests.request("PATCH", self.me_url, headers=self.headers,
                                        data=json.dumps(payload), timeout=10)
            self.ME = json.loads(response.text)
            with open(self.data_dir + '/ME.json', 'w') as file:
                file.write(json.dumps(self.ME, indent=4))

            logging.info(f'Fetched ME.json')
        except Exception:
            logging.warn(f'Error while fetching ME.json')
            pass

    def download_roi_mask(self):
        if self.ME['roi_mask']:
            response = requests.get(self.ME['roi_mask'])
            open("roi_mask.png", "wb").write(response.content)
            logging.info("Downloaded ROI mask")
        else:
            logging.info("ROI mask not available")

    def send_logs(self):
        with self.db:
            clogs, ulogs = self.db.get_pending_logs()

        logs = format_logs(clogs, ulogs)
        response = requests.request("POST", self.logs_url, headers=self.headers,
                                    data=json.dumps(logs), timeout=10)
        if response.status_code == 201:
            logging.info(f'Logs uploaded successfully')
            with self.db:
                self.db.delete_done(clogs, ulogs)


if __name__ == "__main__":
    logging.basicConfig(format='%(asctime)s - monitor:%(levelname)s - %(message)s', level=logging.DEBUG)
    Monitor().run()
