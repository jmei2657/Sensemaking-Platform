# boarded.py
import os
import uuid
import calendar
import time
import billboard
import random
import json
import glob
import boto3
import psycopg2
from datetime import datetime, timezone
from botocore.exceptions import ClientError

target_artists = ["Taylor Swift", "Blackpink", "SZA", "Beyonce", "Kendrick Lamar"] # any target artists we care about
months = ["January","Feburary","March","April","May","June","July","August","September","October","November","December"]

# Config
AWS_REGION     = "us-east-1"
DB_SECRET_NAME = "DB"
CUTOFF_DATE    = datetime(2012, 1, 1, tzinfo=timezone.utc) # it really would be better if we had it go back farther... 
SLEEP_SECONDS  = 2


def get_secret(secret_name: str, region_name: str = AWS_REGION) -> dict:
    """
    AWS Secrets
    """
    session = boto3.session.Session()
    client = session.client("secretsmanager", region_name=region_name)

    try:
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response["SecretString"])
    except ClientError as e:
        print("Failed to get secret:", e)
        raise e

def setup_database():
    """
    Sets up DB connection and creates a new billboard table (if there isn't one there already)
    """
    creds = get_secret(DB_SECRET_NAME)
    conn = psycopg2.connect(
        dbname=creds['dbname'],
        user=creds['user'],
        password=creds['password'],
        host=creds['host'],
        port=creds['port']
    )
    cur = conn.cursor()

    print("Successfully connected to database.")

    create_table_query = """
        CREATE TABLE IF NOT EXISTS billboard (
            uuid UUID PRIMARY KEY,
            file TEXT,
            weekDate TEXT,
            title TEXT,
            artist TEXT,
            rank INTEGER,
            peakPos INTEGER,
            lastPos INTEGER,
            weeks INTEGER
        );
        """
    cur.execute(create_table_query)
    conn.commit()
    print("Billboard table created or verified.")

    # Optional: print existing number of rows for debugging
    cur.execute("SELECT COUNT(*) FROM billboard;")
    count = cur.fetchone()[0]
    print(f"Existing already in DB: {count}")

    cur.close()
    conn.close()

def insert_target_billboard_stats_from_json(folder_path="./data/"):
    """
    Takes the refined chart data (containing all entries for all artists specified in target_artists) and adds them to the database.
    """
    creds = get_secret(DB_SECRET_NAME)
    conn = psycopg2.connect(
        dbname=creds["dbname"],
        user=creds["user"],
        password=creds["password"],
        host=creds["host"],
        port=creds["port"]
    )
    cur = conn.cursor()

    insert_query = """
        INSERT INTO billboard (uuid, file, weekDate, title, artist, rank, peakPos, lastPos, weeks)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (uuid) DO NOTHING;
    """ # Note: Some values should be ints (rank, peakPos, lastPos, weeks) but it seems to work fine if set to %strings?
    match_files = glob.glob(f"{folder_path}/*_artist_matches.json")     # puts each year(s) refined target artists JSON files into a list
    total_inserted = 0

    for match_file in match_files:
        with open(match_file, "r") as f:
            try:
                matches = json.load(f)
            except json.JSONDecodeError:
                print(f"Bad JSON! {match_file}")
                continue

        for entry in matches:               # adding entries into the DB
            cur.execute(insert_query, (
                entry.get("uuid"),
                entry.get("file"),
                entry.get("weekDate"),
                entry.get("title"),
                entry.get("artist"),
                entry.get("rank"),
                entry.get("peakPos"),
                entry.get("lastPos"),
                entry.get("weeks")
            ))
            total_inserted += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"Inserted {total_inserted} rows into table.")

def georgito():
    # Respect Georgito.
    setup_database()
    insert_target_billboard_stats_from_json()

def get_saturdays(year, month):
    """
    Finds and returns all the Saturdays for the given month and year.
    Saturday is the day when the Billboard Chart updates/refreshes, so this is where we want to track changes.
        year: int
        month: int
    Returns:
        saturdays: list of strings (which are ints)
    """
    cal = calendar.Calendar()
    saturdays = []

    for week in cal.monthdayscalendar(year, month):
        saturday = week[calendar.SATURDAY]  
        if saturday != 0:                               # Make sure that this week's Saturday falls within the current month!!!
            saturdays.append(f"{saturday:02}")
    return saturdays

