import requests
import roman
import re
import random
import math
from flask import current_app, session
from requests_oauthlib import OAuth1Session


def query_wikidata(query):
    url = "https://query.wikidata.org/sparql"
    params = {
        "query": query,
        "format": "json"
    }
    result = requests.get(url=url, params=params, headers={'User-agent': 'WikiMI QAM 1.0'})
    data = result.json()
    return data


def query_by_type(query, lang="pt-br"):
    new_query = query.replace("LANGUAGE", lang)
    data = query_wikidata(new_query)
    result = data["results"]["bindings"]

    images = []
    for image in result:
        images.append({
            "qid": image["item_qid"]["value"],
            "label": image["item_label"]["value"],
            "imagem": image["imagem"]["value"],
            "category": image["category"]["value"] if 'category' in image else '',
        })

    return images


def query_next_qid(query):
    data = query_wikidata(query)
    result = data["results"]["bindings"]
    items = []
    for item in result:
        if "obra_next_qid" in item:
            items.append(item["obra_next_qid"]["value"])
    try:
        next_qid = random.choice(items)
    except IndexError:
        next_qid = None
    return next_qid


def query_metadata_of_work(query, lang="pt-br"):
    data = query_wikidata(query)
    result = None
    if "results" in data and "bindings" in data["results"]:
        result = data["results"]["bindings"][0]
        format_dates_in_result(result, lang)
        get_values_lists(result)
        if "obra" in result and len(result["obra"]) > 0:
            result["obra_qid"] = [result["obra"][0].replace("http://www.wikidata.org/entity/", "")]
        if "category" in result and len(result["obra"]) > 0:
            result["category"] = result["category"][0]
    if not result or result == [{}]:
        result = ""
    return result


def query_motifs_metadata(query, qid):
    data = query_wikidata(query)
    result = data["results"]["bindings"]
    for motif_entity in result:
        get_values_lists(motif_entity, sep=";%;")
        if not motif_entity:
            return None
        if 'retrata_stat_id' in motif_entity:
            motif_entity['retrata_stat_id'][0] = "https://www.wikidata.org/wiki/" + \
                                                 qid + "#" + motif_entity['retrata_stat_id'][0].replace('-', '$', 1)
        else:
            motif_entity['retrata_stat_id'] = ['']
        if "retrata_descr" not in motif_entity:
            motif_entity["retrata_descr"] = ""
        if "retrata_label" not in motif_entity:
            motif_entity["retrata_label"] = ""
        if "retrata_qid" not in motif_entity:
            motif_entity["retrata_qid"] = ""
    return result


def api_category_members(category):
    url = 'https://commons.wikimedia.org/w/api.php'
    params = {
        'action': 'query',
        'generator': 'categorymembers',
        'gcmtype': 'file',
        'gcmtitle': category,
        'gcmlimit': 'max',
        'format': 'json'
    }
    result = requests.get(url=url, params=params, headers={'User-agent': 'WikiMI CQREV 1.0'})
    data = result.json()

    category_images = []
    if "query" in data and "pages" in data["query"]:
        for page in data["query"]["pages"]:
            category_images.append(data["query"]["pages"][page]["title"][5:])

    return category_images


def format_dates_in_result(result, lang="pt-br"):
    if "data" in result:
        datas = result["data"]["value"].split(";")
        novas_datas = []
        for data in datas:
            novas_datas.append(format_dates(data, lang))
        result["data"]["value"] = ";".join(novas_datas)


def format_dates(time, lang="pt-br"):
    year, month, day, precision = list(map(int, re.findall(r'\d+', time)))
    if precision == 7:
        if lang == "en":
            date = "%dth century" % (int(year / 100) + 1)
        else:
            if year % 100 == 0:
                date = "Século %s" % (roman.toRoman(math.floor(year / 100)))
            else:
                date = "Século %s" % (roman.toRoman(math.floor(year / 100) + 1))
    elif precision == 8:
        if lang == "en":
            date = "%ds" % (int(year / 10) * 10)
        else:
            date = "Década de %d" % (int(year / 10) * 10)
    elif precision == 9:
        date = "%d" % year
    elif precision == 10:
        date = "%d/%d" % (month, year)
    elif precision == 11:
        if lang == "en":
            date = "%d/%d/%d" % (month, day, year)
        else:
            date = "%d/%d/%d" % (day, month, year)
    else:
        date = ""
    return date


