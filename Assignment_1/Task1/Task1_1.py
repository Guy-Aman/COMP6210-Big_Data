from pymongo import MongoClient
import re
import csv

# *******************************************
# Initial setup :
#   - connect to MongoDB
#   - importing CSV into MongoDB
# *******************************************

client = MongoClient("mongodb://localhost:27017/")
# Delete the database if it exists, then create a fresh one
client.drop_database("Assignment_1")
db = client["Assignment_1"]
fifa_players = db["FIFA_players"]

file_path = "../FIFA2026_Player/data.csv"

with open(file_path, newline="", encoding="utf-8-sig") as file:
    reader = csv.DictReader(file)
    records = [dict(row) for row in reader]

# remove any intially inserted data
fifa_players.delete_many({})
if records:
    fifa_players.insert_many(records)


print(f"| Insertion | Inserted {len(records)} records into '{fifa_players.name}' ")

# creating a set of all the documents in the database
documents_set = list(fifa_players.find())

# STEP 1 field list
STRING_FIELDS_LIST = [
    "player_name",
    "nationality",
    "club",
    "position",
    "competition",
    "season",
]

# STEP 3 field list
IDENTIFIER_FIELDS = ["player_name", "competition", "match_id"]

# STEP 4 field list
INVALID_NUMERIC_VALUE_FIELDS = [
    "market_value_eur_m",
    "minutes_played",
    "goals",
    "assists",
    "shots_on_target",
    "tackles",
    "match_rating",
    "fouls_committed",
]

