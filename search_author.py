import xml.etree.ElementTree as ET
import requests as req
import nltk
from collections import Counter
from math import log, sqrt
from markupsafe import Markup
import html

class article:
    def __init__(self, title, author, abstract):
        self.title = title
        self.author =  author
        self.abstract = abstract

def get_articles(term):
    eSearchResult = req.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term="+term+"&reldate=60&retmax=1000&usehistory=y")

    eSearchResult_xml = ET.fromstring(eSearchResult.text)

    WebEnv = eSearchResult_xml.find("WebEnv").text

    # Get details of the search result(efetch)
    summary = req.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=Pubmed&retmode=xml&rettype=abstract&term="+term+"&query_key=1&retstart=0&retmax=1000&WebEnv="+WebEnv)

    summary_xml = ET.fromstring(summary.text)

    articles = []
    for i in summary_xml.findall(".//PubmedArticle"):
        title = "".join(i.find(".//ArticleTitle").itertext())
        try:
            author = "".join(i.find(".//LastName").itertext()) + ", " + "".join(i.find(".//ForeName").itertext())
            #print(author)
        except:
            # No author found
            author = ""
        try:
            abstract = "".join(i.find(".//AbstractText").itertext())
        except:
            # No abstract found
            abstract = ""
        articles.append(article(title, author, abstract))
    return articles 

def vbyte_encode(num):

    # out_bytes 儲存轉換成Vbyte壓縮後的格式
    out_bytes = []
    
    while num >= 128:
        out_bytes.append(int(num) % 128)
        num /= 128
        
    out_bytes.append(int(num) + 128)
    
    return out_bytes

def vbyte_decode(input_bytes, idx):
    
    x = 0 # 儲存解壓縮後的數字
    s = 0
    consumed = 0 # 記錄花了多少位元組來解壓這個數字
    
    while input_bytes[idx + consumed] < 128:
        x ^= (input_bytes[idx + consumed] << s)
        s += 7
        consumed += 1
    
    x ^= ((input_bytes[idx + consumed]-128) << s)
    consumed += 1
    
    return x, consumed

def decompress_list(input_bytes, gapped_encoded):
    res = []
    prev = 0
    idx = 0
    while idx < len(input_bytes):
        dec_num, consumed_bytes = vbyte_decode(input_bytes, idx)
        idx += consumed_bytes
        num = dec_num + prev
        res.append(num)
        if gapped_encoded:
            prev = num
    return res

def query_tfidf(query, index, k=10):
    
    scores = Counter()
    
    N = index.num_docs()
    
    for term in query:
        i = 0
        f_t = index.f_t(term)
        for docid in index.docids(term):
            # f_(d,t)
            f_d_t = index.freqs(term)[i]
            d = index.doc_len[docid]
            tfidf_cal = log(1+f_d_t) * log(N/f_t) / sqrt(d)
            scores[docid] += tfidf_cal
            i += 1
    
    return scores.most_common(k)

class CompressedInvertedIndex:
    def __init__(self, vocab, doc_term_freqs):
        self.vocab = vocab
        self.doc_len = [0] * len(doc_term_freqs)
        self.doc_term_freqs = [[] for i in range(len(vocab))]
        self.doc_ids = [[] for i in range(len(vocab))]
        self.doc_freqs = [0] * len(vocab)
        self.total_num_docs = 0
        self.max_doc_len = 0
        for docid, term_freqs in enumerate(doc_term_freqs):
            doc_len = sum(term_freqs.values())
            self.max_doc_len = max(doc_len, self.max_doc_len)
            self.doc_len[docid] = doc_len
            self.total_num_docs += 1
            for term, freq in term_freqs.items():
                term_id = vocab[term]
                self.doc_ids[term_id].append(docid)
                self.doc_term_freqs[term_id].append(freq)
                self.doc_freqs[term_id] += 1
        
        # 壓縮文件ID之間的間隔
        for i in range(len(self.doc_ids)):
            last_docid = self.doc_ids[i][0]
            for j in range(len(self.doc_ids[i])):
                if j != 0:
                    ori_docid = self.doc_ids[i][j]
                    self.doc_ids[i][j] = vbyte_encode(self.doc_ids[i][j] - last_docid)
                    last_docid = ori_docid
                else:
                    self.doc_ids[i][0] = vbyte_encode(last_docid)
            self.doc_ids[i] = sum(self.doc_ids[i], [])
            
        # 根據詞頻壓縮
        for i in range(len(self.doc_term_freqs)):
            for j in range(len(self.doc_term_freqs[i])):
                self.doc_term_freqs[i][j] = vbyte_encode(self.doc_term_freqs[i][j])
            self.doc_term_freqs[i] = sum(self.doc_term_freqs[i], [])
    
    def num_terms(self):
        return len(self.doc_ids)

    def num_docs(self):
        return self.total_num_docs

    def docids(self, term):
        term_id = self.vocab[term]
        # 解壓縮
        return decompress_list(self.doc_ids[term_id], True)

    def freqs(self, term):
        term_id = self.vocab[term]
        # 解壓縮
        return decompress_list(self.doc_term_freqs[term_id], False)

    def f_t(self, term):
        try:
            term_id = self.vocab[term]
            return self.doc_freqs[term_id]
        except:
            self.vocab[term] = len(self.vocab)
            self.doc_ids.append([])
            self.doc_term_freqs.append([])
            self.doc_freqs.append(0)
            return 0

    def space_in_bytes(self):
        # 這裡現在假設數字都是位元組型態
        space_usage = 0
        for doc_list in self.doc_ids:
            space_usage += len(doc_list)
        for freq_list in self.doc_term_freqs:
            space_usage += len(freq_list)
        return space_usage

