import hashlib
import hmac
import re
import urllib.parse
from datetime import datetime, timezone

from requests import get as requests_get, put as requests_put, Response


class AwsS3:
    def __init__(self, aws_key_id: str, aws_secret: str, region: str, bucket: str) -> None:
        self.aws_key_id = aws_key_id
        self.aws_secret = aws_secret
        self.region = region
        self.bucket = bucket

    def headers(self, object_key: str, data: tuple[bytes, str] | None = None) -> dict:
        host = f"{self.bucket}.s3.{self.region}.amazonaws.com"
        # request time
        now = datetime.now(timezone.utc)
        amz_date = now.strftime('%Y%m%dT%H%M%SZ')
        date_stamp = now.strftime('%Y%m%d')

        method = 'PUT'
        if not data:
            method = 'GET'
            data = b'', ''

        binary_data, content_type = data

        payload_hash = hashlib.sha256(binary_data).hexdigest()  # type: ignore

        # canonical request
        canonical_uri = f"/{urllib.parse.quote(object_key)}"  # URL encode the key
        canonical_querystring = ''
        canonical_headers = f"host:{host}\nx-amz-content-sha256:{payload_hash}\nx-amz-date:{amz_date}\n"
        signed_headers = 'host;x-amz-content-sha256;x-amz-date'
        if content_type:
            canonical_headers = f"content-type:{content_type}\n{canonical_headers}"
            signed_headers = f'content-type;{signed_headers}'

        canonical_request = f"{method}\n{canonical_uri}\n{canonical_querystring}\n{canonical_headers}\n{signed_headers}\n{payload_hash}"

        # string to sign
        algorithm = 'AWS4-HMAC-SHA256'
        credential_scope = f"{date_stamp}/{self.region}/s3/aws4_request"
        string_to_sign = f"{algorithm}\n{amz_date}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"  # type: ignore

        # compute the signature
        k_date = hmac.new(('AWS4' + self.aws_secret).encode('utf-8'), date_stamp.encode('utf-8'), hashlib.sha256).digest()  # type: ignore
        k_region = hmac.new(k_date, self.region.encode('utf-8'), hashlib.sha256).digest()  # type: ignore
        k_service = hmac.new(k_region, b's3', hashlib.sha256).digest()  # type: ignore
        k_signing = hmac.new(k_service, b'aws4_request', hashlib.sha256).digest()  # type: ignore
        signature = hmac.new(k_signing, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()  # type: ignore

        # build authorization header
        authorization_header = f"{algorithm} Credential={self.aws_key_id}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}"
        return {
            'Host': host,
            'x-amz-date': amz_date,
            'x-amz-content-sha256': payload_hash,
            'Authorization': authorization_header,
        }

    def access_s3_object(self, object_key: str) -> Response:
        headers = self.headers(object_key)
        endpoint = f"https://{headers['Host']}/{object_key}"
        return requests_get(endpoint, headers=headers)

    def upload_binary_to_s3(self, object_key: str, binary_data: bytes, content_type: str):
        headers = self.headers(object_key, (binary_data, content_type)) | {
            'Content-Type': content_type,
            'Content-Length': str(len(binary_data)),
        }
        endpoint = f"https://{headers['Host']}/{object_key}"
        return requests_put(endpoint, headers=headers, data=binary_data)

    def list_s3_objects(self):
        headers = self.headers('')
        endpoint = f"https://{headers['Host']}"
        response = requests_get(endpoint, headers=headers)

        objects = []
        contents_pattern = re.compile(r'<Contents>(.*?)</Contents>', re.DOTALL)
        for content_match in contents_pattern.finditer(response.content.decode('utf-8')):
            content_xml = content_match.group(1)
            key_match = re.search(r'<Key>(.*?)</Key>', content_xml)
            size_match = re.search(r'<Size>(.*?)</Size>', content_xml)
            modified_match = re.search(r'<LastModified>(.*?)</LastModified>', content_xml)

            obj_info = {
                'key': key_match.group(1) if key_match else "",
                'size': int(size_match.group(1)) if size_match else 0,
                'lastModified': modified_match.group(1) if modified_match else "",
            }
            objects.append(obj_info)

        return objects
