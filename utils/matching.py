from typing import List
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
 
# must match the model used in build_vector_index.py
emb_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
 
 
def semantic_candidates_from_db(question, top_k=15, persist_dir="./census_var_concepts") -> List[str]:
    db = Chroma(embedding_function=emb_model, persist_directory=persist_dir)
    docs = db.similarity_search(question, k=top_k)
    return [d.metadata["concept"] for d in docs]