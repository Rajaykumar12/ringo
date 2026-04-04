"""
blob_sync.py — Azure Blob Storage document sync.
Downloads documents from a configured Azure Blob container to local folder.
Falls back to local documents/ folder if Azure is not configured.
"""
import os


def sync_documents_from_blob(local_folder: str = "documents"):
    """Download documents from Azure Blob Storage to local folder.

    Requires env vars:
    - AZURE_STORAGE_CONNECTION_STRING: From Azure Portal → Storage Account → Access keys
    - AZURE_STORAGE_CONTAINER_NAME: Blob container name (default: 'documents')

    Falls back to local documents/ folder if not configured (for local dev).
    """
    connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    container_name = os.environ.get("AZURE_STORAGE_CONTAINER_NAME", "documents")

    if not connection_string:
        print("AZURE_STORAGE_CONNECTION_STRING not set - using local documents/ folder")
        return

    try:
        from azure.storage.blob import ContainerClient

        os.makedirs(local_folder, exist_ok=True)
        container_client = ContainerClient.from_connection_string(connection_string, container_name)

        blob_list = list(container_client.list_blobs())
        blob_names = {blob.name for blob in blob_list}
        print(f"Found {len(blob_list)} file(s) in Azure Blob Storage '{container_name}'")

        # Delete local files that no longer exist in blob storage
        if os.path.exists(local_folder):
            for local_file in os.listdir(local_folder):
                if local_file not in blob_names:
                    local_path = os.path.join(local_folder, local_file)
                    print(f"  Deleting orphaned file: {local_file}")
                    os.remove(local_path)

        for blob in blob_list:
            local_path = os.path.join(local_folder, blob.name)
            if os.path.exists(local_path) and os.path.getsize(local_path) == blob.size:
                print(f"  Already up to date: {blob.name}")
                continue
            print(f"  Downloading: {blob.name} ({blob.size} bytes)")
            blob_data = container_client.download_blob(blob.name).readall()
            with open(local_path, "wb") as f:
                f.write(blob_data)

        print("Azure Blob Storage sync complete")
    except Exception as e:
        print(f"Azure Blob sync failed: {e}. Falling back to local documents/")


def upload_document(filename: str, data: bytes, local_folder: str = "documents") -> None:
    """Upload a document to Azure Blob Storage (or local folder if Azure not configured)."""
    connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    container_name = os.environ.get("AZURE_STORAGE_CONTAINER_NAME", "documents")

    if connection_string:
        try:
            from azure.storage.blob import BlobServiceClient
            client = BlobServiceClient.from_connection_string(connection_string)
            blob_client = client.get_blob_client(container=container_name, blob=filename)
            blob_client.upload_blob(data, overwrite=True)
            print(f"Uploaded '{filename}' to Azure Blob Storage '{container_name}'")
            return
        except Exception as e:
            print(f"Azure upload failed: {e}. Saving locally instead.")

    # Local fallback
    os.makedirs(local_folder, exist_ok=True)
    with open(os.path.join(local_folder, filename), "wb") as f:
        f.write(data)
    print(f"Saved '{filename}' to local {local_folder}/")


def delete_document(filename: str, local_folder: str = "documents") -> None:
    """Delete a document from Azure Blob Storage and local folder."""
    connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    container_name = os.environ.get("AZURE_STORAGE_CONTAINER_NAME", "documents")

    if connection_string:
        try:
            from azure.storage.blob import BlobServiceClient
            client = BlobServiceClient.from_connection_string(connection_string)
            client.get_blob_client(container=container_name, blob=filename).delete_blob()
            print(f"Deleted '{filename}' from Azure Blob Storage")
        except Exception as e:
            print(f"Azure delete failed: {e}")

    local_path = os.path.join(local_folder, filename)
    if os.path.exists(local_path):
        os.remove(local_path)
        print(f"Deleted '{filename}' from local {local_folder}/")
