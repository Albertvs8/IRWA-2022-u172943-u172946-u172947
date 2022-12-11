import os
from json import JSONEncoder

# pip install httpagentparser
import httpagentparser  # for getting the user agent as json
import nltk
from flask import Flask, render_template, session
from flask import request

from myapp.analytics.analytics_data import AnalyticsData, ClickedDoc, User, Requests
from myapp.search.load_corpus import load_corpus
from myapp.search.objects import Document, StatsDocument
from myapp.search.search_engine import SearchEngine
from myapp.search.algorithms import create_index_tfidf
import random
from datetime import datetime, date
import requests


# *** for using method to_json in objects ***
def _default(self, obj):
    return getattr(obj.__class__, "to_json", _default.default)(obj)


_default.default = JSONEncoder().default
JSONEncoder.default = _default

# end lines ***for using method to_json in objects ***

# instantiate the Flask application
app = Flask(__name__)

# random 'secret_key' is used for persisting data in secure cookie
app.secret_key = 'afgsreg86sr897b6st8b76va8er76fcs6g8d7'
# open browser dev tool to see the cookies
app.session_cookie_name = 'IRWA_SEARCH_ENGINE'

# instantiate our in memory persistence
analytics_data = AnalyticsData()

# print("current dir", os.getcwd() + "\n")
# print("__file__", __file__ + "\n")
full_path = os.path.realpath(__file__)
path, filename = os.path.split(full_path)
# print(path + ' --> ' + filename + "\n")
# load documents corpus into memory.
file_path = path + "/tweets-data-who.json"

# file_path = "../../tweets-data-who.json"

# instantiate our search engine
corpus = load_corpus(file_path)
print("loaded corpus. first elem:", list(corpus.values())[0])
num_documents = len(corpus)
index, tf, df, idf = create_index_tfidf(corpus, num_documents)
search_engine = SearchEngine(corpus, num_documents, index, tf, idf)

user = User()
date_start = date.today()
date_now = datetime.now()
hour = date_now.strftime("%H:%M:%S")
user.date = date_start
user.hour = hour


# Home URL "/"
@app.route('/')
def index():
    analytics_data.fact_requests.append(Requests(datetime.now(), request))
    print("starting home url /...")

    # flask server creates a session by persisting a cookie in the user's browser.
    # the 'session' object keeps data between multiple requests
    session['some_var'] = "IRWA 2022 home"

    user_agent = request.headers.get('User-Agent')
    print("Raw user browser:", user_agent)

    user_ip = request.remote_addr
    agent = httpagentparser.detect(user_agent)
    analytics_data.agent = agent
    print("Remote IP: {} - JSON user browser {}".format(user_ip, agent))

    user.ip = requests.get("https://api.ipify.org").text
    req = requests.get('http://ip-api.com/json/{}'.format(user.ip))
    json = req.json()
    user.city = json['city']
    user.country = json['country']
    return render_template('index.html', page_title="Welcome")



@app.route('/search', methods=['POST'])
def search_form_post():
    analytics_data.fact_requests.append(Requests(datetime.now(), request))
    search_query = request.form['search-query']

    session['last_search_query'] = search_query
    search_id = random.randint(0, 100000)
    results = search_engine.search(search_query, search_id, corpus)

    found_count = len(results)
    session['last_found_count'] = found_count

    search_id = analytics_data.save_query_terms(search_query, results)
    print(session)

    return render_template('results.html', results_list=results, page_title="Results", found_counter=found_count)


