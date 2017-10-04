import os
# Hack to avoid "urlopen error [Errno -2] Name or service not known"
os.environ['http_proxy'] = ''

import csv
from urllib.error import HTTPError, URLError
from urllib.request import urlretrieve

# Config

resources_file_name = 'resources.csv'
folder = 'static'


def save_resources(resources_file, directory='static'):
    # Getting row count
    with open(resources_file, 'r') as res_file:
        resources_count = sum(1 for row in res_file)

    if not os.path.exists(directory):
        os.makedirs(directory)

    with open(resources_file, 'r') as res_file:
        csv_reader = csv.DictReader(res_file, delimiter=',', quotechar='"')

        i = 0
        for row in csv_reader:
            abs_link = row['Url']
            file_name = row['FileName']
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


save_resources(resources_file_name, folder)
