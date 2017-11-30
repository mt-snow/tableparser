#! /usr/bin/env python3
# -*- coding: utf-8 -*-
import urllib.parse
from urllib.request import urlopen
from bs4 import BeautifulSoup


API_BASE_URL = 'https://ja.wikipedia.org/w/api.php?'


class WikipediaSearch:
    def __init__(self, keyword, limit=10):
        def generator(soup):
            if self.next_id != 0:
                # if next_id is changed before first call, requery
                query['sroffset'] = self.next_id
                soup = get_api_result
            while True:
                continue_flag = False
                items = soup.find_all('p')
                for item in items:
                    self.next_id += 1
                    next_id_cache = self.next_id
                    yield item.attrs
                    if next_id_cache != self.next_id:
                        continue_flag = True
                        break
                if continue_flag or soup.find('continue'):
                    query['srlimit'] = self.limit
                    query['sroffset'] = self.next_id
                    soup = get_api_result(query)
                else:
                    break

        query = {
            'format': 'xml',
            'action': 'query',
            'list': 'search',
            'srsearch': keyword,
            'srlimit': limit,
            'srprop': 'titlesnippet',
            }

        soup = get_api_result(query)
        self.total_hits = int(soup.searchinfo['totalhits'])
        self.limit = limit
        self.next_id = 0
        self._gen = generator(soup)

    def __iter__(self):
        return iter(self._gen)

    def __next__(self):
        return next(self._gen)


def get_page_source(title_or_id):
    """
    get wiki source by title or page_id.
    """
    query = {
        'format': 'xml',
        'action': 'query',
        'prop': 'revisions',
        'rvprop': 'content',
        }
    if isinstance(title_or_id, int):
        query['pageids'] = title_or_id
    elif isinstance(title_or_id, str):
        query['titles'] = title_or_id
    else:
        raise TypeError('title_or_id must be str or int.')

    result = get_api_result(query)
    if result.rev is None:
        return None
    return result.rev.string


def get_api_result(query_dict):
    query = urllib.parse.urlencode(query_dict)
    with urlopen(API_BASE_URL + query) as f:
        return BeautifulSoup(f.read().decode(), 'xml')


if __name__ == '__main__':
    import sys
    gen = enumerate(WikipediaSearch(sys.argv[1]), start=1)
    key = ''
    while 'q' not in key:
        print('#\tpageid\ttitle')
        for _ in range(10):
            try:
                print("{0}\t{1[pageid]}\t{1[title]}".format(*next(gen)))
            except StopIteration:
                return
        key = input(':')
