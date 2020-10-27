import logging
import sys
import csv
import os
import json


# simple module to manually set logging configuration
def set_logging() -> logging:
    stdout_handler = logging.StreamHandler(sys.stdout)
    handlers = [stdout_handler]

    logger = logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s:%(name)s: %(levelname)s : %(message)s',
        handlers=handlers
    )


# CSV store util
def store_to_csv(data: dict, outfile: str, headers: list) -> None:
    with open(outfile, 'a') as writeFile:
        headers = headers
        writer = csv.DictWriter(writeFile, delimiter=',', lineterminator='\n', fieldnames=headers)
        if writeFile.tell() == 0:
            writer.writeheader()
        writer.writerow(data)


# json config loader
def load_json_config(config_file: json) -> dict:
    try:
        json_file = f"config_files/{config_file}.json"
        with open(json_file) as f:
            loaded_config = json.load(f)
            print(f"Loading config file {config_file}")

        return loaded_config

    except Exception as e:
        print(f"Error in loading config file. {e}")