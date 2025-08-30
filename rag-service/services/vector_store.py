from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Dict, Any
import os
import uuid

class VectorStoreService:
    def __init__(self):
        self.qdrant_host = os.getenv("QDRANT_HOST", "localhost")
        self.qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
        self.collection_name = "websearch_documents"
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.vector_size = 384
        
        # Qdrant 클라이언트 초기화
        self.client = QdrantClient(host=self.qdrant_host, port=self.qdrant_port)
        self._init_collection()
    
    def _init_collection(self):
        """컬렉션 초기화"""
        try:
            # 컬렉션이 존재하는지 확인
            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]
            
            if self.collection_name not in collection_names:
                # 새 컬렉션 생성
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=Distance.COSINE
                    )
                )
                print(f"Created collection: {self.collection_name}")
            else:
                print(f"Collection {self.collection_name} already exists")
                
        except Exception as e:
            print(f"Error initializing collection: {e}")
    
    def add_documents(self, documents: List[Dict[str, Any]]) -> List[str]:
        """문서들을 벡터 스토어에 추가"""
        try:
            points = []
            ids = []
            
            for doc in documents:
                # 텍스트 임베딩 생성
                text = doc.get('content', '')
                if not text.strip():
                    continue
                    
                embedding = self.embedding_model.encode(text).tolist()
                doc_id = str(uuid.uuid4())
                
                point = PointStruct(
                    id=doc_id,
                    vector=embedding,
                    payload={
                        'content': text,
                        'url': doc.get('url', ''),
                        'title': doc.get('title', ''),
                        'metadata': doc.get('metadata', {})
                    }
                )
                points.append(point)
                ids.append(doc_id)
            
            if points:
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
                print(f"Added {len(points)} documents to vector store")
            
            return ids
            
        except Exception as e:
            print(f"Error adding documents: {e}")
            return []
    
    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """쿼리와 유사한 문서 검색"""
        try:
            # 쿼리 임베딩 생성
            query_embedding = self.embedding_model.encode(query).tolist()
            
            # 벡터 검색 수행
            search_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=top_k,
                with_payload=True
            )
            
            # 결과 포맷팅
            results = []
            for result in search_results:
                results.append({
                    'content': result.payload.get('content', ''),
                    'url': result.payload.get('url', ''),
                    'title': result.payload.get('title', ''),
                    'score': result.score,
                    'metadata': result.payload.get('metadata', {})
                })
            
            return results
            
        except Exception as e:
            print(f"Error searching documents: {e}")
            return []
    
    def delete_collection(self):
        """컬렉션 삭제"""
        try:
            self.client.delete_collection(self.collection_name)
            print(f"Deleted collection: {self.collection_name}")
        except Exception as e:
            print(f"Error deleting collection: {e}")
    
    def get_collection_info(self) -> Dict[str, Any]:
        """컬렉션 정보 조회"""
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                'name': info.name,
                'vectors_count': info.vectors_count,
                'points_count': info.points_count
            }
        except Exception as e:
            print(f"Error getting collection info: {e}")
            return {}
    
    def is_healthy(self) -> bool:
        """서비스 상태 확인"""
        try:
            self.client.get_collections()
            return True
        except Exception:
            return False
