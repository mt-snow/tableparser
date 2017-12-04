#! /usr/bin/env python3
# -*- coding: utf-8 -*-
import urllib.parse
from urllib.request import urlopen
import regex
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


def unlink(source):
    """remove link from wiki source"""
    return regex.sub(r'\[\[([^\[\]|]*)(?:\|([^\[\]]*))?\]\]',
                     lambda match: match[2] if match[2] else match[1],
                     source)


def parse_infoboxes(source):
    """
    parse infoboxes with wiki source
    return infobox name and list of parameter name and value.
    (<infobox name>, [[<param name>, <param value>, ...]])
    """
    infoboxes = regex.finditer(
        r'\{\{Infobox (?P<name>[\w/]*)'
        r'(?<content>(?:[^{}]|(?<quote>'
        r'\{\{(?:[^{}]|(?&quote))*\}\}))*)\}\}',
        source.replace('\n', ''))
    for box in infoboxes:
        template_name, params, _ = box.groups()
        params = regex.findall(
            r'([^=|]+)(?:=(?P<quote>(?:[^{}\[\]|]|'
            r'\{\{(?:(?P&quote)|\|)*\}\}|'
            r'\[\[(?:(?P&quote)|\|)*\]\])*))?',
            params)
        yield template_name, [param[:2] for param in params]


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


def show_search_result(keyword, **_):
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


def show_source(title_or_id, unlink_flag, **_):
    """show wiki source"""
    if title_or_id.isdecimal():
        source = get_page_source(int(title_or_id))
    else:
        source = get_page_source(title_or_id)

    if unlink_flag:
        source = unlink(source)
    print(source)


def show_infobox(title_or_id, unlink_flag, **_):
    """show infobox params"""
    if title_or_id.isdecimal():
        source = get_page_source(int(title_or_id))
    else:
        source = get_page_source(title_or_id)
    if not source:
        print(None)
        return
    if unlink_flag:
        source = unlink(source)

    infoboxes = parse_infoboxes(source)
    for name, params in infoboxes:
        print('Infobox ' + name)
        for param in params:
            print(param[0] + ' = ' + param[1])
        print('')


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
    get_parser.add_argument('--unlink', dest='unlink_flag',
                            action='store_true', help='remove link')
    get_parser.set_defaults(func=show_source)

    get_parser = sub_parsers.add_parser(
        'show_infobox', aliases=['sh'],
        help='show infobox')
    get_parser.add_argument('title_or_id')
    get_parser.add_argument('--unlink', dest='unlink_flag',
                            action='store_true', help='remove link')
    get_parser.set_defaults(func=show_infobox)

    args = parser.parse_args(argv[1:])
    args.func(**vars(args))

if __name__ == '__main__':
    import sys
    _main(sys.argv)
