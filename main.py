# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# [START gae_python38_app]
from flask import Flask, url_for, render_template, request, send_file
from urllib.parse import urlparse
from dateutil import parser, tz
from datetime import datetime, timedelta
import feedparser 
import html, requests
from bs4 import BeautifulSoup

# datastores
from google.cloud import datastore
datastore_client = datastore.Client(project='rareyetem')

# If `entrypoint` is not defined in app.yaml, App Engine will look for an app
# called `app` in `main.py`.
app = Flask(__name__)

# building image fetcher
from apiclient.discovery import build

def storeArticle(title, item):
    entity = datastore.Entity(key=datastore_client.key('title', title))
    entity.update(item)
    datastore_client.put(entity)

def fetchArticleByTitle(title):
    print('[info] fetching', title)
    article = datastore_client.get(datastore_client.key('title', title)) 
    return article

def fetchArticles(lim):
    query = datastore_client.query(kind='title')
    query.order = ['-pubdate']
    articles = query.fetch(limit=lim)
    return articles

def cleanupArticles(lim):
    query = datastore_client.query(kind='title')
    query.order = ['pubdate']
    articles = query.fetch(limit=lim)
    for article in articles:
        datastore_client.delete(article.key)

# for scooping image from the news agencies
def imageSoup(url):
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Max-Age': '3600',
        'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:52.0) Gecko/20100101 Firefox/52.0'
    }
    req = requests.get(url)
    soup = BeautifulSoup(req.content, 'html.parser')
    for img in soup.find_all('img'):
        imgsrc = img.get('src')
        if 'http' in imgsrc and ('jpg' in imgsrc or 'jpeg' in imgsrc):
            if len(requests.get(imgsrc).content) > 40000:
                return imgsrc  # return immediately after we find an image

    return 'https://upload.wikimedia.org/wikipedia/commons/3/39/Abstract_6_by_G._M._Solegaonkar.jpg'

def gatherArticles(url, limit=5):

    # parsing news feeds from the given url 
    res = feedparser.parse(url)
    #print(res)

    i = 1
    for item in res.entries:
        title   = html.unescape(item.title)
        article = fetchArticleByTitle(title)
        dt = parser.parse(item.published)
        pubdate = dt.astimezone(tz.tzutc())
        
        if article == None:
            # scooping image for the news
            print('[info] no existing article found, adding new article')
            img = imageSoup(item.link)
            credit = urlparse(item.link).netloc  # getting network location (url) for credits
            article = {'title':title,'link':item.link,'summ':item.summary,'img':img,'credit':credit,'pubdate':pubdate}
            storeArticle(title, article)
            print('[info] new article added')
        else:
            print('[info] article retrieved')

        if i >= limit:
            break
        else:
            i += 1


@app.route('/')
def index():
    # fetch articles from datastore 
    newsItems = fetchArticles(48) 
    return render_template('index.html', items=newsItems)

@app.route('/mobile')
def indexMobile():
    # fetch articles from datastore 
    newsItems = fetchArticles(48) 
    return render_template('mobile.html', items=newsItems)

@app.route('/tasks/update')
def update():
    # generating content using the following feeds
    feedList = ['http://feeds.bbci.co.uk/news/rss.xml?edition=uk#',
            'http://www.thairath.co.th/rss/news.xml',
            #'https://www.bangkokpost.com/rss/data/life.xml',
            #'https://www.bangkokpost.com/rss/data/sports.xml',
            'https://www.bangkokpost.com/rss/data/thailand.xml']
            #'https://www.posttoday.com/rss/src/entertainment.xml']
    
    for feed in feedList:
        gatherArticles(feed, 3) # gather and put them in datastore

    return "[info] update completed"  # for non-viewable page

@app.route('/tasks/cleanup')
def cleanup():
    # adding news clean-up here
    cleanupArticles(50)
    return "[info] cleanup completed"

if __name__ == '__main__':
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be)) configured by adding an `entrypoint` to app.yaml.
    app.run(host='127.0.0.1', port=8080, debug=True)
# [END gae_python38_app]
