
#test that you can connect to db

import boto3
from botocore.exceptions import ClientError
import json
import psycopg2


def get_secret(secret_name):
    region_name = "us-east-1"

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        raise e

    secret = get_secret_value_response['SecretString']
    secret_dict = json.loads(secret)

    return secret_dict


def connect_and_query():
    user, password, host, port, dbname = get_secret()

    try:
        conn = psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password,
            host=host,
            port=port
        )
        print(" Connected to database.")

        cur = conn.cursor()
        cur.execute("SELECT NOW();")
        result = cur.fetchone()
        print(" test Query Current time from DB:", result)

        cur.close()
        conn.close()

    except Exception as e:
        print("Failed to connect or query:", e)


if __name__ == "__main__":
    connect_and_query()
