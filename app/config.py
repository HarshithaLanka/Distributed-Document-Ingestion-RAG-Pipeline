# Import Path from pathlib to work with files and folder paths safely
from pathlib import Path

#Base_dir means root folder of the project
#example :document-intelligence-rag/
BASE_DIR=Path(__file__).resolve().parent.parent


#Upload_dir is the folder where uplaoded files will be saved
#example :document-intelligence-rag/uploads

UPLOAD_DIR= BASE_DIR / "uploads" 

#Data_dir is the folder where local json data files will be saved
#example :document-intelligence-rag/app/data/
DATA_DIR=BASE_DIR/"app"/"data"


#Document json path is the path to our temperory database
#example :document-intelligence-rag/app/data/documents.json

DOCUMENTS_JSON_PATH=DATA_DIR/"documents.json"

#Create uploads folder if it does not exist

UPLOAD_DIR.mkdir(parents=True,exist_ok=True)

#Create app/data dolder if it doesnot exists

DATA_DIR.mkdir(parents=True,exist_ok=True)

