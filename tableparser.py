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


def main():
    pass

with urlopen(sys.argv[1]) as f:
    text = f.read()
    text = text.replace("\n", "")
    soup = BeautifulSoup(text, "lxml")
    tables = soup.find_all("table")
    for table in tables:
        t = Table(table)