def fix_chart(chart):
    """
    Takes in the Chart object (the Billboard Top 100 songs for a week)
    and returns all the date and song entries as a 2-part dictionary;
        date: the date/week
        entries: all the top 100 songs for that week
    """
    bleh = chart.json()
    if isinstance(bleh, str):   # Convert to raw JSON string
        bleh = json.loads(bleh) # Convert to Python Dictionary
    return {
        "date": bleh.get("date"),
        "entries": bleh.get("entries", [])
    }

def scrape():
    """
    Using billboard.py, scrapes the billboard top 100 charts for each week of each month of the year(s) given
    """
    for yoyo in range(CUTOFF_DATE.year,datetime.now().year+1):
        monthly_data = {}
        print(f"Pulling the Billboard Top 100 Charts for {yoyo}:")
        for month in range(1, 13):
            month_str = f"{month:02}"
            print(f"Processing {months[month-1]}...")

            if not os.path.exists(f"./data/temp/{yoyo}_billboard_month_{month_str}.json"):

                days_to_chart = get_saturdays(yoyo, month)    # Days when the Billboard Chart gets updated
                refined_data = []                             # List that temporarily holds all of the Billboard Charts for the current month

                for day in days_to_chart:
                    date_str = f"{yoyo}-{month_str}-{day}"  # Ensures that the Billboard Chart request is always properly formatted (YYYY-MM-DD)

                    chart = billboard.ChartData('hot-100', date=date_str)       # The chart object is a raw JSON string that isn't very useful, hence fix_chart

                    fixed = fix_chart(chart)
                    refined_data.append(fixed)

                    print(f"Fetched data for {date_str}.")
                    time.sleep(random.randint(1, 2))  # Pause to avoid IP banning. Makes this thing incredibly slow, but realistically you'd only have to use this once.
                    print('\n')

                monthly_data[month_str] = refined_data

                with open(f"./data/temp/{yoyo}_billboard_month_{month_str}.json", "w") as f:     # Save the month's data to a single JSON file
                    json.dump(refined_data, f, indent=2)
            
            print(f"Finished processing {months[month-1]}!")

        print(f"Billboards successfully charted for {yoyo}.")

def filter():
    """
    From the scraped billboard charts data, return information only relevant to the artists specified in target_artists as a JSON;
    This will be useful when guaging things like popularity of a song, relative to songs from the same or other artist(s).
    """
    matches = []
    json_files = []
    weeks_data = []
    for bogo in range(CUTOFF_DATE.year,datetime.now().year):
        fred = glob.glob(f"./data/temp/{bogo}_billboard_month_*.json")     # Monthly billboard chart data is stored in /data/temp
        json_files.extend(fred)                                                        # List of relevant "matches" (entries)
    for file_path in json_files:                                            # Parse and load all entries into weeks_data
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                weeks_data = json.load(f)
            except json.JSONDecodeError as e:
                print(f"Fail to parse {file_path}: {e}")
                continue


    for week in weeks_data:                                                         # Check and make sure the JSON formatting is correct
        week_date = week.get("date") or week.get("weekDate") or "unknown_date"      # ^
        entries = week.get("entries", [])
        if not isinstance(entries, list):
            print(f"Got bad in {file_path}")
            continue

        for entry in entries:                                                       # Checks all entries for artists in target_artists list
            artist = entry.get("artist", "")
            if any(target in artist for target in target_artists):                  # If an artist(s) are found within the charts, 
                matches.append({              
                    "uuid": str(uuid.uuid4()),                                      # then include that entry in output (filtered JSON))
                    "file": file_path,
                    "weekDate": week_date,
                    "title": entry.get("title"),
                    "artist": artist,
                    "rank": entry.get("rank"),
                    "peakPos": entry.get("peakPos"),
                    "lastPos": entry.get("lastPos"),
                    "weeks": entry.get("weeks")
                })

        output_path = f"./data/{bogo}_artist_matches.json"  

        if not os.path.exists(output_path):                                 # Skips writing file if it already exists
                                                                            # Note: If you change/add/remove target_artists, make sure you rm *_artist_match.json
                                                                            #       because this only checks if the file exists, not if the contents are different,
                                                                            #       which they would be since you've selected different target_artists! Be careful!
            with open(output_path, "w", encoding="utf-8") as out_f:         
                json.dump(matches, out_f, indent=2, ensure_ascii=False)     # Export JSON file(s) to /data

if __name__ == "__main__":
    scrape()
    filter()
    georgito()

# EOF