def get_values_lists(result, sep=";"):
    for metadata_key, metadata_dict in result.items():
        result[metadata_key] = list(filter(None, metadata_dict["value"].split(sep)))


def api_post_request(params):
    app = current_app
    url = 'https://www.wikidata.org/w/api.php'
    client_key = app.config['CONSUMER_KEY']
    client_secret = app.config['CONSUMER_SECRET']
    oauth = OAuth1Session(client_key,
                          client_secret=client_secret,
                          resource_owner_key=session['owner_key'],
                          resource_owner_secret=session['owner_secret'])
    return oauth.post(url, data=params, timeout=4)


def post_search_entity(term, lang="pt-br"):
    url = 'https://www.wikidata.org/w/api.php'
    params = {
        'action': 'wbsearchentities',
        'search': term,
        'language': lang,
        'format': 'json',
        'limit': 50,
        'uselang': lang,
    }
    result = requests.get(url=url, params=params, headers={'User-agent': 'WikiMI QaM 1.0'})
    data = result.json()

    return data


def filter_by_instancia(qids, lang="pt-br"):
    if lang == "pt-br" or lang == "pt":
        lang = "pt-br,pt"
    data = query_wikidata("SELECT DISTINCT ?item_qid ?item_label ?item_descr WHERE { "
                          "SERVICE wikibase:label {bd:serviceParam wikibase:language '"
                          + lang +
                          "'. ?item rdfs:label ?item_label. ?item schema:description ?item_descr.} "
                          "VALUES ?item {"
                          + qids +
                          "} VALUES ?instancia {wd:Q6881511 wd:Q4830453 wd:Q431289 wd:Q1412386 wd:Q167270 wd:Q5} "
                          "?item wdt:P31/wdt:P279* ?instancia. BIND(SUBSTR(STR(?item),32) AS ?item_qid) }")
    results = data["results"]["bindings"]
    query = []
    for item in results:
        if "item_qid" in item:
            qid = item["item_qid"]["value"]
        else:
            qid = ""
        if "item_label" in item:
            label = item["item_label"]["value"]
        else:
            label = ""
        if "item_descr" in item:
            descr = item["item_descr"]["value"]
        else:
            descr = ""
        query.append({"qid": qid,
                      "label": label,
                      "descr": descr})
    return query


def query_quantidade(query):
    data = query_wikidata(query)
    try:
        valor = int(data["results"]["bindings"][0]["number_works"]["value"])
    except IndexError:
        valor = 0
    return valor