@app.route('/doc_details', methods=['GET'])
def doc_details():
    # getting request parameters:
    # user = request.args.get('user')
    analytics_data.fact_requests.append(Requests(datetime.now(), request))

    print("doc details session: ")
    print(session['last_search_query'])
    print(session)

    res = session["some_var"]

    print("recovered var from session:", res)
    # startDwell=datetime.now()
    # get the query string parameters from request
    clicked_doc_id = request.args["id"]
    p1 = int(request.args["search_id"])  # transform to Integer
    p2 = int(request.args["param2"])  # transform to Integer
    print("click in id={}".format(clicked_doc_id))

    # store data in statistics table 1
    if clicked_doc_id in analytics_data.fact_clicks.keys():
        analytics_data.fact_clicks[clicked_doc_id] += 1
        analytics_data.fact_queries[clicked_doc_id].append(session['last_search_query'])
    else:
        analytics_data.fact_clicks[clicked_doc_id] = 1
        analytics_data.fact_queries[clicked_doc_id] = [session['last_search_query']]

    analytics_data.queries[-1].append(clicked_doc_id)
    analytics_data.get_rank_of_clicked_doc()
    analytics_data.sessions.append(session)

    print("fact_clicks count for id={} is {}".format(clicked_doc_id, analytics_data.fact_clicks[clicked_doc_id]))
    ll = list(corpus.values())
    id_ = 0
    title_ = 0
    description_ = 0
    doc_date_ = 0
    likes_ = 0
    retweets_ = 0
    url_ = 0
    hashtags_ = 0

    for i in range(len(ll)):
        tweet: Document = ll[i]
        if int(clicked_doc_id) == tweet.id:
            id_ = tweet.id
            title_ = tweet.title
            username_ = tweet.username
            description_ = tweet.description
            doc_date_ = tweet.doc_date
            likes_ = tweet.likes
            retweets_ = tweet.retweets
            url_ = tweet.url
            hashtags_ = tweet.hashtags
            break

    return render_template('doc_details.html', id=id_, title=title_, username=username_, description=description_,
                           doc_date=doc_date_,
                           likes=likes_, retweets=retweets_, url=url_, hashtags=hashtags_)


@app.route('/stats', methods=['GET'])
def stats():
    """
    Show simple statistics example. ### Replace with dashboard ###
    :return:
    """
    analytics_data.fact_requests.append(Requests(datetime.now(), request))
    sessions_ = analytics_data.sessions

    queries_ = reversed(analytics_data.queries)
    docs = []
    # ### Start replace with your code ###

    for doc_id in analytics_data.fact_clicks:
        row: Document = corpus[int(doc_id)]
        count = analytics_data.fact_clicks[doc_id]
        queries = analytics_data.fact_queries[doc_id]
        doc = StatsDocument(row.id, row.title, row.description, row.doc_date, row.url, count, queries)
        docs.append(doc)

    # simulate sort by ranking
    docs.sort(key=lambda doc: doc.count, reverse=True)

    agent_ = analytics_data.agent

    browser = agent_['browser']
    browser_str = ""
    for item in browser:
        browser_str = browser_str + browser[item] + " "
    user.browser = browser_str

    ops = agent_['os']
    os_str = ""
    for item in ops:
        os_str = os_str + ops[item] + " "
    user.os = os_str

    return render_template('stats.html', clicks_data=docs, sessions=sessions_, queries=queries_, user=user,
                           requests=analytics_data.fact_requests)
    # ### End replace with your code ###


@app.route('/dashboard', methods=['GET'])
def dashboard():
    analytics_data.fact_requests.append(Requests(datetime.now(), request))

    visited_docs = []
    print(analytics_data.fact_clicks.keys())
    for doc_id in analytics_data.fact_clicks.keys():
        d: Document = corpus[int(doc_id)]
        doc = ClickedDoc(doc_id, d.description, analytics_data.fact_clicks[doc_id])
        visited_docs.append(doc)

    # simulate sort by ranking
    visited_docs.sort(key=lambda doc: doc.counter, reverse=True)
    visited_ser = []
    for doc in visited_docs:
        visited_ser.append(doc.to_json())

    query_counter = {}
    term_counter = {}
    length_dict = {}
    for query in analytics_data.queries:
        if query[0] not in query_counter:
            query_counter[query[0]] = 1
        else:
            query_counter[query[0]] += 1

        terms = query[0].split()
        for term in terms:
            if term not in term_counter:
                term_counter[term] = 1
            else:
                term_counter[term] += 1

        n_terms = query[1]
        if n_terms not in length_dict:
            length_dict[n_terms] = 1
        else:
            length_dict[n_terms] += 1

    return render_template('dashboard.html', visited_docs=visited_ser, visited_queries=query_counter,
                           visited_terms=term_counter, query_lengths=length_dict)


@app.route('/sentiment')
def sentiment_form():
    return render_template('sentiment.html')


@app.route('/sentiment', methods=['POST'])
def sentiment_form_post():
    text = request.form['text']
    nltk.download('vader_lexicon')
    from nltk.sentiment.vader import SentimentIntensityAnalyzer
    sid = SentimentIntensityAnalyzer()
    score = ((sid.polarity_scores(str(text)))['compound'])
    return render_template('sentiment.html', score=score)


if __name__ == "__main__":
    app.run(port=8088, host="0.0.0.0", threaded=False, debug=True)
