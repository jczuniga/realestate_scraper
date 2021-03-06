import logging
import sys
import csv
import os
import json
from lxml.html import fromstring
import requests
from itertools import cycle
import traceback
import re


# module for obtaining a list of free proxy servers from free-proxy-list.net
def get_proxies() -> list:
    url = 'https://free-proxy-list.net/'
    response = requests.get(url)
    parser = fromstring(response.text)
    proxies = list()
    for i in parser.xpath('//tbody/tr')[:10]:
        if i.xpath('.//td[7][contains(text(),"yes")]'):
            proxy = ":".join([i.xpath('.//td[1]/text()')[0], i.xpath('.//td[2]/text()')[0]])
            proxies.append(proxy)
    return proxies


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
    with open(outfile, 'a', encoding="utf8") as writeFile:
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


# function for converting string number to int
def convert_str_to_number(x: str) -> list:
    try:
        extracted_str = re.findall(r'[\d.,K,k,M,m]+', x, re.IGNORECASE)
        cleaned_str = [r.strip().replace(",", "") for r in extracted_str]
        total_stars = 0
        num_map = {'K': 1000, 'M': 1000000, 'B': 1000000000}
        converted = []
        if len(cleaned_str) > 1:
            for x in cleaned_str:
                if x.isdigit():
                    converted.append(int(x))
                else:
                    if len(x) > 1:
                        total_stars = int(x[:-1]) * num_map.get(x[-1].upper(), 1)
                        converted.append(total_stars)
        else:
            if ''.join(cleaned_str).isdigit():
                converted.append(int(''.join(cleaned_str)))
            else:
                if len(''.join(cleaned_str)) > 1:
                    total_stars = int(''.join(cleaned_str)[:-1]) * num_map.get(''.join(cleaned_str)[-1].upper(), 1)
                    converted.append(total_stars)

        return converted

    except ValueError as ve:

        return []
