import sqlite3
from datetime import datetime


class SQLite:
    _DEFAULT_TIMEOUT = 60 * 60  # 1hr

    def __init__(self, db_path: str, timeout: float = _DEFAULT_TIMEOUT):
        self._db_path = db_path
        self._db_conn = None
        self._timeout = timeout

    def __enter__(self):
        self._db_conn = sqlite3.connect(self._db_path, timeout=self._timeout)
        self._db_conn.isolation_level = None
        self._db_conn.execute("PRAGMA locking_mode = EXCLUSIVE;")
        self._db_conn.execute("BEGIN EXCLUSIVE;")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._db_conn.execute("COMMIT;")
        self._db_conn.close()
        self._db_conn = None

    def create_tables(self):
        self._db_conn.execute('CREATE TABLE IF NOT EXISTS capture_logs(datestamp TEXT, log_type TEXT , pending INT, message TEXT)')
        self._db_conn.execute('CREATE TABLE IF NOT EXISTS upload_logs(datestamp TEXT, log_type TEXT, pending INT, message TEXT)')

    def data_entry(self, table_name, values):
        values_csv = ','.join(values)
        self._db_conn.execute(f'INSERT INTO {table_name} VALUES({values_csv})')

    def get_pending_logs(self, ):
        c = self._db_conn.cursor()
        c.execute('SELECT * FROM capture_logs WHERE pending==1')
        capture_logs = [row for row in c.fetchall()]
        c.execute('SELECT * FROM upload_logs WHERE pending==1')
        upload_logs = [row for row in c.fetchall()]
        return capture_logs, upload_logs

    def mark_done(self, clogs, ulogs):
        c = self._db_conn.cursor()
        cdates = ','.join([f'"{row[0]}"' for row in clogs])
        c.execute(f'UPDATE capture_logs SET pending = 0 WHERE datestamp IN ({cdates})')
        udates = ','.join([f'"{row[0]}"' for row in ulogs])
        c.execute(f'UPDATE upload_logs SET pending = 0 WHERE datestamp IN ({udates})')
        return


if __name__ == '__main__':
    database = SQLite("local.db", 5)
    with database:
        database.create_tables()
        database.data_entry('capture_logs', [f'"{datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}"', '"EVENT_CAPTURED"', '1', '"some thing about log"'])
        database.data_entry('upload_logs', [f'"{datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}"', '"CHECKED_MOTION"', '1', '"some thing about log"'])
        clogs, ulogs = database.get_pending_logs()
        # database.mark_done(clogs, ulogs)
        print('acquired lock!')
