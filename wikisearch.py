import urllib.parse
from urllib.request import urlopen
from bs4 import BeautifulSoup


API_BASE_URL = 'http://ja.wikipedia.org/w/api.php?'

class WikipediaSearch:
    def __init__(self, keyword, limit=10):
        def generator(soup):
            if self.next_id != 0:
                # if next_id is changed before first call, requery 
                query['sroffset'] = self.next_id
                soup = get_api_result
            while True:
                continue_flag = False
                items = soup.find_all('p')
                for item in items:
                    self.next_id += 1
                    next_id_cache = self.next_id
                    yield item.attrs
                    if next_id_cache != self.next_id:
                        continue_flag = True
                        break
                if continue_flag or soup.find('continue'):
                    query['srlimit'] = self.limit
                    query['sroffset'] = self.next_id
                    soup = get_api_result(query)
                else:
                    break
        
        query = {
                'format': 'xml',
                'action': 'query',
                'list': 'search',
                'srsearch': keyword,
                'srlimit': limit,
                'srprop': 'titlesnippet',
            }
        soup = get_api_result(query)
        self.total_hits = int(soup.searchinfo['totalhits'])
        self.limit = 10
        self.next_id = 0
        self._gen = generator(soup)

    def __iter__(self):
        return iter(self._gen)

    def __next__(self):
        return next(self._gen)


def get_api_result(query_dict):
    query = urllib.parse.urlencode(query_dict)
    with urlopen(API_BASE_URL + query) as f:
        return BeautifulSoup(f.read().decode(), 'xml')


if __name__ == '__main__':
    import sys
    gen = enumerate(WikipediaSearch(sys.argv[1]), start=1)
    key = ''
    while 'q' not in key:
        print('#\tpageid\ttitle')
        for i in range(10):
            print("{0}\t{1[pageid]}\t{1[title]}".format(*next(gen)))
        key = input(':')
