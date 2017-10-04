import codecs
import datetime
import os

from time import sleep

# Hack to avoid "urlopen error [Errno -2] Name or service not known"
os.environ['http_proxy'] = ''

from urllib.error import HTTPError
from urllib.error import URLError
from urllib.parse import unquote
from urllib.parse import urljoin
from urllib.request import urlparse
from urllib.request import urlretrieve

import selenium
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# Config
start_page = 0
end_page = 2
screen_prefix = 'page_'
topic = 'http://artmusic.smfforfree.com/index.php/topic,2183'
url_format = '{}.{}'
csv_file_name = 'output.csv'
json_file_name = 'json.json'
resources_list_file_name = 'resources.csv'
pages_html = 'pages.html'
user_login = 'username'
user_password = 'password'
write_to_csv = False
write_to_json = False
save_screenshots = False
use_local_resources = True


class ForumMessage:
    def __init__(self, author, title, date, content):
        self.author = str(author)
        self.title = str(title)
        self.date = str(date)
        self.content = str(content)

    def to_csv(self):
        csv_string = '\t"{}",\t"{}",\t"{}",\t"{}"'.format(
            self.author,
            self.title,
            self.date,
            self.content
        )

        return csv_string

    def to_json(self):
        json_string = '{author:"{}", title:"{}", date:"{}", content:"{}"}'.format(
            self.author,
            self.title,
            self.date,
            self.content
        )

        return json_string


def get_posts(_driver):
    posts = _driver.find_elements_by_xpath(".//*[text()='Quote']")
    results = []
    posts_count = len(posts)

    for i in range(0, posts_count):
        quote_button = posts[i]

        # Open a quote page in a new tab
        quote_button.send_keys(Keys.CONTROL + Keys.RETURN)

        # Waiting for tab to be opened
        WebDriverWait(_driver, 10).until(
            lambda y: len(_driver.window_handles) > 1
        )

        _driver.switch_to.window(_driver.window_handles[-1])

        # Waiting for content loading of new tab
        WebDriverWait(_driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, 'textarea'))
        )

        _text = _driver.find_element_by_tag_name('textarea').text
        metadata = _text[_text.index("[") + 1:_text.rindex("]")]

        # Starting from 2nd character to cut out '[]'
        message_text = _text.replace(metadata, '')[2:]

        metadata_list = metadata.replace('quote ', '').split(' ')
        message_author = metadata_list[0].split('=')[1]
        message_date = datetime.datetime.fromtimestamp(
            int(metadata_list[-1].split('=')[1])).strftime('%Y-%m-%d %H:%M:%S')
        message_title = _driver.find_element_by_name('subject').get_attribute('value')

        new_message = ForumMessage(message_author, message_title, message_date, message_text)

        results.append(new_message)

        # Logging process
        print('\tPost: {}/{}'.format(i + 1, posts_count))

        # Closing new tab and switching to main tab
        _driver.close()
        _driver.switch_to.window(_driver.window_handles[0])

    return results


def print_posts(file, messages_list, count):
    for message in messages_list:
        count += 1
        file.write('{},"{}"\n'.format(count, message.to_csv().encode('unicode_escape')))

    return count


def print_posts_json(file, messages_list):
    for message in messages_list:
        file.write(message.to_json())


def login(username, password, _driver):
    # Login
    _driver.find_element_by_name('user').send_keys(username)
    sleep(1)
    _driver.find_element_by_name('passwrd').send_keys(password)
    sleep(1)
    _driver.find_element_by_xpath("//form/input[3]").click()
    sleep(1)

    try:
        _driver.find_element_by_xpath("//form/input[3]")
        login(username, password, _driver)
    except NoSuchElementException:
        pass


def save_resources_list(img_dict):
    with open(resources_list_file_name, 'w') as res_file:
        res_file.write('FileName,Url\n')

        for key, value in img_dict.items():
            res_file.write('"{}","{}"\n'.format(value, key))


