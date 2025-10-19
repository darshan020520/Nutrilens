import boto3
from botocore.exceptions import ClientError
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


class S3Service:
    """Service for handling S3 operations for receipt images"""

    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            config=boto3.session.Config(signature_version='s3v4')
        )
        self.bucket_name = settings.s3_bucket

    def upload_file(self, file_path: str, s3_key: str) -> str:
        """
        Upload file to S3 and return public URL

        Args:
            file_path: Local file path
            s3_key: S3 object key (e.g., 'receipts/user_123/uuid.jpg')

        Returns:
            Public S3 URL

        Raises:
            ClientError: If upload fails
        """
        try:
            self.s3_client.upload_file(
                file_path,
                self.bucket_name,
                s3_key,
                ExtraArgs={'ContentType': 'image/jpeg'}
            )

            # Generate public URL
            url = f"https://{self.bucket_name}.s3.{settings.s3_region}.amazonaws.com/{s3_key}"
            logger.info(f"Uploaded to S3: {url}")
            print("upload succesful", url)
            return url

        except ClientError as e:
            logger.error(f"S3 upload failed: {e}")
            print(e)
            raise

    def upload_fileobj(self, file_obj, s3_key: str, content_type: str = 'image/jpeg') -> str:
        """
        Upload file object (from FastAPI UploadFile) to S3

        Args:
            file_obj: File object or bytes
            s3_key: S3 object key
            content_type: MIME type of the file

        Returns:
            Public S3 URL

        Raises:
            ClientError: If upload fails
        """
        try:
            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket_name,
                s3_key,
                ExtraArgs={'ContentType': content_type}
            )

            # Generate public URL
            url = f"https://{self.bucket_name}.s3.{settings.s3_region}.amazonaws.com/{s3_key}"
            logger.info(f"Uploaded file object to S3: {url}")
            return url

        except ClientError as e:
            logger.error(f"S3 upload failed: {e}")
            raise

    def generate_presigned_url(self, s3_key: str, expiration: int = 3600) -> str:
        """
        Generate presigned URL for private S3 object

        Args:
            s3_key: S3 object key
            expiration: URL expiration in seconds (default 1 hour)

        Returns:
            Presigned URL

        Raises:
            ClientError: If URL generation fails
        """
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=expiration
            )
            logger.info(f"Generated presigned URL for {s3_key}")
            return url
        except ClientError as e:
            logger.error(f"Presigned URL generation failed: {e}")
            raise

    def delete_file(self, s3_key: str) -> bool:
        """
        Delete file from S3

        Args:
            s3_key: S3 object key

        Returns:
            True if successful, False otherwise
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            logger.info(f"Deleted from S3: {s3_key}")
            return True
        except ClientError as e:
            logger.error(f"S3 delete failed: {e}")
            return False

    def check_bucket_exists(self) -> bool:
        """
        Check if the S3 bucket exists and is accessible

        Returns:
            True if bucket exists and is accessible
        """
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"S3 bucket '{self.bucket_name}' is accessible")
            return True
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == '404':
                logger.error(f"S3 bucket '{self.bucket_name}' does not exist")
            elif error_code == '403':
                logger.error(f"Access denied to S3 bucket '{self.bucket_name}'")
            else:
                logger.error(f"Error checking S3 bucket: {e}")
            return False
