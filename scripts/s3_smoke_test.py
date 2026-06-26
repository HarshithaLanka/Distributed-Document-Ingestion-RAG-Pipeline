# Import sys so we can safely add the project root to Python path.
import sys

# Import Path so we can work with folder paths safely.
from pathlib import Path

# Import BytesIO so we can create a small fake file in memory.
from io import BytesIO

# Import boto3 so Python can talk to AWS S3.
import boto3

# Import ClientError so we can handle AWS-specific errors cleanly.
from botocore.exceptions import ClientError


# PROJECT_ROOT points to the main project folder.
# This helps this script import app.config correctly.
PROJECT_ROOT = Path(__file__).resolve().parent.parent


# Add the project root to Python's import path.
# This allows: from app.config import ...
sys.path.append(str(PROJECT_ROOT))


# Import S3 config values from your app config.
from app.config import (
    AWS_REGION,
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    S3_BUCKET_NAME,
    is_s3_configured,
    get_missing_s3_settings,
)


def create_s3_client():
    """
    Create and return an S3 client.

    A boto3 client is an object that can call AWS service APIs.
    Here, it will call S3 APIs.
    """

    # Create an S3 client using credentials from .env.
    return boto3.client(
        "s3",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )


def test_bucket_access(s3_client):
    """
    Check whether the bucket exists and whether our IAM user can access it.
    """

    # head_bucket does not upload anything.
    # It only checks bucket existence and permission.
    s3_client.head_bucket(Bucket=S3_BUCKET_NAME)

    # If no error happens, bucket access is successful.
    print(f"S3 bucket access successful: {S3_BUCKET_NAME}")


def test_upload_download_delete(s3_client):
    """
    Test upload, download, and delete using one tiny test file.
    """

    # This key is allowed because your IAM policy allows documents/*.
    test_key = "documents/smoke-test/s3-test.txt"

    # Create tiny test content.
    test_content = b"Hello from Document Intelligence RAG S3 smoke test."

    # Convert bytes into a file-like object.
    test_file = BytesIO(test_content)

    # Upload the test file to S3.
    s3_client.upload_fileobj(
        test_file,
        S3_BUCKET_NAME,
        test_key,
        ExtraArgs={
            "ContentType": "text/plain"
        },
    )

    # Print upload success.
    print(f"Upload successful: s3://{S3_BUCKET_NAME}/{test_key}")

    # Download the same object from S3.
    response = s3_client.get_object(
        Bucket=S3_BUCKET_NAME,
        Key=test_key,
    )

    # Read the downloaded content.
    downloaded_content = response["Body"].read()

    # Compare uploaded and downloaded content.
    if downloaded_content == test_content:
        print("Download successful and content matched.")
    else:
        print("Download failed because content did not match.")

    # Delete the test object from S3.
    s3_client.delete_object(
        Bucket=S3_BUCKET_NAME,
        Key=test_key,
    )

    # Print delete success.
    print("Delete successful.")


def main():
    """
    Run the complete S3 smoke test.
    """

    # First check whether .env has all required values.
    if not is_s3_configured():
        print("S3 configuration is incomplete.")
        print("Missing settings:", get_missing_s3_settings())
        return

    # Print region for confirmation.
    print(f"Using AWS region: {AWS_REGION}")

    # Print bucket name for confirmation.
    print(f"Using S3 bucket: {S3_BUCKET_NAME}")

    # Create S3 client.
    s3_client = create_s3_client()

    try:
        # Test bucket access.
        test_bucket_access(s3_client)

        # Test upload, download, and delete.
        test_upload_download_delete(s3_client)

        # Final success message.
        print("S3 smoke test completed successfully.")

    except ClientError as error:
        print("S3 smoke test failed.")
        print(error)


if __name__ == "__main__":
    main()