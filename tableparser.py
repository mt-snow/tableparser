#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""HTML Table parser"""

import re
from itertools import product, zip_longest
from functools import reduce
from urllib.request import urlopen
from bs4 import BeautifulSoup


class Table:
    """
    Table Tag Parser
    This class analyzes row and col of Table and
    convert HTML Table to TSV(Tab-Separated Values).
    """
    def __init__(self, soup):
        self.soup = soup
        self.table_map = {}
        self._parse_table(soup)

    def _parse_table(self, table):
        re_td = re.compile("t[hd]")
        trs = []
        if table.thead:
            thead_trs = table.thead.find_all("tr", recursive=False)
            trs += zip_longest(thead_trs, [True])
        tbody = table.tbody if table.tbody else table
        tbody_trs = tbody.find_all("tr", recursive=False)
        trs += zip_longest(tbody_trs, [False])
        for y, (tr, header_flag) in enumerate(trs):
            x = 0
            tds = tr.find_all(re_td)
            for td in tds:
                while (y, x) in self.table_map:
                    x += 1
                cell = Cell(td, header_flag)
                for p in product(range(y, y + cell.dy),
                                 range(x, x + cell.dx)):
                    self.table_map[p] = cell
                x += cell.dx

    def get_strings(self, with_header=True):
        old_y = 0
        keys = sorted(self.table_map)
        words = []
        lines = []
        for y, x in keys:
            v = self.table_map[(y, x)]
            if not with_header and v.is_header():
                continue
            if y == old_y:
                words.append(str(v))
            else:
                lines.append("\t".join(words))
                if y - old_y > 1:
                    lines.append("\n" * (y - old_y - 2))
                words = [str(v)]
            old_y = y
        if words:
            lines.append("\t".join(words))

        return "\n".join(lines)

    def __str__(self):
        return self.get_strings()


class Cell:
    """
    Table Data Parser
    This class extracts "TD" tag contents.
    """
    def __init__(self, soup, in_thead=False):
        self.soup = soup
        self.dx = int(soup.get("colspan", 1))
        self.dy = int(soup.get("rowspan", 1))
        self.in_thead = in_thead

    def __str__(self):
        if not hasattr(self, "_string_cache"):
            self._string_cache = reduce(lambda x, y: x + y,
                                        list(self.soup.stripped_strings), "")
        return self._string_cache

    def is_header(self):
        return self.in_thead or self.soup.name == 'th'


def main():
    class AllContains:
        def __contains__(self, target):
            return True

    import argparse
    parser = argparse.ArgumentParser(description='HTML Table Parser')
    parser.add_argument('url', help='target URL')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-a', '--all', action='store_true',
                       help='show all table')
    group.add_argument('-n', '--table-num', type=int, metavar='num',
                       action='append', help='table number',
                       default=AllContains())
    parser.add_argument('--dump', action='store_true',
                        help='dump html source.')
    parser.add_argument('--with-header', action='store_true',
                        default=True, dest="header", help='with header')
    parser.add_argument('--without-header', action='store_false',
                        dest="header", help='without header')
    args = parser.parse_args()
    with urlopen(args.url) as f:
        text = f.read()
        text = text.replace(b"\n", b"").replace(b"\r", b"")
        soup = BeautifulSoup(text, "lxml")
        tables = soup.find_all("table")
        for count, table in enumerate(tables, 1):
            if not args.all and count not in args.table_num:
                continue
            if len(tables) != 1:
                print("Table %d:" % count)
            if not args.dump:
                print(Table(table))
            else:
                print(Table(table).get_strings(with_header=args.header))
            print()

    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
