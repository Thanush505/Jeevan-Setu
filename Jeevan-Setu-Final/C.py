import chromadb

client = chromadb.PersistentClient(
    path="./vector_storage"
)

print("Connected to Jeevan Setu ChromaDB!")

print("Available collections:")

for collection in client.list_collections():
    print(collection.name)