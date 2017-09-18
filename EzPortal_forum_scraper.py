import codecs
import os

from time import sleep
from urllib.error import HTTPError
from urllib.error import URLError
from urllib.parse import unquote
from urllib.parse import urljoin
from urllib.request import urlparse
from urllib.request import urlretrieve

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# Config
total_pages = 2
screen_prefix = 'page_'
topic = 'http://artmusic.smfforfree.com/index.php/topic,2183'
url_format = '{}.{}'
output_file_name = 'output.csv'
pages_html = 'pages.html'
user_login = 'username'
user_password = 'password'


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

        results.append(_driver.find_element_by_tag_name('textarea').text)

        # Logging process
        print('\tPost: {}/{}'.format(i + 1, posts_count))

        # Closing new tab and switching to main tab
        _driver.close()
        _driver.switch_to.window(_driver.window_handles[0])

    return results


def print_posts(file, posts_list, count):
    for post in posts_list:
        count += 1
        file.write('{},\t"{}"\n'.format(count, post.encode('unicode_escape')))

    return count


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


def save_resources(img_dict, directory='static'):
    resources_count = len(img_dict.keys())
    i = 0

    for abs_link, file_name in img_dict.items():
        print('Retrieving {}/{}'.format(i + 1, resources_count), end='\r')
        i += 1

        try:
            urlretrieve(abs_link, '{}/{}'.format(directory, file_name))

        except HTTPError:
            # If 404 - do not replace http path to local path
            pass

        except URLError as e:
            print('Resource not available, skipping...\nDetails:\n' + str(e))

    print('\nDone!')


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

driver = webdriver.Firefox()

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

output_file = codecs.open(output_file_name, 'w', 'utf-8')
output_file.write('id,\tpost:\n')


for x in range(0, total_pages):
    url = url_format.format(topic, page_num)
    if page_num != 0:
        print("Page: {}".format(x + 1))
        page_num += 15
        driver.get(url)

        print('\tGetting screenshot...')
        driver.save_screenshot('{}{}.png'.format(screen_prefix, x + 1))
        print('\tDone!')

        print('\tExtracting posts HTML...')
        page_html, new_images_dict = extract_page(driver)
        pages_file.write(page_html)

        # Adding new items to dict
        resources_dict = {**resources_dict, **new_images_dict}

        print('\tDone!')

        print('\tScraping post content with BB codes...')
        scrapped_posts_count = print_posts(output_file, get_posts(driver), scrapped_posts_count)
        print('\tDone!')
    else:
        print("Page: {}".format(x + 1))
        driver.get(url)
        page_num += 15

        print('\tGetting screenshot...')
        driver.save_screenshot('{}{}.png'.format(screen_prefix, x + 1))
        print('\tDone!')

        print('\tExtracting posts HTML...')
        page_html, new_images_dict = extract_page(driver)
        pages_file.write(page_html)

        # Adding new items to dict
        resources_dict = {**resources_dict, **new_images_dict}
        print('\tDone!')

        print('\tScraping post content with BB codes...')
        scrapped_posts_count = print_posts(output_file, get_posts(driver), scrapped_posts_count)
        print('\tDone!')

driver.close()

print('Downloading resources...')
save_resources(resources_dict)

finalize_page(pages_file)

pages_file.close()
output_file.close()

print('Scraping finished!')
