#! /usr/bin/env python3
# -*- coding: utf-8 -*-

"""wikipedia api command"""

import os
import urllib.parse
from urllib.request import urlopen
import collections
import collections.abc
from collections import OrderedDict
import regex
from bs4 import BeautifulSoup


API_BASE_URL = 'https://ja.wikipedia.org/w/api.php?'
ANIME_INFO_TEMPLATE = """tracks = 
track = 1
season = 1
title := "%s %s" % (i[0], i[1])
#title := i[1]
show = "{series_title}"
#sortShow = "{series_title}"
album = "{title}"
#sortAlbum = ""
#sortAlbum = sortShow
artist = "{director}"
albumArtist = "{studio}"
genre = "Anime"
hdvideo = "1"
network = ""
year = date("")
comment = "TV版, %s~%s, %s" % (year.strftime("%Y.%m"), (year + W * (tracks - track)).strftime("%Y.%m"), network)
year =: year + W
track =: track + 1
episode := track
episodeid := "S%02dE%02d" % (season, track)
stik = "tvshow"
#description :=
#longdesc :=
COMMENT_PREFIX = "//"
"""

_DEBUG_API = False

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
                query.update(soup.find('continue').attrs)
                soup = call_api(query)
            else:
                break

    gen = _generator(keyword, limit)

    return gen, next(gen)


def find_page(title_or_id, redirects_flag=True):
    """
    Find the wikipedia page by title or page_id,
    returning the wikipage object.
    """
    return _Wikipage.find_page(title_or_id, redirects_flag=redirects_flag)


def find_pages(titles, redirects_flag=True):
    """
    Return wiki sources by collection of titles.
    """
    return _Wikipage.find_page(titles, redirects_flag=redirects_flag)


class _Wikipage:
    """Wikipedia page parser"""
    def __init__(self, source=None, api_response=None, page=None):
        self.source = source
        self.api_response = api_response
        self.page = page
        self.pageid = None
        self.title = None
        if page is None and api_response is not None:
            self.page = api_response.page
        if self.page is not None:
            if 'missing' in self.page.attrs:
                raise ValueError('The api_response contains no page.')
            self.source = self.page.string
            self.pageid = self.page['pageid']
            self.title = self.page['title']

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
            return_dict[title] = (cls(api_response=result, page=page)
                                  if 'missig' not in page.attrs else None)
        return return_dict

    def __repr__(self):
        return '<%s title=%s pegeid=%s source=%s>' % (
            self.__class__.__name__,
            self.title,
            self.pageid,
            self.source if len(self.source) < 10 else self.source[:8] + '...')

    def templates_iter(self):
        """
        return an iterator over all templates in the page.
        """
        return _Template.finditer(self.source)

    def infoboxes_iter(self):
        """
        Parse infoboxes with wiki source,
        returning Iterator of infobox name and parameters dict.
        (<infobox name>, {<param name>: <param value>, ...})
        """
        return (temp for temp in self.templates_iter()
                if temp.name.startswith('Infobox'))

    def anime_info(self):
        """Parse infobox animanga."""
        infoboxes = [item for item in self.infoboxes_iter()
                     if item.name.startswith('Infobox animanga')]
        animes = []
        for box in infoboxes:
            if box.name == 'Infobox animanga/Header':
                series_title = box.get('タイトル')
                break
        for box in infoboxes:
            if box.name in ('Infobox animanga/TVAnime',
                            'Infobox animanga/OVA'):
                title = box.get('タイトル', series_title)
                director = box.get('総監督', box.get('監督'))
                studio = box.get('アニメーション制作')
            elif box.name == 'animanga/Movie':
                title = box.get('タイトル', series_title)
                director = box.get('総監督', box.get('監督'))
                studio = box.get('制作')
            else:
                continue
            animes.append({'type': box.name, 'series_title': series_title,
                           'title': title, 'director': director, 'studio': studio})
        return animes

    def unlink(self):
        """Remove link from the page."""
        self.source = regex.sub(
            r'\[\[([^\[\]|]*)(?:\|([^\[\]]*))?\]\]',
            lambda match: match[2] if match[2] else match[1],
            self.source)
        return self

    def parse_infoboxes2(self):
        """
        Parse infoboxes with wiki source,
        returning Iterator of infobox name and parameters dict.
        (<infobox name>, {<param name>: <param value>, ...})
        """
        infoboxes = regex.finditer(
            r'\{\{(?P<name>[^|{}]*)'
            r'(?<content>(?:[^{}]|(?<quote>'
            r'\{\{(?:[^{}]|(?&quote))*\}\}))*)\}\}',
            self.source.replace('\n', ''))
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


