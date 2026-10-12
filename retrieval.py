import chromadb
from rank_bm25 import BM25Okapi
from data_loader import(
    load_text_folder,
    load_sample_complaints,
    REGULATIONS_FOLDER,
    GUIDANCE_FOLDER
)
client=chromadb.PersistentClient(path="chroma_db")
RRF_k=60

def build_collections():
    regulations_collection=client.get_or_create_collection("regulations")
    guidance_collection=client.get_or_create_collection("guidance")
    complaints_collection=client.get_or_create_collection("complaints")

    if regulations_collection.count()==0:
        docs=load_text_folder(REGULATIONS_FOLDER)
        regulations_collection.add(
            documents=[d["text"] for d in docs],
            ids=[d["source"] for d in docs],
            metadatas=[{"category":d["category"]} for d in docs]
        )
        print("Added", len(docs),"documents to regulations collection")
    if guidance_collection.count()==0:
        docs=load_text_folder(GUIDANCE_FOLDER)
        guidance_collection.add(
            documents=[d["text"] for d in docs],
            ids=[d["source"] for d in docs],
            metadatas=[{"category":d["category"]} for d in docs]
        )
        print("Added",len(docs),"documents to guidance collection")
    if complaints_collection.count()==0:
        docs=load_sample_complaints()
        complaints_collection.add(
            documents=[d["text"] for d in docs],
            ids=["complaint_"+str(i) for i in range(len(docs))],
            metadatas=[{"category":d["category"]} for d in docs]
        )
        print("Added",len(docs),"documents to complaints collection")

    return regulations_collection,guidance_collection,complaints_collection

def vector_search(collection,query_text,category,top_k):
    results=collection.query(
        query_texts=[query_text],
        n_results=top_k,
        where={"category":category}
    )
    return results["documents"][0]

def keyword_search(collection,query_text,category,top_k):
    matches=collection.get(where={"category":category})
    documents=matches["documents"]
    if len(documents)==0:
        return []
    tokenized_docs=[doc.lower().split() for doc in documents]
    bm25=BM25Okapi(tokenized_docs)
    tokenized_query=query_text.lower().split()
    scores=bm25.get_scores(tokenized_query)
    scored_docs=list(zip(documents,scores))
    scored_docs.sort(key=lambda pair:pair[1],reverse=True)
    top_docs=[doc for doc,score in scored_docs[:top_k]]
    return top_docs

def reciprocal_rank_fusion(vector_results,keyword_results,top_k):
    scores={}
    for rank,doc in enumerate(vector_results):
        scores[doc]=scores.get(doc,0)+1/(RRF_k+rank)
    for rank,doc in enumerate(keyword_results):
        scores[doc]=scores.get(doc,0)+1/(RRF_k+rank)
    ranked_docs=sorted(scores.keys(),key=lambda doc:scores[doc],reverse=True)
    return ranked_docs[:top_k]

def hybrid_search(collection,query_text,category,top_k=3):
    vector_results=vector_search(collection,query_text,category,top_k=10)
    keyword_results=keyword_search(collection,query_text,category,top_k=10)
    return reciprocal_rank_fusion(vector_results,keyword_results,top_k)

def search_all_buckets(complaint_text,category,top_k=3):
    regulations_collection,guidance_collection,complaints_collection=build_collections()
    return{
        "regulatory_docs":hybrid_search(regulations_collection,complaint_text,category,top_k),
        "complaint_handling_guidance":hybrid_search(guidance_collection,complaint_text,category,top_k),
        "similar_historical_complaints":hybrid_search(complaints_collection,complaint_text,category,top_k)
    }