# STEP 5 field list
OUTPUT_FIELDS = [
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


# *******************************************
# Storing the data needed before cleaning happens
# - the total number of records before cleaning
# - the number of records with nationality = "Unknown" before cleaning
# - the number of records with missing market_value_eur_m before cleaning
# *******************************************

total_records_before_cleaning = len(documents_set)
unknown_nationality_count_before = sum(
    1 for document in documents_set if document.get("nationality") == "Unknown"
)
missing_market_value_count_before = sum(
    1 for document in documents_set if document.get("market_value_eur_m") in (None, "")
)


print(
    f"| Count | Total document count before cleaning: {total_records_before_cleaning}"
)
print(
    f"| Count | Number of records with Unknown nationality before cleaning: {unknown_nationality_count_before}"
)
print(
    f"| Count | Number of records with missing market value before cleaning: {missing_market_value_count_before}"
)

documents_set = []
for row in fifa_players.find():
    documents_set.append(row)


# *******************************************
# Rule 1: string standardization
# *******************************************
def standardize_string(documents):
    changed_count = 0
    for document in documents:
        for field in STRING_FIELDS_LIST:
            field_value = document.get(field)
            if isinstance(field_value, str):
                edited_value = re.sub(r"\s+", " ", field_value.strip())
                document[field] = edited_value
                if edited_value != field_value:
                    changed_count += 1

    print(f"String standardized for {changed_count} records.")
    return documents, changed_count


# *******************************************
# Rule 2: competition standardization
# *******************************************
def standardize_competition(documents):
    standard_competition_array = [
        "FIFA World Cup 2026",
        "Champions League",
        "Domestic Cup",
        "World Cup Qualifiers",
        "League",
    ]

    std_name_count = 0

    def capitalize_first(array):
        nonlocal std_name_count
        if array[0].lower() == "fifa":
            array = [
                word.upper() if word.lower() == "fifa" else word.capitalize()
                for word in array
            ]
        else:
            array = [word.capitalize() for word in array]
        joined_word = " ".join(array)
        std_name_count += 1
        return joined_word

    for document in documents:
        competition = document.get("competition")
        if competition and competition not in standard_competition_array:
            splitted_words_array = document.get("competition").split(" ")
            document["competition"] = capitalize_first(splitted_words_array)

    return documents, std_name_count


# ***********************************************
# Rule 3: Remove records with missing identifiers
# ***********************************************
def clean_missing_identifier_records(documents):
    cleaned_records = []
    missing_count = 0

    def is_missing(value):
        return value is None or (isinstance(value, str) and value.strip() == "")

    def clean_records(documents):
        nonlocal missing_count
        for document in documents:
            document_is_missing = any(
                is_missing(document.get(field)) for field in IDENTIFIER_FIELDS
            )
            if document_is_missing:
                missing_count += 1
            else:
                cleaned_records.append(document)

    clean_records(documents)
    return cleaned_records, missing_count


# ***************************************************
# Rule 4: Remove records with negative numeric values
# ***************************************************
def clean_invalid_numeric(documents):
    negative_count = 0
    cleaned = []

    for document in documents:
        has_negative = False
        for field in INVALID_NUMERIC_VALUE_FIELDS:
            if document.get(field) == "":
                continue
            if float(document.get(field)) < 0:
                has_negative = True
        if has_negative:
            negative_count += 1
        else:
            cleaned.append(document)

    return cleaned, negative_count


# *******************************************
# Rule 5: Infer Unknown nationality
# *******************************************
def filling_unknown_nationality_values(documents):
    nationality_group = {}

    for document in documents:
        nationality = document.get("nationality")
        if nationality and nationality != "Unknown":
            key = (
                document.get("player_name"),
                document.get("age"),
                document.get("club"),
            )
            if key not in nationality_group:
                # creating an empty set
                nationality_group[key] = set()
            nationality_group[key].add(nationality)

    # fixing unknown values
    fixed_document_count = 0

    for document in documents:
        if document.get("nationality") == "Unknown":
            key = (
                document.get("player_name"),
                document.get("age"),
                document.get("club"),
            )
            # in case there are no documents it returns an empty set
            players = nationality_group.get(key, set())
            if len(players) == 1:
                document["nationality"] = next(iter(players))
                fixed_document_count += 1

    return documents, fixed_document_count


# *******************************************
# Rule 6: Fill missing market_value_eur_m
# *******************************************
def fill_missing_market_value(documents):
    market_value_groups = {}

    for document in documents:
        if document.get("market_value_eur_m") not in ("", None):
            key = (document.get("competition"), document.get("player_name"))
            if key not in market_value_groups:
                market_value_groups[key] = []
            market_value_groups[key].append(float(document.get("market_value_eur_m")))

    filled_count = 0
    for document in documents:
        value = document.get("market_value_eur_m")
        if value in (None, ""):
            key = (document.get("competition"), document.get("player_name"))
            candidates = market_value_groups.get(key, [])
            if len(candidates) > 0:
                average = sum(candidates) / len(candidates)
                document["market_value_eur_m"] = round(average, 4)
                filled_count += 1
            else:
                document["market_value_eur_m"] = "NA"

    return documents, filled_count


# *******************************************
# Running the pipeline
# *******************************************
records, standardized_count = standardize_string(documents_set)
print(f"| Rule 1 | {standardized_count} records standardized ")

records, standardized_competition_name_count = standardize_competition(records)
print(
    f"| Rule 2 | {standardized_competition_name_count} competition names standardized"
)

records, missing_identifier_count = clean_missing_identifier_records(records)
print(
    f"| Rule 3 | {missing_identifier_count} records removed with missign identifiers. {len(records)} records remaining."
)

records, negatives_count = clean_invalid_numeric(records)
print(
    f"| Rule 4 | {negatives_count} records removed with negative values. {len(records)} records remaining."
)

records, nationality_fixed_count = filling_unknown_nationality_values(records)
print(
    f"| Rule 5 | {nationality_fixed_count} records fixed through nationality inference."
)

records, market_value_filled_count = fill_missing_market_value(records)
print(
    f"| Rule 6 | {market_value_filled_count} records filled for missing market value."
)

final_number_of_records = len(records)
print(f"| Count | {final_number_of_records} records remaining after cleaning.")

# *******************************************
# Storing cleaned records in MongoDB
# *******************************************

cleaned_records_collection = db["FIFA_players_cleaned"]
cleaned_records_collection.delete_many({})
cleaned_docs = []
for record in records:
    new_dict = {}
    for key, value in record.items():
        if key != "_id":
            new_dict[key] = value
    cleaned_docs.append(new_dict)

if cleaned_docs:
    cleaned_records_collection.insert_many(cleaned_docs)
print(
    f"| Insertion | inserted {len(cleaned_docs)} record into '{cleaned_records_collection.name}'"
)


# **************************************************
# Step 3 - 1: Extracting fields into player_data.txt
# **************************************************
with open("player_data.txt", "w", newline="") as player_data:
    writer = csv.writer(player_data)
    for record in records:
        writer.writerow([record.get(field, "NA") for field in OUTPUT_FIELDS])
print(f"| Output | Wrote {len(records)} rows into player_data.txt")

# **************************************************
# Step 3 - 2: Preparing the cleaning report
# **************************************************
with open("cleaning_report.txt", "w") as cleaning_report:
    cleaning_report.write(
        f"Total records before cleaning: {total_records_before_cleaning}\n"
    )
    cleaning_report.write(f"Total records after cleaning: {final_number_of_records}\n")
    cleaning_report.write(
        f"Records with nationality = 'Unknown' before cleaning: {unknown_nationality_count_before}\n"
    )
    cleaning_report.write(
        f"Records with missing market_value_eur_m before cleaning: {missing_market_value_count_before}\n"
    )
    cleaning_report.write(
        f"Records for which string fields were standardized: {standardized_count}\n"
    )
print("--------- Cleaning report Prepared ---------")
