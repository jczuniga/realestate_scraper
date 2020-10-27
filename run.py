from scraper import Scraper
from util.gen_util import load_json_config

import argparse

"""
code meta found in __init__.py top level code directory
Usage:
    python run.py -f <config_filename> -o <output_filename>  [Optional]
    Sample:
        python run.py -f realestateau -o realestateau.csv
        ^ command saves scraped contents into csv file named realestateau.csv

    Another sample:
        python run.py --file realestate --keyword melbourne --max_pages 10 --output scrape.csv

"""


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--file", "-f", help="name of config file to fetch", required=True)
    parser.add_argument("--output", "-o", help="save filename", required=False)
    parser.add_argument("--keyword", "-k", help="keyword search", required=False)
    parser.add_argument("--max_pages", "-m", help="maximum number of pagination crawling", required=False)
    args = parser.parse_args()

    config_file = load_json_config(args.file)

    if args.output:
        config_file['scraper_config']['outfile'] = args.output

    if args.keyword:
        config_file['scraper_config']['keyword'] = args.keyword

    if args.max_pages:
        config_file['scraper_config']['max_num_of_pages'] = args.max_pages

    # Instantiate Scraper object and pass keyword args dict
    scrape = Scraper(**config_file['scraper_config'])
    links = scrape.paging_task()
    scrape.quit_browser()  # Explicit quitting of browser after scraping


if __name__ == '__main__':
    main()
