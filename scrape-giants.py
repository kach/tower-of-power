# "If I have seen further it is by standing on the shoulders of Giants."
#   -- Newton

from bs4 import BeautifulSoup
import requests, re

seen = set()
def get(sid, depth=5):
    if sid in seen:
        return
    seen.add(sid)
    soup = BeautifulSoup(requests.get('https://www.genealogy.math.ndsu.nodak.edu/id.php?id=%s' % sid).text, "html5lib")
    name = u'\\'.join(soup.find('h2').text.strip().split()).encode('utf-8')
    advisors = []
    if depth > 0:
        for advisor in soup.find_all(string=re.compile('Advisor')):
            atag = advisor.find_next_sibling()
            if atag is None:
                continue
            aid = atag.attrs['href'].replace('id.php?id=', '')
            advisors.append(aid)
            get(aid, depth - 1)
    print sid,
    print u'(' + (u', '.join(advisors)), u') :',
    print name

get('61129', 15) # mitch resnick, as an example
