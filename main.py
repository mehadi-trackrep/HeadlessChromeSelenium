import time
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService

ALL_EN_LETTERS_IN_UPPER_FORM = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
ALL_EN_LETTERS_IN_LOWER_FORM = 'abcdefghijklmnopqrstuvwxyz'

def wait_for_page_load(driver, timeout=30):
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script('return document.readyState') == 'complete'
    )
    time.sleep(10)

def get_text(url):
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--run-all-compositor-stages-before-draw")
        chrome_options.add_argument("--force-color-profile=srgb")
        chrome_options.add_argument("--window-size=1920x1080")
        chrome_options.add_argument(f'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')

        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)
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
            elif '@' in element.text or '<at>' in element.text:
                emails_at_href.append('mailto:' + element.text)
            
            print(f"=> {index}: scrolling to email text: {element.text} and/or href: {href}")
        
        return {
                "body_text": driver.find_element(By.TAG_NAME, 'body').text,
                "probable_emails_at_href": emails_at_href
            }
    except Exception as es:
        print(f"error: {es}")
    finally: {
        driver.quit()
    }

def get_texts(urls):
    url_vs_text = {
    }
    for url in urls:
        print(f"url: {url}")
        url_vs_text[url] = get_text(url)
    return json.dumps(
        url_vs_text,
        ensure_ascii=False,
        indent=4
    )

if __name__ == "__main__":
    print(
        get_texts(
            [
                "https://www.voky.com/om-voky/medarbetare/",
                "https://idkommunikation.com/kontakta-oss/",
                "https://styrhytten.com/kontakt/"
            ]
        )
    )