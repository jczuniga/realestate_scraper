from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.proxy import Proxy, ProxyType
from selenium.webdriver.support.expected_conditions import staleness_of
from selenium.common.exceptions import (
    NoSuchElementException,
    ElementNotInteractableException,
    TimeoutException
)
from selenium.webdriver.firefox.options import Options
from util.gen_util import (
    set_logging,
    store_to_csv,
    get_proxies
)
from typing import (List, Dict)

import time
import itertools
import logging
import sys
import re
import random
import os
import json


# By default, logging is set to stdout print in terminal
# this can be changed by manually setting the config in gen_util
set_logging()
log = logging.getLogger(__name__)


class Scraper(object):
    def __init__(self, **kwargs: dict) -> None:
        """Instantiate Scraper object for selected config.

        Parameters
        ----------
        **kwargs : dict
            Unpacked keyword arguments from scraper config file

            login_url (Optional) -- login url/endpoint to access auth interface
            main_url (Required) -- primary url to collect pagination links (if applicable)
            xpath (Required)-- collection of xpath selectors expressed in dict/json format
            proxy (Optional) -- to be used when proxy is necessary in scraping, module for creation
            keyword (Optional) -- indicated keyword for search feature
            auth (Optional) -- credentials for login interface
            headless (Optional) -- use headless firefox
            log_path (Optional)-- file path of selenium logging
            wait_between (Optional) -- scraper timeout
            disable_images (Optional) -- toggle True to enable faster scraping, might not work with specific sites
            user_agent (Optional) -- toggles defined user agent for sending requests
            browser_time (Optional) -- sets defined requests duration
            outfile (Optional) -- path to saved scraped contents
            file_headers (Optional) -- headers in csv file

        Returns
        -------
        None

        """
        # Main browser attributes
        self.login_url: str = kwargs.get('login_url', None)
        self.main_url = kwargs.get('main_url')
        self.xpath: dict = kwargs.get('xpath')
        self.proxy: str = kwargs.get('proxy', None)
        self.keyword: str = kwargs.get('keyword', None)
        self.auth: dict = kwargs.get('auth', None)
        self.headless: str = kwargs.get('headless', False)
        self.verbose: bool = kwargs.get('verbose', True)
        self.log_path: str = kwargs.get('log_path', None)
        self.wait_between: list = kwargs.get('wait_between', [3, 5])
        self.disable_images: bool = kwargs.get('disable_images', False)
        self.user_agent: str = kwargs.get('user_agent', None)
        self.browser_timeout: int = kwargs.get('browser_timeout', None)
        self.options = Options()

        # attributes for storing to csv file
        # self.store: bool = kwargs.get('store', False)
        self.outfile: str = kwargs.get('outfile', None)
        self.file_headers: list = kwargs.get('file_headers', None)

        self.driver: webdriver = self._initialize_webdriver()
        self.options = Options()

        self.paging_task_links = []
        self.scraped_data = []

        self.max_num_of_pages: str = kwargs.get('max_num_of_pages', 1000)

        log.info(f"Initializing scraper with config: {self.__dict__}")

        if self.headless is True:
            self.options.add_argument("--headless")
            log.info("Setting headless config...")

    def _initialize_webdriver(self) -> webdriver:
        firefox_profile = webdriver.FirefoxProfile()
        if self.disable_images is True:
            if self.user_agent is not None:
                firefox_profile.set_preference('general.useragent.override', self.user_agent)
            firefox_profile.set_preference('permissions.default.image', 2)
            firefox_profile.set_preference('dom.ipc.plugins.enabled.libflashplayer.so', 'false')
            log.info('Image loading disabled..')

            if self.proxy is not None:
                proxy_ip = random.choice(get_proxies())
                self.proxy = Proxy({
                    'proxyType': ProxyType.MANUAL,
                    'httpProxy': proxy_ip,
                    'ftpProxy': proxy_ip,
                    'sslProxy': proxy_ip,
                    'noProxy': ''
                })

                log.info(f"Using proxy address {proxy_ip}")
                time.sleep(2)
            web_driver = webdriver.Firefox(
                firefox_options=self.options,
                firefox_profile=firefox_profile,
                log_path=None if self.log_path is None else self.log_path,
                proxy=self.proxy
            )

            if self.browser_timeout is not None:
                web_driver.set_page_load_timeout(self.browser_timeout)
                web_driver.set_script_timeout(self.browser_timeout)

            return web_driver

        else:
            if self.user_agent is not None:
                firefox_profile.set_preference("general.useragent.override", self.user_agent)

            if self.proxy is not None:
                proxy_ip = random.choice(get_proxies())
                self.proxy = Proxy({
                    'proxyType': ProxyType.MANUAL,
                    'httpProxy': proxy_ip,
                    'ftpProxy': proxy_ip,
                    'sslProxy': proxy_ip,
                    'noProxy': ''
                })

                log.info(f"Using proxy address {proxy_ip}")
                time.sleep(2)

            web_driver = webdriver.Firefox(
                firefox_options=self.options,
                firefox_profile=firefox_profile,
                log_path=None if self.log_path is None else self.log_path,
                proxy=self.proxy
            )
            if self.browser_timeout is not None:
                web_driver.set_page_load_timeout(self.browser_timeout)
                web_driver.set_script_timeout(self.browser_timeout)

            return web_driver


    def wait_for_page_to_load(self, timeout=10):
        try:
            element_present = EC.presence_of_element_located((By.ID, 'main'))
            WebDriverWait(self.driver, timeout).until(element_present)
        except TimeoutException:
            log.error("Timed out waiting for page to load")
        finally:
            log.info("Page loaded")

    def quit_browser(self):
        self.driver.quit()

    # First pagination. Only pass-on argument is login_url or main_url
    def paging_task(self) -> list:
        current_url = ""
        try:
            if self.login_url is not None:
                self.driver.get(self.login_url)
                time.sleep(2)
                self.driver.find_element_by_xpath(
                    self.xpath['uname_input_xpath']
                ).send_keys(self.auth.split(':')[0])

                self.driver.find_element_by_xpath(
                    self.xpath['pword_input_xpath']
                ).send_keys(self.auth.split(':')[1])
                time.sleep(2)

                self.driver.find_element_by_xpath(
                    self.xpath['submit_xpath']
                ).click()

                if self.main_url is not None:
                    self.driver.get(self.main_url)
                    current_url = self.driver.current_url
                else:
                    pass
            else:
                self.driver.get(self.main_url)
                time.sleep(2)
                if self.keyword is not None:
                    self.driver.find_element_by_xpath(
                        self.xpath['search_xpath']
                    ).send_keys(self.keyword)
                    time.sleep(2)
                self.driver.find_element_by_xpath(
                    self.xpath['search_submit_xpath']
                ).click()
                self.wait_for_page_to_load()

                current_url = self.driver.current_url

            # For Pagination

            for i in range(int(self.max_num_of_pages)):
                url_list = [
                    url.get_attribute('href') for url in self.driver.find_elements_by_xpath(
                        self.xpath['link_xpath']
                    )
                ]
                for url in url_list:
                    self.get_content(link=url)
                    # log.info("Navigating back...")
                    # self.driver.back()
                    # self.paging_task_links.append(url_list)

                self.driver.get(current_url)
                try:
                    self.driver.find_element_by_xpath(self.xpath['next_xpath']).click()
                    a, b = self.wait_between
                    wait_between = random.randint(a, b)
                    log.info(f"Waiting {wait_between} seconds in between loads..")
                    time.sleep(wait_between)
                    current_url = self.driver.current_url
                except NoSuchElementException or ElementNotInteractableException as ee:
                    log.info('No next page found. End of pagination..')
                    break

            return self.paging_task_links

        except TimeoutException as te:
            log.info(f'Cannot access url. Error:{te}')
            log.info('Quitting Browser session..')
            self.quit_browser()

    # Extract content from final page
    def get_content(self, link: str) -> None:
        data = {}

        try:
            self.driver.get(link)

            data['address_url'] = self.driver.current_url
            try:
                data['address_listing_price'] = self.driver.find_element_by_xpath(
                    self.xpath['address_listing_price_xpath']
                ).text
            except NoSuchElementException as e:
                data['address_listing_price'] = None

            try:
                data['address_bedrooms'] = int(
                    re.sub(
                        r'"', '', self.driver.find_element_by_xpath(self.xpath['address_bedrooms_xpath']).text
                )
            )
            except NoSuchElementException as e:
                data['address_bedrooms'] = None

            try:
                data['address_bathrooms'] = int(
                    re.sub(
                        r'"', '', self.driver.find_element_by_xpath(self.xpath['address_bathrooms_xpath']).text
                )
            )
            except NoSuchElementException as e:
                data['address_bathrooms'] = None

            try:
                data['address_car_spaces'] = int(
                    re.sub(
                        r'"', '', self.driver.find_element_by_xpath(self.xpath['address_car_spaces_xpath']).text
                )
            )
            except NoSuchElementException as e:
                data['address_car_spaces'] = None

            try:
                data['address_property_type'] = self.driver.find_element_by_xpath(
                    self.xpath['address_property_type_xpath']
                ).text
            except NoSuchElementException as e:
                data['address_property_type'] = None

            try:
                data['address_description'] = self.driver.find_element_by_xpath(
                    self.xpath['address_description_xpath']
                ).text
            except NoSuchElementException as e:
                data['address_description'] = None

            try:
                data['address_full_address'] = self.driver.find_element_by_xpath(
                    self.xpath['address_full_address_xpath']
                ).text
            except NoSuchElementException as e:
                data['address_full_address'] = None

            try:
                data['property_size'] = float(
                    "".join(
                        re.findall(
                            r'[0-9]+', self.driver.find_element_by_xpath(self.xpath['property_size_xpath']).text
                        )
                    )
                )
            except NoSuchElementException as e:
                data['property_size'] = None

            try:
                distances = self.driver.find_elements_by_xpath(
                    self.xpath['property_distance_from_schools_aggregate_xpath']
                )
                dst_agg = list()
                for distance in distances:
                    dst = re.sub(r'km', '', distance.text)
                    dst_agg.append(float(dst))
                data['property_distance_from_schools_aggregate'] = sum(dst_agg)
            except NoSuchElementException as e:
                data['property_distance_from_schools_aggregate'] = None


            log.info(json.dumps(
                data,
                sort_keys=True,
                indent=4
            ))

            # self.scraped_data.append(data)

            if self.outfile is not None:
                store_to_csv(
                    data=data,
                    outfile=self.outfile,
                    headers=self.file_headers
                )

            a, b = self.wait_between
            wait_between = random.randint(a, b)
            log.info(f"Waiting {wait_between} seconds in between loads..")
            time.sleep(wait_between)

        except TimeoutException as te:
            log.info('Browser timeout. Quitting session..')
            self.quit_browser()
