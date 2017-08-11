#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""HTML Table parser"""

import re
from itertools import product
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
        tbody = table.tbody if table.tbody else table
        trs = tbody.find_all("tr", recursive=False)
        for y, tr in enumerate(trs):
            x = 0
            tds = tr.find_all(re_td)
            for td in tds:
                while (y, x) in self.table_map:
                    x += 1
                cell = Cell(td)
                for p in product(range(y, y + cell.dy),
                                 range(x, x + cell.dx)):
                    self.table_map[p] = cell
                x += cell.dx

    def __str__(self):
        old_y = 0
        keys = sorted(self.table_map)
        words = []
        lines = []
        for y, x in keys:
            v = str(self.table_map[(y, x)])
            if y == old_y:
                words.append(v)
            else:
                lines.append("\t".join(words))
                if y - old_y > 1:
                    lines.append("\n" * (y - old_y - 2))
                words = [v]
            old_y = y
        if words:
            lines.append("\t".join(words))

        return "\n".join(lines)


class Cell:
    """
    Table Data Parser
    This class extracts "TD" tag contents.
    """
    def __init__(self, soup):
        self.soup = soup
        self.dx = int(soup.get("colspan", 1))
        self.dy = int(soup.get("rowspan", 1))

    def __str__(self):
        if not hasattr(self, "_string_cache"):
            self._string_cache = reduce(lambda x, y: x + y,
                                        list(self.soup.stripped_strings), "")
        return self._string_cache

    def is_header(self):
        return self.soup.name == 'th'


def main():
    import argparse
    parser = argparse.ArgumentParser(description='HTML Table Parser')
    parser.add_argument('url', help='target URL')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-a', '--all', action='store_true',
                       help='show all table')
    group.add_argument('-n', '--table-num', type=int, metavar='num',
                       action='append', help='table number')
    parser.add_argument('--dump', action='store_true',
                        help='dump html source.')
    args = parser.parse_args()
    with urlopen(args.url) as f:
        text = f.read()
        text = text.replace(b"\n", b"").replace(b"\r", b"")
        soup = BeautifulSoup(text, "lxml")
        tables = soup.find_all("table")
        for count, table in enumerate(tables, 1):
            if not args.all and count not in args.table_num:
                continue
            print("Table %d:" % count)
            if not args.dump:
                print(Table(table))
            else:
                print(table)
            print()
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
