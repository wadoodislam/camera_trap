import json
from datetime import datetime, timedelta

import requests

from utils import Constants, get_disk_usage, format_logs


class Monitor(Constants):

    def __init__(self):
        super(Monitor, self).__init__()
        self.fetch_params()

        with self.db:
            self.db.create_tables()

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
        except Exception:
            pass

    def send_logs(self):
        with self.db:
            clogs, ulogs = self.db.get_pending_logs()

        logs = format_logs(clogs, ulogs)
        response = requests.request("POST", self.logs_url, headers=self.headers,
                                    data=json.dumps(logs), timeout=10)
        if response.status_code == 201:
            with self.db:
                self.db.delete_done(clogs, ulogs)


if __name__ == "__main__":
    Monitor().run()
