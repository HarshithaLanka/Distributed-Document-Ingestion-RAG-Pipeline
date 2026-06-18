#This file handles file saving
# Basically this file allows uploads to store on local storage

#This is used for copy uploaded file content in local storage
import shutil

#import path to work with paths
from pathlib import Path

from fastapi import UploadFile

#import upload folde path from config
from app.config import UPLOAD_DIR

#Define a function save uploaded PDF locally

def save_pdf_locally(file: UploadFile,document_id: str) -> str:
    #Create a folder path for this specific document
    #Example :uploads/doc_897854d8d
    
    document_folder=UPLOAD_DIR/document_id
    
    #So final path Example : uploads/doc_8f2591c/sample.pdf
    #Create a document folder if it does not exist
    document_folder.mkdir(parents=True,exist_ok=True)
    
    #Create the final file path using the original filename
    file_path=document_folder/file.filename
    
    #Open the destination file in write-binary mode
    with open(file_path, "wb") as buffer:
        
        #copy uploaded file content into destination file
        
        shutil.copyfileobj(file.file,buffer)
    return str(file_path)
    
    