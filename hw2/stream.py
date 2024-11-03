import os
import sys

os.environ["PYWIKIBOT_NO_USER_CONFIG"] = "1"

import argparse
import json
import socket
from datetime import datetime
from pywikibot.comms.eventstreams import EventStreams


def get_stream(stream_date):
    stream = EventStreams(streams=["recentchange", "revision-create"], since=stream_date)
    stream.register_filter(server_name=["en.wikipedia.org", "de.wikipedia.org"], type="edit")
    return stream


def extract_record(change):
    record = {
        "id": change["id"],
        "title": change["title"].replace(",", ""),
        "user": change["user"].replace(",", ""),
        "bot": change["bot"],
        "length": change["length"]["new"] - change["length"]["old"],
        "wiki": change["wiki"].replace(",", ""),
        "timestamp": datetime.fromtimestamp(change["timestamp"]).strftime("%Y-%m-%d %H:%M:%S"),
        "minor": change["minor"],
        "comment": change["comment"].replace(",", "")
    }
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("date", help="Enter date for edit stream (YYYYMMDD)", type=str, default="20200101")
    args = parser.parse_args()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('localhost', 5050))
        s.listen(1)
        conn, addr = s.accept()

        with conn:
            print('Connected by', addr)
            stream = get_stream(args.date)
            for change in stream:
                try:
                    record = extract_record(change)
                    record_str = json.dumps(record) + '\n'
                    conn.sendall(record_str.encode('utf-8'))
                except Exception as e:
                    print(f"Error processing change: {e}")
                    continue


if __name__ == "__main__":
    sys.argv = [sys.argv[0], '20241025']
    main()

#%%
