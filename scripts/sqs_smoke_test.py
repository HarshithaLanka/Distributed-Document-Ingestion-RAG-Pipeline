# Import sys so we can add project root to Python path.
import sys

# Import Path to work with file/folder paths safely.
from pathlib import Path

# Import time so we can wait briefly before receiving message.
import time

# Import load_dotenv so this script can read .env.
from dotenv import load_dotenv


# Current file:
# scripts/sqs_smoke_test.py
#
# PROJECT_ROOT becomes:
# Document_Intelligence_RAG/
PROJECT_ROOT = Path(__file__).resolve().parent.parent


# Add project root to Python path.
# This lets us import app.services.sqs_service.
sys.path.append(str(PROJECT_ROOT))


# Load .env file before importing app config/services.
# Important because app.config reads environment variables.
load_dotenv(PROJECT_ROOT / ".env")


# Import SQS service functions after .env is loaded.
from app.services.sqs_service import (  # noqa: E402
    get_queue_attributes,
    send_document_processing_message,
    receive_document_processing_messages,
    delete_message,
)


def run_sqs_smoke_test():
    """
    Run real AWS SQS smoke test.

    This checks:
    1. Can we access queue?
    2. Can we send message?
    3. Can we receive message?
    4. Can we delete message?
    """

    print("Starting SQS smoke test...")

    # Step 1: Check queue access.
    print("\nStep 1: Checking queue attributes...")

    attributes = get_queue_attributes()

    print("Queue access successful.")
    print("ApproximateNumberOfMessages:", attributes.get("ApproximateNumberOfMessages"))
    print("VisibilityTimeout:", attributes.get("VisibilityTimeout"))
    print("ReceiveMessageWaitTimeSeconds:", attributes.get("ReceiveMessageWaitTimeSeconds"))

    # Step 2: Send a test message.
    print("\nStep 2: Sending test message...")

    test_document_id = "sqs_smoke_test_document"

    send_result = send_document_processing_message(
        document_id=test_document_id,
        pipeline_steps=["smoke_test"],
    )

    print("Message sent successfully.")
    print("MessageId:", send_result.get("message_id"))
    print("Message body:", send_result.get("message_body"))

    # Step 3: Wait briefly.
    print("\nWaiting 2 seconds before receiving...")
    time.sleep(2)

    # Step 4: Receive message.
    print("\nStep 3: Receiving message...")

    messages = receive_document_processing_messages(max_messages=1)

    if not messages:
        print("No message received.")
        print("Check queue URL, region, and whether another worker consumed it.")
        return

    message = messages[0]

    print("Message received successfully.")
    print("SQS MessageId:", message.get("message_id"))
    print("Message body:", message.get("body"))

    # Step 5: Delete message.
    print("\nStep 4: Deleting message...")

    receipt_handle = message.get("receipt_handle")

    delete_result = delete_message(receipt_handle)

    print(delete_result.get("message"))

    print("\nSQS smoke test completed successfully.")


# Run this only when executing this file directly.
if __name__ == "__main__":
    run_sqs_smoke_test()