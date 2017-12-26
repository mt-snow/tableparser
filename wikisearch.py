#! /usr/bin/env python3
# -*- coding: utf-8 -*-

"""wikipedia api command"""

import urllib.parse
from urllib.request import urlopen
from collections import OrderedDict
import regex
from bs4 import BeautifulSoup


API_BASE_URL = 'https://ja.wikipedia.org/w/api.php?'


def search(keyword, limit=10):
    """
    Search pages by keyword, returning
    the generator of page soup objects and amount of total hits.
    """
    def _generator(keyword, limit):
        next_id = 0
        query = {
            'list': 'search',
            'srsearch': keyword,
            'srlimit': limit,
            'srprop': 'titlesnippet',
            }
        soup = call_api(query)
        yield int(soup.searchinfo['totalhits'])

        while True:
            items = soup.find_all('p')
            for item in items:
                next_id += 1
                yield item.attrs
            if soup.find('continue'):
                soup = call_api(query)
            else:
                break

    gen = _generator(keyword, limit)

    return gen, next(gen)


class _Wikipage:
    """Wikipedia page parser"""
    def __init__(self, source=None, api_response=None):
        self.source = source
        self.api_response = None
        self.pageid = None
        self.title = None
        if api_response is not None:
            if 'missing' in api_response.page.attrs:
                raise ValueError('The api_response contains no page.')
            self.source = api_response.page.string
            self.pageid = api_response.page['pageid']
            self.title = api_response.page['title']

    @classmethod
    def find_page(cls, title_or_id, redirects_flag=True):
        """
        Find the wikipedia page by title or page_id,
        returning the wikipage object.
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
        if redirects_flag:
            query['redirects'] = True

        result = call_api(query)
        if 'missing' in result.page.attrs:
            return None
        return cls(api_response=result)

    @classmethod
    def find_pages(cls, titles, redirects_flag=True):
        """
        Return wiki sources by collection of titles.
        """
        query = {
            'prop': 'revisions',
            'rvprop': 'content',
            }
        if (hasattr(titles, '__iter__') and
                any(not isinstance(obj, str) for obj in titles)):
            raise TypeError('Titles_or_ids must be conllection of str.')
        query['titles'] = "|".join(titles)
        if redirects_flag:
            query['redirects'] = True

        result = call_api(query)

        return_dict = {}
        for title in titles:
            normalized = title
            item = result.find(['n', 'r'], **{'from': normalized})
            while item:
                normalized = item['to']
                item = result.find(['n', 'r'], **{'from': normalized})
            page = result.find('page', title=normalized)
            return_dict[title] = page.rev.string if page.rev else None
        return return_dict

    def infoboxes_iter(self):
        """
        Parse infoboxes with wiki source,
        returning Iterator of infobox name and parameters dict.
        (<infobox name>, {<param name>: <param value>, ...})
        """
        infoboxes = regex.finditer(
            r'\{\{Infobox (?P<name>[\w/]*)'
            r'(?<content>(?:[^{}]|(?<quote>'
            r'\{\{(?:[^{}]|(?&quote))*\}\}))*)\}\}',
            self.source.replace('\n', ''))
        for box in infoboxes:
            template_name, params, _ = box.groups()
            params = regex.findall(
                r'\s*([^=|]+?)\s*(?:=\s*(?P<quote>(?:[^{}\[\]|]|'
                r'\{\{(?:(?P&quote)|\|)*\}\}|'
                r'\[\[(?:(?P&quote)|\|)*\]\])*))?(?:$|\|)',
                params)
            yield template_name, OrderedDict([param[:2] for param in params])

    def anime_info(self):
        """Parse infobox animanga."""
        infoboxes = [item for item in self.infoboxes_iter()
                     if item[0].startswith('animanga')]
        animes = []
        for name, params in infoboxes:
            if name == 'animanga/Header':
                series_title = params.get('タイトル')
                break
        for name, params in infoboxes:
            if name in ('animanga/TVAnime', 'animanga/OVA'):
                title = params.get('タイトル', series_title)
                director = params.get('総監督', params.get('監督'))
                studio = params.get('アニメーション制作')
            elif name == 'animanga/Movie':
                title = params.get('タイトル', series_title)
                director = params.get('総監督', params.get('監督'))
                studio = params.get('制作')
            else:
                continue
            animes.append((name, series_title, title, director, studio))
        return animes

    def unlink(self):
        """Remove link from the page."""
        self.source = regex.sub(
            r'\[\[([^\[\]|]*)(?:\|([^\[\]]*))?\]\]',
            lambda match: match[2] if match[2] else match[1],
            self.source)
        return self


def parse_infoboxes2(source):
    """
    Parse infoboxes with wiki source,
    returning Iterator of infobox name and parameters dict.
    (<infobox name>, {<param name>: <param value>, ...})
    """
    infoboxes = regex.finditer(
        r'\{\{(?P<name>[^|{}]*)'
        r'(?<content>(?:[^{}]|(?<quote>'
        r'\{\{(?:[^{}]|(?&quote))*\}\}))*)\}\}',
        source.replace('\n', ''))
    non_infobox_templates = set()
    for box in infoboxes:
        infobox_flag = True
        check_templates = set()
        template_name, params, _ = box.groups()
        name = template_name
        indent = 0
        while not name.startswith('Infobox'):
            if name in non_infobox_templates:
                infobox_flag = False
                break
            print("\t" * indent + name)
            check_templates.add(name)
            name = check_template_name(name.rstrip())
            if not name:
                infobox_flag = False
                break
            indent += 1
        if not infobox_flag:
            non_infobox_templates.update(check_templates)
            continue

        params = regex.findall(
            r'\s*([^=|]+?)\s*(?:=\s*(?P<quote>(?:[^{}\[\]|]|'
            r'\{\{(?:(?P&quote)|\|)*\}\}|'
            r'\[\[(?:(?P&quote)|\|)*\]\])*))?(?:$|\|)',
            params)
        yield template_name, OrderedDict([param[:2] for param in params])


def check_template_name(template_name):
    """Check internal templates name."""
    page = Wikipage.find_page('Template:' + template_name)
    if not page:
        return None
    match = regex.match(r'\{\{([^|{}]*)', page.source)
    if not match:
        return None
    return match.group(1).rstrip()


def call_api(query_dict):
    """
    Call wikipedia api, returning beatutiful soup xml object.

    Query_dict must be formed acording to media wiki api.
    The 'format' and 'action' query-params is prisetted to
    'xml' and 'query'.
    """
    actual_query_dict = {'format': 'xml', 'action': 'query'}
    actual_query_dict.update(query_dict)
    query = urllib.parse.urlencode(actual_query_dict)
    with urlopen(API_BASE_URL + query) as xml:
        return BeautifulSoup(xml.read().decode(), 'xml')


def print_search_result(keyword, **_):
    """Print search result by keyword."""
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


def print_source(title_or_id, unlink_flag, redirects_flag, **_):
    """Print wiki source."""
    page = Wikipage(title_or_id, redirects_flag=redirects_flag)

    if unlink_flag:
        page.unlink()
    print(page.source)


def print_infobox(title_or_id, unlink_flag, redirects_flag, **_):
    """Print infoboxes and those params."""
    page = Wikipage.find_page(title_or_id, redirects_flag)
    if not page:
        print(None)
        return
    if unlink_flag:
        page.unlink()

    infoboxes = page.infoboxes_iter()
    for name, params in infoboxes:
        print('Infobox ' + name)
        for key, value in params.items():
            print(key + ' = ' + value)
        print('')


def print_anime_info(title_or_id, **_):
    """Print infoboxes and those params."""
    page = Wikipage.find_page(title_or_id)
    if not page:
        print(None)
        return
    page.unlink()
    print(page.anime_info())


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
    search_parser.set_defaults(func=print_search_result)

    get_parser = sub_parsers.add_parser(
        'get_source', aliases=['get', 'g'],
        help='get wiki source by title or page id')
    get_parser.add_argument('title_or_id',
                            type=lambda x: int(x) if x.isdecimal() else x)
    get_parser.add_argument('--unlink', dest='unlink_flag',
                            action='store_true', help='remove link')
    get_parser.add_argument('--no-redirects', dest='redirects_flag',
                            action='store_false', help='resolve redirects')
    get_parser.set_defaults(func=print_source)

    get_parser = sub_parsers.add_parser(
        'show_infobox', aliases=['sh'],
        help='show infobox')
    get_parser.add_argument('title_or_id',
                            type=lambda x: int(x) if x.isdecimal() else x)
    get_parser.add_argument('--unlink', dest='unlink_flag',
                            action='store_true', help='remove link')
    get_parser.add_argument('--no-redirects', dest='redirects_flag',
                            action='store_false', help='resolve redirects')
    get_parser.set_defaults(func=print_infobox)

    anime_parser = sub_parsers.add_parser(
        'show_anime_info', aliases=['anime'],
        help='show anime')
    anime_parser.add_argument('title_or_id',
                              type=lambda x: int(x) if x.isdecimal() else x)
    anime_parser.set_defaults(func=print_anime_info)

    args = parser.parse_args(argv[1:])
    args.func(**vars(args))


if __name__ == '__main__':
    import sys
    _main(sys.argv)
