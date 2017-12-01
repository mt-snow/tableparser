#! /usr/bin/env python3
# -*- coding: utf-8 -*-
import urllib.parse
from urllib.request import urlopen
from bs4 import BeautifulSoup


API_BASE_URL = 'https://ja.wikipedia.org/w/api.php?'


def search(keyword, limit=10):
    """
    search page by keyword
    return generator object.
    """
    def generator(keyword, limit):
        next_id = 0
        query = {
            'list': 'search',
            'srsearch': keyword,
            'srlimit': limit,
            'srprop': 'titlesnippet',
            }
        soup = get_api_result(query)
        yield int(soup.searchinfo['totalhits'])

        while True:
            items = soup.find_all('p')
            for item in items:
                next_id += 1
                yield item.attrs
            if soup.find('continue'):
                soup = get_api_result(query)
            else:
                break

    gen = generator(keyword, limit)

    return gen, next(gen)


def get_page_source(title_or_id):
    """
    get wiki source by title or page_id.
    """
    query = {
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
    """
    query wiki api
    query_dict is media wiki format without format or action.
    return beautiful soup xml object.
    """
    query_dict.update({'format': 'xml', 'action': 'query'})
    query = urllib.parse.urlencode(query_dict)
    with urlopen(API_BASE_URL + query) as f:
        return BeautifulSoup(f.read().decode(), 'xml')


def show_search_result(keyword, **args):
    del args
    gen, total = search(keyword, limit=50)
    gen = enumerate(gen, start=1)
    print('total: %d' % total)
    key = ''
    while 'q' not in key:
        print('#\tpageid\ttitle')
        for _ in range(10):
            try:
                print("{0}\t{1[pageid]}\t{1[title]}".format(*next(gen)))
            except StopIteration:
                return
        key = input(':')


def show_source(title_or_id, **args):
    del args
    if title_or_id.isdecimal():
        print(get_page_source(int(title_or_id)))
    else:
        print(get_page_source(title_or_id))


def _main(argv):
    import argparse
    parser = argparse.ArgumentParser()
    sub_parsers = parser.add_subparsers(title='Actions')
    sub_parsers.required = True
    sub_parsers.dest = 'action'

    search_parser = sub_parsers.add_parser(
        'search', aliases=['s'],
        help='search keyword and show titles and page_ids')
    search_parser.add_argument('keyword')
    search_parser.set_defaults(func=show_search_result)

    get_parser = sub_parsers.add_parser(
        'get_source', aliases=['get', 'g'],
        help='get wiki source by title or page id')
    get_parser.add_argument('title_or_id')
    get_parser.set_defaults(func=show_source)

    args = parser.parse_args(argv[1:])
    args.func(**vars(args))

if __name__ == '__main__':
    import sys
    _main(sys.argv)
