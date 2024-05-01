from flask import Flask, render_template, request
import search_process

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    query = request.form['query']
    # 在這裡你可以使用你喜歡的搜尋演算法，這裡我們只是簡單地搜尋名字
    results, author_count = search_process.search(query)
    return render_template('results.html', query=query, results=results, author_count=author_count)

if __name__ == '__main__':
    app.run(debug=True)
