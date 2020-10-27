from selenium import webdriver
from selenium.webdriver.remote.webdriver import WebDriver as RemoteWebDriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from .PatchedFirefoxProfile import PatchedFirefoxProfile
from selenium.webdriver.chrome.options import Options as ChromeOptions
from typing import (List, Dict, Union, Any)

from lxml import html, etree
import time
import socket
from shutil import copyfile
import os
import sys
import subprocess
import re
import pkg_resources
from pyvirtualdisplay import Display
import random
import string
import numpy as np
import csv
import shutil


from base64 import b64encode
import logging

log = logging.getLogger(__name__)

AVAILABLE_PROXIES = {}


def get_headless_display():
    display = None
    try:
        display = Display(visible=0, size=(1000, 1000))
        display.start()
    except Exception as e:
        log.warning("Unable to start py-virtual-display.")
        if display is not None:
            display.stop()
    return display


class HeadlessFirefox(webdriver.Firefox):

    def __init__(self, **kwargs: dict) -> webdriver:
        self.display = get_headless_display()
        super(HeadlessFirefox, self).__init__(**kwargs)

    def quit(self):
        super(HeadlessFirefox, self).quit()
        self.stop_display()

    def stop_display(self):
        if self.display is not None:
            try:
                self.display.stop()
                log.info("Browser quit and display stopped.")
            except Exception as e:
                pass


class CleanRemoteWebdriver(RemoteWebDriver):

    def __init__(self, browser_profile: dict = None, **kwargs: dict) -> webdriver:
        self.profile = browser_profile
        RemoteWebDriver.__init__(self, browser_profile=browser_profile, **kwargs)

    def stop_client(self):
        if self.profile.profile_dir:
            log.debug("Removing profile tmp dir %s" % self.profile.profile_dir)
            shutil.rmtree(self.profile.profile_dir)



def get_firefox(proxy_type: str,
                use_grid: bool = True,
                options: dict = None,
                user_agent: str = 'default',
                headless: bool = False,
                local_fallback: bool = True,
                proxy_creds: dict = None,
                override_proxy: dict = None,
                override_grid_host: dict = None
                ) -> webdriver:

    if not use_grid:
        if sys.version_info >= (3, 7):
            output = subprocess.run(["geckodriver", "--version"], capture_output=True).stdout.decode('utf8')
        else:
            process = subprocess.Popen(["geckodriver", "--version"], stdout=subprocess.PIPE)
            output, error = process.communicate()
        if hasattr(output, 'decode'):
            output = output.decode('utf8')
        geckodriver_version = re.search(r"geckodriver (.*)\n", output).group(1)

        assert (geckodriver_version == "0.19.0")

    profile = PatchedFirefoxProfile()
    if user_agent != 'default':
        profile.set_preference("general.useragent.override", user_agent)
    log.info("User agent: %s" % user_agent)

    if proxy_type is None:
        pass
    elif proxy_type != "tor" and proxy_type not in AVAILABLE_PROXIES:
        raise RuntimeError("Proxy type %s is not supported" % proxy_type)
    else:

        profile.add_extension(pkg_resources.resource_filename(__name__, 'proxy_auth.xpi'))

        if override_proxy is None:
            proxy = random.choice((AVAILABLE_PROXIES).split(','))
        else:
            proxy = override_proxy
        proxy_address, proxy_port = proxy.split(":")
        profile.set_preference("network.proxy.type", 1)

        if proxy_type == "tor":
            profile.set_preference("network.proxy.socks", proxy_address)
            profile.set_preference("network.proxy.socks_port", int(proxy_port))
            profile.set_preference("network.proxy.socks_remote_dns", True)
            profile.set_preference("network.proxy.socks_version", 5)
        else:
            profile.set_preference('network.proxy.ftp', proxy_address)
            profile.set_preference('network.proxy.ftp_port', int(proxy_port))
            profile.set_preference('network.proxy.ssl', proxy_address)
            profile.set_preference('network.proxy.ssl_port', int(proxy_port))
            profile.set_preference('network.proxy.http', proxy_address)
            profile.set_preference('network.proxy.http_port', int(proxy_port))

            if proxy_creds:

                if isinstance(proxy_creds, dict):
                    if "random_string" in proxy_creds and proxy_type == 'proxymesh':
                        # https://docs.proxymesh.com/article/17-controlling-ip-addresses-requests
                        fmt = "{username}:{random_string}:{password}"
                    elif "random_string" in proxy_creds and proxy_type == 'luminati':
                        # https://luminati.io/faq#integration-rotation
                        fmt = "{username}-session-{random_string}:{password}"
                    else:
                        fmt = "{username}:{password}"
                    proxy_creds = fmt.format(**proxy_creds)

                credentials = b64encode(proxy_creds.encode('ascii')).decode('utf-8')
                profile.set_preference('extensions.closeproxyauth.authtoken', credentials)

    if options and "extensions" in options:
        for extension in options['extensions']:
            log.info("Adding extension: %s" % extension)
            try:
                profile.add_extension(pkg_resources.resource_filename(__name__, extension))
            except Exception as e:
                raise

    if options and "profile" in options:
        for k, v in options["profile"].items():
            if k == "javascript.enabled" and not v:
                profile.add_extension(pkg_resources.resource_filename(__name__, 'noscript_firefox.xpi'))
            profile.set_preference(k, v)

    opts = None
    if options and "options" in options:
        opts = FirefoxOptions()
        for k, v in options["options"].items():
            opts.set_preference(k, v)

    '''
    # app_path localized
    if options and "lib_files" in options:
        app_path = get_app_path()

        for filename in options['lib_files']:
            filepath = os.path.join(app_path, "lib", filename)
            copyfile(filepath, os.path.join(profile.path, filename))
            log.info("Added file to profile: %s" % filepath)
    '''
    # turn off about:config warning
    profile.set_preference("general.warnOnAboutConfig", False)
    profile.set_preference("webdriver_accept_untrusted_certs", True)

    caps = DesiredCapabilities.FIREFOX.copy()
    if options and "capabilities" in options:
        caps.update(options["capabilities"])

    def get_remote_browser(tries=0, max_tries=2):
        socket.setdefaulttimeout(60)
        executor = override_grid_host
        log.info("Executor: " + executor)

        if opts:
            caps.update(opts.to_capabilities())

        try:
            return CleanRemoteWebdriver(
                command_executor=executor,
                desired_capabilities=caps,
                browser_profile=profile
            )
        except Exception as e:  # TODO catch specific timeouts
            log.error("Error requesting remote webdriver: %s" % e)
            if tries < max_tries:
                log.warning("Timeout (%d) while initializing remote webdriver." % (tries + 1))
                return get_remote_browser(tries + 1)
            else:
                warn = "Timeout (%d) while initializing remote webdriver. " % (tries + 1)
                if local_fallback:
                    log.warning(warn + "Switching to local display.")
                    return get_local_browser()
                else:
                    socket.setdefaulttimeout(120)
                    raise e

    def get_local_browser():
        params = {
            "firefox_profile": profile,
            "capabilities": caps,
            "log_path": "/tmp/geckodriver.log",
            "firefox_options": opts
        }
        if headless:
            return HeadlessFirefox(**params)
        return webdriver.Firefox(**params)

    browser = get_remote_browser() if use_grid else get_local_browser()

    browser.set_script_timeout(120)
    socket.setdefaulttimeout(120)

    time.sleep(0.5)

    # close any additional tab
    while len(browser.window_handles) > 1:
        browser.switch_to.window(browser.window_handles[-1])
        browser.close()
        browser.switch_to.window(browser.window_handles[0])

    return browser


