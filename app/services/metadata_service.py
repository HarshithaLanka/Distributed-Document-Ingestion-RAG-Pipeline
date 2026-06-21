#This file acts as tiny local database

#import read and write json files
import json

#import List and Optional for type hints
from typing import List,Optional

#import metadata json path from config
from app.config import DOCUMENTS_JSON_PATH

# This function reads all document metadata from documents.json.
def load_documents() -> List[dict]:
    # If documents.json does not exist, return an empty list.
    if not DOCUMENTS_JSON_PATH.exists():
        return []

    # If documents.json exists but is empty, return an empty list.
    if DOCUMENTS_JSON_PATH.stat().st_size == 0:
        return []

    # Open documents.json in read mode.
    with open(DOCUMENTS_JSON_PATH, "r") as file:
        # Load JSON data from the file.
        data = json.load(file)

    # Return all documents.
    return data

#Define a function to save all document metadata records

def save_documents(documents: List[dict]) -> None:
    
    #Open the json file in write mode
    with open(DOCUMENTS_JSON_PATH, "w") as file:
        #Save the documents list in json file with nice formatting
        
        json.dump(documents,file,indent=4)
        
#define a function to add one new document metadata record

def add_document_metadata(document: dict) -> None:
    #Load existing documents from JSON
    documents=load_documents()
    
    #Add the new document to the list
    documents.append(document)
    
    #Save the updated list back to json
    save_documents(documents)
    
def get_document_by_id(document_id:str)-> Optional[dict]:
    #Load all documents
    documents=load_documents()
    
    #Loop through each document
    for document in documents:
        #Check if current document ID matches the requested ID
        if document["document_id"]== document_id:
            #return the matching document
            return document
    #if no document matched ,return
    return None
        
# Define a function to update metadata for one document.
def update_document_metadata(document_id: str, updates: dict) -> Optional[dict]:
    # Load all existing documents.
    documents = load_documents()

    # Loop through all documents with index.
    for index, document in enumerate(documents):
        # Check if current document matches requested document_id.
        if document["document_id"] == document_id:
            # Update the document dictionary with new values.
            document.update(updates)

            # Replace old document with updated document.
            documents[index] = document

            # Save updated documents back to JSON.
            save_documents(documents)

            # Return updated document.
            return document

    # If document_id is not found, return None.
    return None