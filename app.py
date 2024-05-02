from flask import Flask, render_template, request
import search_process
import search_author

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    query = request.form['query']
    pubmed_query = request.form['PubMedQuery']

    results, author_count = search_process.search(query, pubmed_query)
    return render_template('results.html', query=query, results=results, author_count=author_count)

@app.route('/search_author', methods=['POST'])
def search_authors():
    query = request.form['query']
    pubmed_query = request.form['PubMedQuery']
    #author_query = request.form['author']

    results, author_count = search_author.search(query, pubmed_query )
    return render_template('results.html', query=query, results=results, author_count=author_count)

if __name__ == '__main__':
    app.run(debug=True)