def get_chrome(proxy_type: str,
               use_grid: bool = True,
               options: dict = None,
               user_agent: str = 'default',
               headless: bool = False,
               local_fallback: bool = True,
               proxy_creds: dict = None,
               override_proxy: dict = None,
               override_grid_host: dict = None) -> webdriver:

    opts = ChromeOptions()
    caps = DesiredCapabilities.CHROME.copy()
    caps.update(opts.to_capabilities())

    log.warning("get_chrome: these args are not being used: headless, local_fallback, proxy_creds")

    if user_agent != 'default':
        opts.add_argument("--user-agent=%s" % user_agent)
    log.info("User agent: %s" % user_agent)

    if proxy_type is None:
        pass
    elif proxy_type != "tor" and proxy_type not in AVAILABLE_PROXIES:
        raise RuntimeError("Proxy type %s is not supported" % proxy_type)
    else:
        if override_proxy is None:
            proxy = AVAILABLE_PROXIES
        else:
            proxy = override_proxy

        if proxy_type == "tor":
            opts.add_argument("--proxy-server=socks5://%s" % proxy)
        else:
            opts.add_argument("--proxy-server=http://%s" % proxy)

    if options and "extensions" in options:
        for extension in options['extensions']:
            log.info("Adding extension: %s" % extension)
            try:
                opts.add_extension(pkg_resources.resource_filename(__name__, extension))
            except Exception as e:
                raise

    if options and "args" in options:
        for a in options["args"]:
            if a not in opts.arguments:
                opts.add_argument(a)

    if options and "capabilities" in options:
        caps.update(options["capabilities"])

    def get_remote_browser(tries=0, max_tries=2):
        socket.setdefaulttimeout(60)
        executor = override_grid_host
        log.info("Executor: " + executor)

        try:
            return RemoteWebDriver(
                command_executor=executor,
                desired_capabilities=caps
            )
        except Exception as e:  # TODO catch specific timeouts
            log.error("Error requesting remote webdriver: %s" % e)
            if tries < max_tries:
                log.warning("Timeout (%d) while initializing remote webdriver." % (tries + 1))
                return get_remote_browser(tries + 1)
            else:
                warn = "Timeout (%d) while initializing remote webdriver. " % (tries + 1)
                socket.setdefaulttimeout(120)
                raise e

    def get_local_browser():
        return webdriver.Chrome(chrome_options=opts)

    browser = get_remote_browser() if use_grid else get_local_browser()

    browser.set_script_timeout(120)
    socket.setdefaulttimeout(120)

    return browser


