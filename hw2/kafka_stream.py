import json
from datetime import datetime
from kafka import KafkaProducer
from pywikibot.comms.eventstreams import EventStreams


def get_stream(stream_date):
    stream = EventStreams(
        streams=["recentchange", "revision-create"], since=stream_date
    )
    stream.register_filter(
        server_name=["en.wikipedia.org", "de.wikipedia.org"], type="edit"
    )
    return stream


def extract_record(change):
    record = {
        "id": change["id"],
        "title": change["title"].replace(",", ""),
        "user": change["user"].replace(",", ""),
        "bot": change["bot"],
        "length": change["length"]["new"] - change["length"]["old"],
        "wiki": change["wiki"].replace(",", ""),
        "timestamp": datetime.fromtimestamp(change["timestamp"]).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "minor": change["minor"],
        "comment": change["comment"].replace(",", ""),
    }
    return record


def main():
    producer = KafkaProducer(
        bootstrap_servers="localhost:9092",
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    stream_date = "20241025"

    stream = get_stream(stream_date)
    for change in stream:
        try:
            record = extract_record(change)
            producer.send("wikipedia-edits", record)
        except Exception as e:
            print(f"Error processing change: {e}")
            continue


if __name__ == "__main__":
    main()
