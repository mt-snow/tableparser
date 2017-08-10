#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import re
from itertools import product
from functools import reduce
from urllib.request import urlopen
from bs4 import BeautifulSoup


class Table:
    def __init__(self, soup):
        self.soup = soup
        self.table_map = {}
        self.parse_table(soup)

    def parse_table(self, table):
        re_td = re.compile("t[hd]")
        tbody = self.soup.tbody if self.soup.tbody else self.soup
        trs = tbody.find_all("tr", recursive=False)
        for y, tr in enumerate(trs):
            x = 0
            tds = tr.find_all(re_td)
            for td in tds:
                while (y, x) in self.table_map:
                    x += 1
                data, dx, dy = self._parse_td(td)
                for p in product(range(y, y + dy), range(x, x + dx)):
                    self.table_map[p] = data
                x += dx

    def _parse_td(self, td):
        dx = int(td.get("colspan", 1))
        dy = int(td.get("rowspan", 1))
        data = reduce(lambda x, y: x + y, list(td.stripped_strings), "")
        return data, dx, dy

    def to_string(self):
        old_y = 0
        keys = sorted(self.table_map)
        words = []
        lines = []
        for y, x in keys:
            v = self.table_map[(y, x)]
            if y == old_y:
                words.append(v)
            else:
                lines.append("\t".join(words))
                if y - old_y > 1:
                    lines.append("\n" * (y - old_y -1))
                words = [v]
            old_y = y
        if(len(words) > 0):
            lines.append("\t".join(words))

        return "\n".join(lines)


if __name__ =='__main__':
    import argparse
    parser = argparse.ArgumentParser(description='HTML Table Parser')
    parser.add_argument('url', help='target URL')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-a', '--all', action='store_true',
                       help='show all table')
    group.add_argument('-n', '--table-num', type=int, metavar='num',
                       action='append', help='table number')
    args = parser.parse_args()
    with urlopen(args.url) as f:
        text = f.read()
        text = text.replace(b"\n", b"").replace(b"\r", b"")
        soup = BeautifulSoup(text, "lxml")
        tables = soup.find_all("table")
        for count, table in enumerate(tables, 1):
            if not args.all and count not in args.table_num:
                continue
            t = Table(table)
            print("Table %d:" % count)
            print(t.to_string())
            print()