def filter_by_category(data, cat):
    qids = "wd:" + " wd:".join([x["id"] for x in data["search"]])
    filtered_items = []

    categories = {
        "Elementos da natureza": "SELECT DISTINCT ?item (SAMPLE(STR(?itemLabelptbr)) AS ?labelptbr) (SAMPLE(STR(?itemDescriptionptbr)) AS ?descrptbr) (SAMPLE(STR(?itemLabelpt)) AS ?labelpt) (SAMPLE(STR(?itemDescriptionpt)) AS ?descrpt) (SAMPLE(STR(?itemLabelen)) AS ?labelen) (SAMPLE(STR(?itemDescriptionen)) AS ?descren) WITH { SELECT DISTINCT ?item WHERE { VALUES ?item {" + qids + "} { ?item wdt:P31 wd:Q16521. } UNION { ?item (wdt:P279/(wdt:P279*)) wd:Q16521. } UNION { ?item (wdt:P279/wdt:P31) wd:Q55983715. } UNION { ?item wdt:P31 wd:Q55983715. } UNION { ?item wdt:P31 wd:Q16521. } UNION { ?item (wdt:P31/wdt:P279) wd:Q38829. } UNION {?item wdt:P31 wd:Q12089225.} UNION {?item wdt:P279/wdt:P31* wd:Q12089225.} UNION {?item wdt:P279/wdt:P279* wd:Q8063.} UNION {?item wdt:P361 wd:Q764.}}} AS %items WHERE { INCLUDE %items. OPTIONAL{?item rdfs:label ?itemLabelptbr. FILTER(LANG(?itemLabelptbr)='pt-br')} OPTIONAL{?item schema:description ?itemDescriptionptbr. FILTER(LANG(?itemDescriptionptbr)='pt-br')} OPTIONAL{?item rdfs:label ?itemLabelpt. FILTER(LANG(?itemLabelpt)='pt')} OPTIONAL{?item schema:description ?itemDescriptionpt. FILTER(LANG(?itemDescriptionpt)='pt')} OPTIONAL{?item rdfs:label ?itemLabelen. FILTER(LANG(?itemLabelen)='en')} OPTIONAL{?item schema:description ?itemDescriptionen. FILTER(LANG(?itemDescriptionen)='en')}} GROUP BY ?item",
        "Ornamentos arquitetônicos": "SELECT DISTINCT ?item (SAMPLE(STR(?itemLabelptbr)) AS ?labelptbr) (SAMPLE(STR(?itemDescriptionptbr)) AS ?descrptbr) (SAMPLE(STR(?itemLabelpt)) AS ?labelpt) (SAMPLE(STR(?itemDescriptionpt)) AS ?descrpt) (SAMPLE(STR(?itemLabelen)) AS ?labelen) (SAMPLE(STR(?itemDescriptionen)) AS ?descren) WITH { SELECT DISTINCT ?item WHERE { VALUES ?item {" + qids + "} {?item wdt:P279? wd:Q183272.} UNION {?item wdt:P279? wd:Q12277.} UNION {?item wdt:P279/wdt:P279* wd:Q391414.}}} AS %items WHERE { INCLUDE %items. OPTIONAL{?item rdfs:label ?itemLabelptbr. FILTER(LANG(?itemLabelptbr)='pt-br')} OPTIONAL{?item schema:description ?itemDescriptionptbr. FILTER(LANG(?itemDescriptionptbr)='pt-br')} OPTIONAL{?item rdfs:label ?itemLabelpt. FILTER(LANG(?itemLabelpt)='pt')} OPTIONAL{?item schema:description ?itemDescriptionpt. FILTER(LANG(?itemDescriptionpt)='pt')} OPTIONAL{?item rdfs:label ?itemLabelen. FILTER(LANG(?itemLabelen)='en')} OPTIONAL{?item schema:description ?itemDescriptionen. FILTER(LANG(?itemDescriptionen)='en')}} GROUP BY ?item",
        "Seres mitológicos": "SELECT DISTINCT ?item (SAMPLE(STR(?itemLabelptbr)) AS ?labelptbr) (SAMPLE(STR(?itemDescriptionptbr)) AS ?descrptbr) (SAMPLE(STR(?itemLabelpt)) AS ?labelpt) (SAMPLE(STR(?itemDescriptionpt)) AS ?descrpt) (SAMPLE(STR(?itemLabelen)) AS ?labelen) (SAMPLE(STR(?itemDescriptionen)) AS ?descren) WITH {SELECT DISTINCT ?item WHERE { VALUES ?item {" + qids + "} {?item wdt:P31/wdt:P279* wd:Q21070598.} UNION {?item wdt:P31/wdt:P279* wd:Q24334685.} UNION {?item wdt:P31/wdt:P279* wd:Q95074.}}} AS %items WHERE { INCLUDE %items. OPTIONAL{?item rdfs:label ?itemLabelptbr. FILTER(LANG(?itemLabelptbr)='pt-br')} OPTIONAL{?item schema:description ?itemDescriptionptbr. FILTER(LANG(?itemDescriptionptbr)='pt-br')} OPTIONAL{?item rdfs:label ?itemLabelpt. FILTER(LANG(?itemLabelpt)='pt')} OPTIONAL{?item schema:description ?itemDescriptionpt. FILTER(LANG(?itemDescriptionpt)='pt')} OPTIONAL{?item rdfs:label ?itemLabelen. FILTER(LANG(?itemLabelen)='en')} OPTIONAL{?item schema:description ?itemDescriptionen. FILTER(LANG(?itemDescriptionen)='en')}} GROUP BY ?item",
        "Transporte": "SELECT DISTINCT ?item (SAMPLE(STR(?itemLabelptbr)) AS ?labelptbr) (SAMPLE(STR(?itemDescriptionptbr)) AS ?descrptbr) (SAMPLE(STR(?itemLabelpt)) AS ?labelpt) (SAMPLE(STR(?itemDescriptionpt)) AS ?descrpt) (SAMPLE(STR(?itemLabelen)) AS ?labelen) (SAMPLE(STR(?itemDescriptionen)) AS ?descren) WITH { SELECT DISTINCT ?item WHERE { VALUES ?item {" + qids + "} {?item wdt:P279* wd:Q334166.} UNION {?item wdt:P31/wdt:P279* wd:Q334166} UNION {?item wdt:P279/wdt:P31 wd:Q334166}}} AS %items WHERE { INCLUDE %items. OPTIONAL{?item rdfs:label ?itemLabelptbr. FILTER(LANG(?itemLabelptbr)='pt-br')} OPTIONAL{?item schema:description ?itemDescriptionptbr. FILTER(LANG(?itemDescriptionptbr)='pt-br')} OPTIONAL{?item rdfs:label ?itemLabelpt. FILTER(LANG(?itemLabelpt)='pt')} OPTIONAL{?item schema:description ?itemDescriptionpt. FILTER(LANG(?itemDescriptionpt)='pt')} OPTIONAL{?item rdfs:label ?itemLabelen. FILTER(LANG(?itemLabelen)='en')} OPTIONAL{?item schema:description ?itemDescriptionen. FILTER(LANG(?itemDescriptionen)='en')}} GROUP BY ?item",
        "Outros": "SELECT DISTINCT ?item (SAMPLE(STR(?itemLabelptbr)) AS ?labelptbr) (SAMPLE(STR(?itemDescriptionptbr)) AS ?descrptbr) (SAMPLE(STR(?itemLabelpt)) AS ?labelpt) (SAMPLE(STR(?itemDescriptionpt)) AS ?descrpt) (SAMPLE(STR(?itemLabelen)) AS ?labelen) (SAMPLE(STR(?itemDescriptionen)) AS ?descren) WITH { SELECT DISTINCT ?item WHERE { VALUES ?item {" + qids + "} } } AS %items WHERE { INCLUDE %items. OPTIONAL{?item rdfs:label ?itemLabelptbr. FILTER(LANG(?itemLabelptbr)='pt-br')} OPTIONAL{?item schema:description ?itemDescriptionptbr. FILTER(LANG(?itemDescriptionptbr)='pt-br')} OPTIONAL{?item rdfs:label ?itemLabelpt. FILTER(LANG(?itemLabelpt)='pt')} OPTIONAL{?item schema:description ?itemDescriptionpt. FILTER(LANG(?itemDescriptionpt)='pt')} OPTIONAL{?item rdfs:label ?itemLabelen. FILTER(LANG(?itemLabelen)='en')} OPTIONAL{?item schema:description ?itemDescriptionen. FILTER(LANG(?itemDescriptionen)='en')}} GROUP BY ?item"
        # "Cabelos, barbas e bigodes": "SELECT DISTINCT ?item WHERE { VALUES ?item {" + qids + "} {?item_ wdt:P8839 ?item.} UNION {?item wdt:P31|wdt:P279* wd:Q327496.} UNION {?item wdt:P31|wdt:P279* wd:Q42804.} UNION {?item wdt:P31|wdt:P279* wd:Q15179.} }",
    }

    if cat in categories:
        _filter = query_wikidata(categories[cat])
        results = _filter["results"]["bindings"]
        filtered_items = extract_items(results)
    else:
        filtered_items = [{"id": x["id"],
                           "labelptbr": x["label"] if "label" in x else "",
                           "labelpt": x["label"] if "label" in x else "",
                           "labelen": x["label"] if "label" in x else "",
                           "descrptbr": x["description"] if "description" in x else "",
                           "descrpt": x["description"] if "description" in x else "",
                           "descren": x["description"] if "description" in x else ""} for x in data["search"]]
    # new_data = [search_result for search_result in data["search"] if search_result["id"] in filtered_items]

    return filtered_items


def extract_items(results):
    items = []
    for result in results:
        items.append({"id": result["item"]["value"].replace("http://www.wikidata.org/entity/", ""),
                      "labelptbr": result["labelptbr"]["value"] if "labelptbr" in result else "",
                      "labelpt": result["labelpt"]["value"] if "labelpt" in result else "",
                      "labelen": result["labelen"]["value"] if "labelen" in result else "",
                      "descrptbr": result["descrptbr"]["value"] if "descrptbr" in result else "",
                      "descrpt": result["descrpt"]["value"] if "descrpt" in result else "",
                      "descren": result["descren"]["value"] if "descren" in result else "",
                      })
    return items