def prepare_page(_driver, _file, resource_dir='static'):
    _file.write('<html>\n')
    html_head = _driver.find_element_by_tag_name('head'). \
        get_attribute('outerHTML').encode().decode('utf-8', 'strict')

    parsed_uri = urlparse(topic)
    http_domain = '{uri.scheme}://{uri.netloc}/'.format(uri=parsed_uri)

    if not os.path.exists(resource_dir):
        os.makedirs(resource_dir)

    head_soup = BeautifulSoup(html_head, 'lxml')

    # Removing <script> tag
    [s.extract() for s in head_soup.findAll('script')]

    link_css_tags = head_soup.findAll('link', rel='stylesheet')

    links_css_tags_dict = {}

    for item in link_css_tags:
        link = item['href']
        abs_link = urljoin(http_domain, link)
        item_href = unquote(abs_link.split('/')[-1])
        file_name = item_href.split('?')[0]
        links_css_tags_dict[abs_link] = file_name
        item['href'] = '{}/{}'.format(resource_dir, item_href)

    _file.write(str(head_soup))

    _file.write('<body>/n')

    return links_css_tags_dict


def finalize_page(_file):
    _file.write(
        '</body>\n</html>'
    )


def extract_page(_driver, resource_dir='static'):
    posts_table = str(_driver.find_element_by_id('postTable').get_attribute('outerHTML')) \
        .replace('id="postTable"', '')

    parsed_uri = urlparse(topic)
    http_domain = '{uri.scheme}://{uri.netloc}/'.format(uri=parsed_uri)

    page_soup = BeautifulSoup(posts_table, 'lxml')

    img_tags = page_soup.findAll('img')

    page_images_dict = {}

    if use_local_resources:
        for item in img_tags:
            link = item.get('src')

            if link is None:
                continue

            abs_link = urljoin(http_domain, link)
            item_src = unquote(abs_link.split('/')[-1])
            file_name = item_src.split('?')[0]
            page_images_dict[abs_link] = file_name
            item['src'] = '{}/{}'.format(resource_dir, item_src)

    # Removing <script> tag
    [s.extract() for s in page_soup.findAll('script')]

    # Converting HTML source to utf-8 to prevent 'UnicodeEncodeError' while writing to file
    return str(page_soup.encode('utf-8', errors='replace').decode('utf-8', errors='replace')), page_images_dict


# Temporary parameters
page_num = 0
scrapped_posts_count = 0
resources_dict = {}
url = url_format.format(topic, page_num)

driver = webdriver.PhantomJS()

# HACK: setting window size at the beginning,
# since multiple calls of set_window_size hangs application(Selenium bug)
driver.set_window_size(1024, 768)

driver.get(url)

print('Logging in...')
login(user_login, user_password, driver)
print('Login successful!')

# Preparing output files
pages_file = codecs.open(pages_html, 'w', 'utf-8')

new_css_dict = prepare_page(driver, pages_file)
resources_dict = {**resources_dict, **new_css_dict}

csv_file = None
json_file = None

if write_to_csv:
    csv_file = codecs.open(csv_file_name, 'w', 'utf-8')
    csv_file.write('id,\tpost:\n')

if write_to_json:
    json_file = codecs.open(json_file_name, 'w', 'utf-8')

for x in range(start_page, end_page):
    try:
        url = url_format.format(topic, page_num)
        print("Page: {}".format(x + 1))
        page_num += 15
        driver.get(url)

        if save_screenshots:
            print('\tGetting screenshot...')
            driver.save_screenshot('{}{}.png'.format(screen_prefix, x + 1))
            print('\tDone!')

        print('\tExtracting posts HTML...')
        page_html, new_images_dict = extract_page(driver)
        pages_file.write(page_html)

        # Adding new items to dict
        resources_dict = {**resources_dict, **new_images_dict}

        print('\tDone!')

        if write_to_csv:
            print('\tScraping post content with BB codes to *.csv...')
            scrapped_posts_count = print_posts(csv_file, get_posts(driver), scrapped_posts_count)
            print('\tDone!')

        if write_to_json:
            print('\tScraping post content with BB codes to *.json...')
            print_posts_json(json_file, get_posts(driver))
            print('\tDone!')

    except selenium.common.exceptions.TimeoutException:
        print('Page loading timeout. Skipping page #', str(x + 1))

driver.close()

if use_local_resources:
    print('Downloading resources...')
    save_resources_list(resources_dict)

finalize_page(pages_file)

pages_file.close()

if write_to_csv:
    csv_file.close()

if write_to_json:
    json_file.close()

print('Scraping finished!')