def search(search_query,pubmedquery, k=10):
    query_list = search_query.split()
    pubmedquery_list = pubmedquery.split()
    docs = []
    for q in pubmedquery_list:
        docs.extend(get_articles(q))
    # docs.extend(get_articles(search_query[:search_query.find(" ")]))
    # docs.extend(get_articles(search_query[search_query.find(" ")+1:search_query.rfind(" ")]))
    # docs.extend(get_articles(search_query[search_query.rfind(" ")+1:]))

    raw_docs = []
    raw_titles = []
    raw_authors = []
    raw_abstracts = []
    for doc in docs:
        raw_titles.append(doc.title)
        raw_docs.append(doc.author)
        raw_abstracts.append(doc.abstract)
        raw_authors.append(doc.author)

    processed_docs = []

    vocab = {}

    total_tokens = 0


    stemmer = nltk.stem.PorterStemmer()

    for raw_doc in raw_docs:
        
        norm_doc = []
        
        tokenized_document = nltk.word_tokenize(raw_doc)
        for token in tokenized_document:
            stemmed_token = stemmer.stem(token).lower()
            norm_doc.append(stemmed_token)

            total_tokens += 1
            
            if stemmed_token not in vocab:
                vocab[stemmed_token] = len(vocab)
                
        processed_docs.append(norm_doc)

    doc_term_freqs = []

    for norm_doc in processed_docs:
        tfs = Counter()

        for token in norm_doc:
            tfs[token] += 1
        doc_term_freqs.append(tfs)

    compressed_index = CompressedInvertedIndex(vocab, doc_term_freqs)

    query = search_query
    stemmed_query = nltk.stem.PorterStemmer().stem(query).split()
    comp_results = query_tfidf(stemmed_query, compressed_index, k+10)
    results = []
    author_count = {}
    counter = 0
    for rank, res in enumerate(comp_results):
        # result 中title重複不計入
        if raw_titles[res[0]] in [r["title"] for r in results]:
            continue
        r = {}
        r["rank"] = rank+1
        r["score"] = res[1]
        r["title"] = raw_titles[res[0]]
        r["author"] = raw_authors[res[0]]
        if r["author"] in author_count:
            author_count[r["author"]][0] += 1
            author_count[r["author"]][1].append(r["title"])
        else:
            author_count[r["author"]] = [1, [r["title"]]]
        r["abstract"] = raw_abstracts[res[0]]
        
        for i in range(len(stemmed_query)):
            r["author"] = r["author"].replace(stemmed_query[i].upper(), "<b><font color='red'>" + stemmed_query[i].upper() + "</font></b>", -1)
            r["author"] = r["author"].replace(stemmed_query[i], "<b><font color='red'>" + stemmed_query[i] + "</font></b>", -1)
            # r["title"] = r["title"].replace(stemmed_query[i], "<b><font color='red'>" + stemmed_query[i] + "</font></b> ", -1)
            # r["title"] = r["title"].replace(stemmed_query[i].upper(), "<b><font color='red'>" + stemmed_query[i].upper() + "</font></b> ", -1)
            # Markupsafe的Markup函數可以讓HTML tag不被escape
            #r["abstract"] = Markup(r["abstract"])
            # r["title"] = Markup(r["title"])
        #r["positions"] = positions

        # 取得query在文件中的詞頻
        term_freq = {}
        for token in processed_docs[res[0]]:
            if token not in stemmed_query:
                continue
            if token in term_freq:
                term_freq[token] += 1
            else:
                term_freq[token] = 1
        r["term_freq"] = term_freq
        results.append(r)
        counter += 1
        if counter == k:
            break
    return results, author_count