def get_html_string(browser: webdriver) -> webdriver:
    return browser.execute_script("return document.documentElement.outerHTML")


def get_html_tree(browser: webdriver, e_tree: bool = False):
    try:
        doc = get_html_string(browser)

        if e_tree:
            root = etree.HTML(doc)
            tree = etree.ElementTree(root)
        else:
            tree = html.fromstring(doc)
    except Exception as e:
        tree = None

    return tree


class wait_for_page_load(object):
    def __init__(self, browser: webdriver, timeout: int = 60) -> None:
        self.browser = browser
        self.timeout = timeout
        self.run = True

    def __enter__(self):
        try:
            self.old_page = self.browser.find_element_by_tag_name('html')
        except Exception as e:
            try:
                self.old_page = self.browser.find_element_by_tag_name('rss')  # current page is non-rendered rss
            except Exception:
                log.warning("Unable to use wait_for_page_load wrapper")
                self.run = False

    def page_has_loaded(self):
        try:
            new_page = self.browser.find_element_by_tag_name('html')
            return new_page.id != self.old_page.id
        except Exception as e:
            try:
                new_page = self.browser.find_element_by_tag_name('rss')  # In case Firefox doesn't render rss page
                return new_page.id != self.old_page.id
            except Exception:
                return False

    def __exit__(self, *_):
        if self.run:
            _wait_for(self.page_has_loaded, self.timeout)


def _wait_for(condition_function, timeout: int) -> None:
    start_time = time.time()
    while time.time() < start_time + timeout:
        if condition_function():
            return True
        else:
            time.sleep(1.0)
    raise TimeoutException(
        'Timeout waiting for {}'.format(condition_function.__name__))


def disable_images(browser: webdriver) -> None:
    log.info("disabling images")
    _set_browser_config(browser, 'permissions.default.image', 2)


def enable_images(browser: webdriver) -> None:
    log.info("enabling images")
    _set_browser_config(browser, 'permissions.default.image', 1)


def _set_browser_config(browser: webdriver, config: dict, value: float) -> None:
    browser.get("about:config")

    script = '''var prefs = Components.classes["@mozilla.org/preferences-service;1"]
            .getService(Components.interfaces.nsIPrefBranch);

            '''

    if isinstance(value, int):
        script += 'prefs.setIntPref("%s", "%s");' % (config, value)
    else:
        script += 'prefs.setCharPref("%s", "%s");' % (config, value)

    browser.execute_script(script)
    browser.execute_script("window.history.go(-1)")
    time.sleep(3.0)


def random_user_agent():
    with open(
        os.path.expandvars('$RF_ROOT/python/src/recordedfuture/apps/ha_torvest/lib/useragents.tsv')
    ) as infile:
        reader = csv.DictReader(infile, delimiter='\t')
        agents = []
        p = []
        for row in reader:
            agents.append(row['useragent'])
            p.append(float(row['percent'].replace('%', '')) / 100)

        p_norm = [x / sum(p) for x in p]
    return np.random.choice(agents, p=p_norm)


'''

# Firebug browser deprecated
# retained code in the future

def get_firebug_browser(proxy="proxymesh", area_code='random', firefox_options=None, maintain_session=True):

    opts = {
        "extensions": [
            "FireXPath.xpi",
            "firebug.xpi"
        ],
        "profile":
            {
                "browser.tabs.remote.autostart.2": False
            }
    }

    if firefox_options:
        opts.update(firefox_options)

    if proxy == "proxymesh":
        proxy_creds = secret_service.get_ext_secrets(proxy, 'torvest')
        if maintain_session:
            proxy_creds['random_string'] = ''.join(random.sample(string.ascii_uppercase, 8))
            proxy_creds = "{username}:{random_string}:{password}".format(**proxy_creds)
        else:
            proxy_creds = "{username}:{password}".format(**proxy_creds)
    else:
        proxy_creds = None

    if area_code == 'random' and proxy == "proxymesh":
        areas = ["us-wa", "fr", "jp", "au", "de", "nl", "sg", "us-il", "us", "us-dc"]
        area_code = random.choice(areas)
        proxy_host = area_code + ".proxymesh.com:31280"
    elif area_code and proxy == 'proxymesh':
        proxy_host = area_code + ".proxymesh.com:31280"
    else:
        proxy_host = None

    return get_firefox(
        proxy_type=proxy,
        use_grid=False,
        options=opts,
        headless=False,
        proxy_creds=proxy_creds,
        override_proxy=proxy_host,
        user_agent=random_user_agent()
    )
'''
