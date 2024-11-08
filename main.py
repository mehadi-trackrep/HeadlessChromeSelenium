import os
import sys
import time
import json
import random
import shutil
import logging
import traceback
from faker import Faker
from tempfile import mkdtemp
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

language_list = ['en']

GOAVA_REQUEST_COUNT = 0
RELOAD_BROWSER_THRESHOLD = int(os.getenv('RELOAD_BROWSER_THRESHOLD', 50))
GOAVA_TMP_DIRECTORY = None
GOAVA_HEADLESS_DRIVER = None

#This part make logging work locally when testing and in lambda cloud watch
if logging.getLogger().hasHandlers():
    logging.getLogger().setLevel(logging.INFO)
else:
    logging.basicConfig(level=logging.INFO)


ALL_EN_LETTERS_IN_UPPER_FORM = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
ALL_EN_LETTERS_IN_LOWER_FORM = 'abcdefghijklmnopqrstuvwxyz'

#Function that setup the browser parameters and return browser object.
def open_browser(tmp_directory) -> None:
    fake_user_agent = Faker()
    # options = webdriver.ChromeOptions()
    options = Options()
    options.binary_location = '/opt/chrome/chrome'
    service = Service(executable_path='/opt/chromedriver')
    
    options.add_experimental_option("excludeSwitches", ['enable-automation'])
    options.add_argument('--disable-infobars')
    options.add_argument('--disable-extensions')
    options.add_argument('--no-first-run')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--disable-client-side-phishing-detection')
    options.add_argument('--allow-running-insecure-content')
    options.add_argument('--disable-web-security')
    options.add_argument('--user-agent=' + fake_user_agent.user_agent())
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1280x1696")
    options.add_argument("--single-process")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-dev-tools")
    options.add_argument("--no-zygote")
    options.add_argument(f"--user-data-dir={tmp_directory}")
    options.add_argument(f"--data-path={tmp_directory}")
    options.add_argument(f"--disk-cache-dir={tmp_directory}")
    # options.add_argument("--remote-debugging-port=9222")
    
    chrome = webdriver.Chrome(service=service, options=options)
    driver = chrome
    return driver
    
def wait_for_page_load(driver, timeout=50):
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script('return document.readyState') == 'complete'
    )
    time.sleep(10)


def get_text(driver, url):
    try:
        driver.get(url)
        
        wait_for_page_load(driver)
        
        print(f"url: {url} is loaded.")
        
        times = 0
        while True:
            show_more_button = None
            try:
                show_more_button = driver.find_element(
                    By.XPATH, 
                    f"//button[\
                        contains(\
                            translate(\
                                text(), '{ALL_EN_LETTERS_IN_UPPER_FORM}', '{ALL_EN_LETTERS_IN_LOWER_FORM}'\
                            ), \
                            'mer'\
                        )\
                            \
                        or \
                            \
                        contains(\
                            translate(\
                                text(), '{ALL_EN_LETTERS_IN_UPPER_FORM}', '{ALL_EN_LETTERS_IN_LOWER_FORM}'\
                            ), \
                            'more'\
                        )\
                    ]"
                )
            except Exception as es:
                print(f"error while searching for show more button: {es}")
                break
            if not show_more_button:
                print(f"found no show more button.")
                break
            try:
                driver.execute_script( # it will go to the HTML element and ..
                    "arguments[0].scrollIntoView(true);", 
                    show_more_button
                )
                time.sleep(2)
                show_more_button.click() # and then click
                times += 1
                print(f"# {times}: clicked on the show_more_button: {show_more_button}")
            except Exception as es:
                print(f"error while clicking on the show more button. {es}")
                break

        emails_at_href= []
        email_elements = driver.find_elements(
            By.XPATH, 
            "//*[contains(text(), '@') or contains(text(), '<at>') or contains(@href, 'mailto') or contains(@href, '@') ]"
        )
        
        for index, element in enumerate(email_elements):
            driver.execute_script(
                "arguments[0].scrollIntoView(true);", 
                element
            )
            
            time.sleep(1)
            
            href = element.get_attribute('href')
            if href and ('mailto' in href or '@' in href or '<at>' in href):
                emails_at_href.append(href)
            elif element.text and ('@' in element.text or '<at>' in element.text):
                emails_at_href.append("mailto:" + element.text)
            
            print(f"=> {index}: scrolling to email text: {element.text} and/or href: {href}")
        
        return {
                "body_text": driver.find_element(By.TAG_NAME, 'body').text,
                "probable_emails_at_href": emails_at_href
            }
    except Exception as es:
        print(f"error: {es}")
    # finally: {
    #     driver.quit()
    # }


def get_texts(driver, urls):
    url_vs_text = {
    }
    for url in urls:
        print(f"url: {url}")
        url_vs_text[url] = get_text(driver, url)
    return url_vs_text

def get_disk_space_info(path='/'):
    statvfs = os.statvfs(path)

    # Get total disk space
    total_space = statvfs.f_frsize * statvfs.f_blocks

    # Get available disk space
    available_space = statvfs.f_frsize * statvfs.f_bavail

    # Get used space
    used_space = total_space - available_space

    return total_space, used_space, available_space

# """
#     event = {
#         "urls": [
#             "url1",
#             "url2"
#         ]
#     }
# """
def lambda_handler(event={}, context=None):
    global GOAVA_REQUEST_COUNT, GOAVA_TMP_DIRECTORY, GOAVA_HEADLESS_DRIVER
    logging.info(f"Payload: {event}")
    
    url_vs_text = {}

    # total, used, available = get_disk_space_info('/')
    logging.info(
        (
            f"GOAVA_REQUEST_COUNT: {GOAVA_REQUEST_COUNT}" 
            f"\nRELOAD_BROWSER_THRESHOLD: {RELOAD_BROWSER_THRESHOLD}"
            # f"\nTotal space: {total / (1024 ** 3):.2f} GB"
            # f"\nUsed space: {used / (1024 ** 3):.2f} GB"
            # f"\nAvailable space: {available / (1024 ** 3):.2f} GB"
        )
    )
    
    if not GOAVA_HEADLESS_DRIVER or GOAVA_REQUEST_COUNT % RELOAD_BROWSER_THRESHOLD == 0:
        logging.info("Reloading browser...")
        if GOAVA_HEADLESS_DRIVER:
            try:
                GOAVA_HEADLESS_DRIVER.quit()
            except Exception as es:
                logging.error(f"driver.quit() spawed an error. {es}")
        if GOAVA_TMP_DIRECTORY:
            try:
                shutil.rmtree(GOAVA_TMP_DIRECTORY)
            except Exception as es:
                logging.error(f"deleting tmp dir spawed an error. {es}")
            
        GOAVA_TMP_DIRECTORY = mkdtemp()
        GOAVA_HEADLESS_DRIVER = open_browser(GOAVA_TMP_DIRECTORY)
        logging.info(f"Browser reloaded with tmp directory: {GOAVA_TMP_DIRECTORY}")
    
    url_vs_text = get_texts(GOAVA_HEADLESS_DRIVER, event.get("urls", []))
    GOAVA_REQUEST_COUNT += 1

    return url_vs_text
    

if __name__ == "__main__":
    """
        event={"urls": ["https://ravema.se/mot-teamet/"]}
    """
    print(
        get_texts(
            [
               "https://ravema.se/mot-teamet/"
                # ,
                # "https://www.cegal.com/sv/kontakt"
                # ,
                # ,"https://www.voky.com/om-voky/medarbetare/"
                # ,"https://idkommunikation.com/kontakta-oss/"
                # "https://styrhytten.com/kontakt/"
            ]
        )
    )