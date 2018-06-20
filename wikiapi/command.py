#! /usr/bin/env python3
# -*- coding: utf-8 -*-

"""wikiapi cli"""

import os
import api


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


def print_search_result(keyword, limit=0, **_):
    """Print search result by keyword."""
    gen, total = api.search(keyword, limit=50)
    gen = enumerate(gen, start=1)
    print('total: %d' % total)
    print('#\tpageid\ttitle')
    iterator = zip(range(limit), gen) if limit > 0 else enumerate(gen)
    for _, item in iterator:
        print("{0}\t{1[pageid]}\t{1[title]}".format(*item))


def print_source(title_or_id, unlink_flag, redirects_flag, **_):
    """Print wiki source."""
    page = api.find_page(title_or_id, redirects_flag=redirects_flag)

    if unlink_flag:
        page.unlink()
    print(page.source)


def print_infobox(title_or_id, unlink_flag, redirects_flag, **_):
    """Print infoboxes and those params."""
    page = api.find_page(title_or_id, redirects_flag=redirects_flag)
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
    page = api.find_page(title_or_id)
    if not page:
        print(None)
        return
    page.unlink()
    infoboxes = page.anime_info()
    if infoboxes == 0:
        print('Error: "Infobox animanga" is not found.')
        sys.exit(1)
    for i, info in enumerate(infoboxes):
        print('%d\t%s' % (i, info))
    print('ID [filename]')
    words = input('> ').split()
    if not words or len(words) > 2:
        print('Error')
        sys.exit(1)
    num = int(words[0])
    filename = words[0] if len(words) > 2 else os.environ['HOME'] + '/title.txt'
    with open(filename, mode='w') as out:
        print(ANIME_INFO_TEMPLATE.format(**infoboxes[num]), file=out)


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
        'infobox', aliases=['info'],
        help='show infobox')
    get_parser.add_argument('title_or_id',
                            type=lambda x: int(x) if x.isdecimal() else x)
    get_parser.add_argument('--disable-unlink', dest='unlink_flag',
                            action='store_false', help='remove link', default=True)
    get_parser.add_argument('--no-redirects', dest='redirects_flag',
                            action='store_false', help='resolve redirects')
    get_parser.set_defaults(func=print_infobox)

    anime_parser = sub_parsers.add_parser(
        'anime', help='show anime')
    anime_parser.add_argument('title_or_id',
                              type=lambda x: int(x) if x.isdecimal() else x)
    anime_parser.set_defaults(func=print_anime_info)

    args = parser.parse_args(argv[1:])
    args.func(**vars(args))


if __name__ == '__main__':
    import sys
    _main(sys.argv)
