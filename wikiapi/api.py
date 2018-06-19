#! /usr/bin/env python3
# -*- coding: utf-8 -*-

"""wikipedia api"""

import sys
import urllib.parse
from urllib.request import urlopen
import collections
import collections.abc
from collections import OrderedDict
import regex
from bs4 import BeautifulSoup


API_BASE_URL = 'https://ja.wikipedia.org/w/api.php?'

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

    def templates_iter(self, name=None):
        """
        return an iterator over all templates in the page.
        """
        return _Template.finditer(self.source, name)

    def infoboxes_iter(self):
        """
        Parse infoboxes with wiki source,
        returning Iterator of infobox name and parameters dict.
        (<infobox name>, {<param name>: <param value>, ...})
        """
        return self.templates_iter(lambda x: x.startswith('Infobox'))

    def anime_info(self):
        """Parse infobox animanga."""
        infoboxes = list(self.templates_iter(lambda x: x.startswith('Infobox animanga')))
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


class _Template(collections.abc.Mapping):
    """Wiki template object"""
    TEMPLATE_REGEX = regex.compile(
        r'(?<quote>\{\{(?<contents>(?:[^{}]|(?&quote))*)\}\})')

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
        def _split_params(text):
            nest = ''
            key = None
            start = 0
            counter = 1
            for i, char in enumerate(text):
                if nest:
                    if char == nest[-1]:
                        nest = nest[:-1]
                    continue
                if char == '=' and not key:
                    key = text[start:i].strip()
                    start = i + 1
                elif char == '|':
                    value = text[start:i].strip()
                    if key == '':
                        key = str(counter)
                        counter += 1
                    yield key, value
                    start = i + 1
                    key = ''
                elif char in '{[':
                    nest += char
            value = text[start:].strip()
            yield (key, value) if key != '' else (str(counter), value)

        # Remove '{{' and '}}'
        contents = source[2:-2]
        gen = _split_params(contents)
        return next(gen)[1], OrderedDict(gen)

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
