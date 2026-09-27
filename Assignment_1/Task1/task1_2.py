from mrjob.job import MRJob
from mrjob.step import MRStep
from mrjob.protocol import RawValueProtocol
import csv

FIELDS = [
    "player_name",
    "nationality",
    "club",
    "position",
    "market_value_eur_m",
    "competition",
    "match_id",
    "minutes_played",
    "goals",
    "assists",
    "match_rating",
]


class MRSortRecordsByCompetition(MRJob):
    OUTPUT_PROTOCOL = RawValueProtocol

    def mapper(self, _, line):
        row = next(csv.reader([line]))
        record = dict(zip(FIELDS, row))
        yield record["competition"], record

    def reducer(self, competition, records):
        sorted_records = sorted(
            records, key=lambda record: (record["player_name"], int(record["match_id"]))
        )
        for record in sorted_records:
            line = ",".join(
                [competition]
                + [str(record[field]) for field in FIELDS if field != "competition"]
            )
            yield None, line


if __name__ == "__main__":
    MRSortRecordsByCompetition.run()