class _Template(collections.abc.Mapping):
    """Wiki template object"""
    TEMPLATE_REGEX = regex.compile(
        r'(?<quote>\{\{(?<contents>(?:[^{}]|(?&quote))*)\}\})')
    PARAM_REGEX = regex.compile(
        r'\s*(?:(?P<quote>(?:[^{}\[\]|=]|'
        r'\{\{(?:(?P&quote)|\||=)*\}\}|\[\[(?:(?P&quote)|\||=)*\]\]'
        r')+?)\s*=\s*)?(?P<value>(?P&quote))(?:\Z|\|)'
    )

    @classmethod
    def finditer(cls, source, name=None):
        """
        Return an iterator over all mediawiki templates in the source.
        """
        temp_sources = cls.TEMPLATE_REGEX.finditer(source)
        a_filter = _make_filter(name)

        for match in temp_sources:
            source = match.group(0)
            name, params = cls._get_name_and_params(source)
            if not a_filter(name):
                continue
            yield _Template(source, name=name, params=params)

    def __init__(self, source=None, *, name=None, params=None):
        self._source = source
        self.name = name
        self._params = params
        if source is not None:
            match = self.TEMPLATE_REGEX.fullmatch(source)
            if match is None:
                raise ValueError('There is no template.')
        if name is None or params is None:
            if source is None:
                raise ValueError(
                    'Neither source nor (name, params) must be None.')
            name, params = self._get_name_and_params(source)
            if self.name is None:
                self.name = name
            if self._params is None:
                self._params = params

    @property
    def source(self):
        """
        Return the wiki source of template.
        If the source is not preset, genarate it from the name and params.
        """
        if self._source is not None:
            return self._source
        lines = [self.name]
        numeric_keys = 1
        for key, value in self.items():
            if (regex.fullmatch(r'[0-9]+', key) and
                    numeric_keys == int(key)):
                lines.append(value)
                numeric_keys += 1
            else:
                lines.append('%s=%s' % (key, value))
        return '{{' + '|'.join(lines) + '}}'

    def __repr__(self):
        return '%r(%r)' % (self.__class__.__name__, self.source)

    @classmethod
    def _get_name_and_params(cls, source):
        # Remove '{{' and '}}'
        contents = source[2:-2]
        name_params = cls.PARAM_REGEX.findall(contents)
        name = name_params[0][1].strip()

        counter = 1
        params = OrderedDict()
        for key, value in name_params[1:]:
            # Skip the first param,
            # because it is template_name
            if key == '':
                key = str(counter)
                counter += 1
            if key in params:
                del params[key]
            params[key] = value.strip()
        return name, params

    def __contains__(self, key):
        return key in self._params

    def __eq__(self, other):
        return isinstance(self, _Template) and self.source == other.source

    def __getitem__(self, key):
        if isinstance(key, int):
            key = str(key)
        return self._params[key]

    def get(self, key, default=None):
        if isinstance(key, int):
            key = str(key)
        return self._params.get(key, default)

    def items(self):
        return self._params.items()

    def keys(self):
        return self._params.keys()

    def values(self):
        return self._params.values()

    def __len__(self):
        return len(self._params)

    def __iter__(self):
        return iter(self._params)


def _make_filter(name=None):
    def _check(target):
        if name is None:
            return True
        if isinstance(name, bool):
            return name
        if isinstance(name, str):
            return name == target
        if isinstance(name, tuple):
            return target in name
        if hasattr(name, 'match'):
            return name.match(target)
        if isinstance(name, collections.Callable):
            return name(target)
        raise TypeError()

    if not (name is None or
            isinstance(name, (bool, str, collections.Callable)) or
            hasattr(name, 'match')):
        raise TypeError()
    if (not isinstance(name, str) and
            isinstance(name, collections.Iterable)):
        name = tuple(name)
    return _check


def check_template_name(template_name):
    """Check internal templates name."""
    page = find_page('Template:' + template_name)
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
    if _DEBUG_API:
        print('QUERRY: ' + str(actual_query_dict), file=sys.stderr)
        print('URLOPEN: ' + API_BASE_URL + query, file=sys.stderr)
    with urlopen(API_BASE_URL + query) as xml:
        result = BeautifulSoup(xml.read().decode(), 'xml')
        if _DEBUG_API:
            print('RESULT:\n' + result.prettify(), file=sys.stderr)
        return result


def print_search_result(keyword, limit=0, **_):
    """Print search result by keyword."""
    gen, total = search(keyword, limit=50)
    gen = enumerate(gen, start=1)
    print('total: %d' % total)
    print('#\tpageid\ttitle')
    iterator = zip(range(limit), gen) if limit > 0 else enumerate(gen)
    for _, item in iterator:
        print("{0}\t{1[pageid]}\t{1[title]}".format(*item))


def print_source(title_or_id, unlink_flag, redirects_flag, **_):
    """Print wiki source."""
    page = _Wikipage.find_page(title_or_id, redirects_flag=redirects_flag)

    if unlink_flag:
        page.unlink()
    print(page.source)


def print_infobox(title_or_id, unlink_flag, redirects_flag, **_):
    """Print infoboxes and those params."""
    page = find_page(title_or_id, redirects_flag=redirects_flag)
    if not page:
        print(None)
        return
    if unlink_flag:
        page.unlink()

    infoboxes = page.infoboxes_iter()
    for box in infoboxes:
        print(box.name)
        for key, value in box.items():
            print(key + ' = ' + value)
        print('')


def print_anime_info(title_or_id, **_):
    """Print infoboxes and those params."""
    page = find_page(title_or_id)
    if not page:
        print(None)
        return
    page.unlink()
    infoboxes = page.anime_info()
    if len(infoboxes) == 0:
        import sys
        print('Error: "Infobox animanga" is not found.')
        sys.exit(1)
    for i, info in enumerate(infoboxes):
        print('%d\t%s' % (i, info))
    print('ID [filename]')
    n = input('> ').split()
    if len(n) == 1:
        n = n[0]
        filename = os.environ['HOME'] + '/title.txt'
    elif len(n) == 2:
        filename = n[0]
        n = n[1]
    else:
        import sys
        print('Error')
        sys.exit(1)
    with open(filename, mode='w') as f:
        print(ANIME_INFO_TEMPLATE.format(**infoboxes[int(n)]), file=f)


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
    search_parser.add_argument('-l', '--limit', type=int, default=10,
                               help='max of printing serch result')
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
    get_parser.add_argument('--disable-unlink', dest='unlink_flag',
                            action='store_false', help='remove link', default=True)
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
